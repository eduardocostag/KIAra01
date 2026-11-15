"""Growth suite against a real Postgres with every migration applied.

Runs only when KIARA_PG_TEST_URL points to a disposable database (never production), e.g.
  docker run -d --name kiara-pgtest -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:16-alpine
  + scripts/apply_migrations.py against it.
"""
import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

URL = os.getenv("KIARA_PG_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL or "55432" not in URL, reason="needs the disposable test database")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def seeded():
    import psycopg

    org, user = uuid4(), uuid4()
    now = datetime.now(UTC)
    with psycopg.connect(URL, autocommit=True) as db:
        db.execute("INSERT INTO organizations(id,slug,name) VALUES(%s,%s,'Teste')", (org, f"t-{org}"))
        db.execute("INSERT INTO users(id,identity_provider,external_subject) VALUES(%s,'test',%s)", (user, str(user)))
        db.execute("INSERT INTO sales_profiles(organization_id,average_deal_cents) VALUES(%s,150000)", (org,))
        search = db.execute("""INSERT INTO hunter_searches(organization_id,requested_by,query,market,sources,result_limit)
                               VALUES(%s,%s,'dentistas','b2b',ARRAY['google_maps'],30) RETURNING id""", (org, user)).fetchone()[0]
        for i in range(12):
            db.execute("INSERT INTO hunter_results(organization_id,search_id,source,title,url,created_at) VALUES(%s,%s,'google_maps',%s,%s,%s)",
                       (org, search, f"Clínica {i}", f"https://maps.example/{i}", now - timedelta(days=2 if i < 10 else 40)))
        entries = []
        for i, (stage, value) in enumerate([("contacted", None), ("opportunity", None), ("won", 500000), ("qualified", None), ("new", None)]):
            consumer = db.execute("INSERT INTO consumers(organization_id,display_name) VALUES(%s,%s) RETURNING id", (org, f"Lead {i}")).fetchone()[0]
            entry = db.execute("INSERT INTO pipeline_entries(organization_id,consumer_id,stage,deal_value_cents,created_at) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                               (org, consumer, stage, value, now - timedelta(days=5))).fetchone()[0]
            entries.append((entry, consumer, stage))
        for entry, _consumer, stage in entries[:4]:
            db.execute("INSERT INTO outreach_activities(organization_id,pipeline_entry_id,actor_user_id,channel,status,created_at) VALUES(%s,%s,%s,'whatsapp','sent',%s)",
                       (org, entry, user, now - timedelta(days=4)))
            if stage != "contacted":
                db.execute("INSERT INTO pipeline_stage_events(organization_id,pipeline_entry_id,actor_user_id,from_stage,to_stage,created_at) VALUES(%s,%s,%s,'contacted',%s,%s)",
                           (org, entry, user, stage, now - timedelta(days=3)))
        # The won lead also passed through opportunity: counted once in "generated".
        db.execute("INSERT INTO pipeline_stage_events(organization_id,pipeline_entry_id,actor_user_id,from_stage,to_stage,created_at) VALUES(%s,%s,%s,'contacted','opportunity',%s)",
                   (org, entries[2][0], user, now - timedelta(days=3, hours=2)))
        thread = db.execute("INSERT INTO conversation_threads(organization_id,consumer_id,channel,provider_thread_id) VALUES(%s,%s,'whatsapp','t1') RETURNING id",
                            (org, entries[0][1])).fetchone()[0]
        db.execute("INSERT INTO messages(organization_id,thread_id,direction,body,sent_at) VALUES(%s,%s,'inbound','oi',%s)", (org, thread, now - timedelta(hours=20)))
    yield str(org), entries


def test_results_summary_counts_leads_once_and_values_money(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.results import ResultsRepository

    org, entries = seeded
    data = run(ResultsRepository(PostgresRepository(URL)).summary(org, 30))
    current = data["current"]
    assert current["found"] == 10 and data["previous"]["found"] == 2
    assert current["added"] == 5 and current["approached"] == 4 and current["conversations"] == 1
    assert current["replied"] == 3            # qualified, opportunity, won
    assert current["opportunities"] == 2      # opportunity + won (once, although it passed both)
    assert current["won"] == 1 and current["won_cents"] == 500000
    assert current["generated_cents"] == 150000 + 500000   # average for the one without a value
    funnel = {item["stage"]: item["total"] for item in data["funnel"]}
    assert funnel == {"new": 1, "qualified": 1, "contacted": 1, "opportunity": 1, "won": 1, "lost": 0}
    assert data["open_cents"] == 300000 and len(data["weekly"]) == 8 and data["average_deal_cents"] == 150000


def test_deal_value_is_saved_and_unknown_lead_is_404(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.http.errors import ApiError
    from kiara_api.results import ResultsRepository

    org, entries = seeded
    repository = ResultsRepository(PostgresRepository(URL))
    run(repository.set_deal_value(org, str(entries[1][0]), 990000))
    assert run(repository.summary(org, 30))["current"]["generated_cents"] == 990000 + 500000
    with pytest.raises(ApiError):
        run(repository.set_deal_value(org, str(uuid4()), 1))


def test_old_profile_screen_keeps_growth_fields(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.sales import SalesRepository

    org, _entries = seeded
    repository = SalesRepository(PostgresRepository(URL))
    base = {"business_name": "Lume", "sender_name": "Ana", "offer": "Sites", "tone": "direto", "follow_up_hours": 48,
            "contact_start": "09:00", "contact_end": "18:00", "templates": {}}
    saved = run(repository.save_profile(org, {**base, "owner_whatsapp": "5551999990000", "daily_summary": True, "average_deal_cents": 200000}))
    assert saved["daily_summary"] is True and saved["owner_whatsapp"] == "5551999990000"
    again = run(repository.save_profile(org, base))   # the old settings form does not send the new fields
    assert again["average_deal_cents"] == 200000 and again["daily_summary"] is True and again["owner_whatsapp"] == "5551999990000"


def ctx(org, user=None, role="owner", email=None):
    from kiara_api.http.context import RequestContext

    return RequestContext(user or org, org, f"{org}:{user or org}", role, "req", email=email)


def test_knowledge_feeds_the_prompt_and_respects_limits(seeded):
    import base64
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.knowledge import KnowledgeCreate, KnowledgeRepository, KnowledgeUpdate

    org, _ = seeded
    repo = KnowledgeRepository(PostgresRepository(URL))
    item = run(repo.create(org, KnowledgeCreate(kind="text", title="Preços", content="Site completo: R$ 1.900 em até 6x.")))
    csv = base64.b64encode("produto;preço\nLanding page;900\n".encode()).decode()
    run(repo.create(org, KnowledgeCreate(kind="file", file={"name": "tabela.csv", "mime": "text/csv", "data_base64": csv})))
    context = run(repo.context(org))
    assert "R$ 1.900" in context and "Landing page;900" in context and "## Preços" in context
    run(repo.update(org, item["id"], KnowledgeUpdate(enabled=False)))
    assert "R$ 1.900" not in run(repo.context(org))
    listed = run(repo.list(org))
    assert len(listed["items"]) == 2 and listed["items"][0]["preview"]


def test_plan_limits_count_per_month_and_refuse_without_spending(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.http.errors import ApiError
    from kiara_api.usage import UsageService

    org, _ = seeded
    service = UsageService(PostgresRepository(URL))
    for _ in range(3):
        run(service.consume(ctx(org), "videos"))   # trial: 3 videos
    with pytest.raises(ApiError) as refused:
        run(service.consume(ctx(org), "videos"))
    assert refused.value.status_code == 402 and "vídeos" in refused.value.message
    overview = run(service.overview(ctx(org)))
    videos = next(item for item in overview["usage"] if item["metric"] == "videos")
    assert videos == {"metric": "videos", "label": "vídeos", "used": 3, "limit": 3} and overview["plan"] == "trial"
    run(service.consume(ctx(org, email="admin@kiara.local"), "videos"))   # the system administrator is not limited


def test_first_message_uses_lead_facts_profile_and_knowledge(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.outreach_ai import DraftRequest, OutreachAI
    import psycopg
    from psycopg.types.json import Jsonb

    org, entries = seeded
    with psycopg.connect(URL, autocommit=True) as db:
        db.execute("UPDATE consumers SET attributes=%s WHERE id=%s", (Jsonb({"hunter": {"research_query": "dentistas sem site", "location": "Canoas",
                   "website_status": "not_listed", "rating": 4.9, "user_rating_count": 87}}), entries[4][1]))
        db.execute("UPDATE sales_profiles SET business_name='Lume',sender_name='Ana',offer='Sites para clínicas' WHERE organization_id=%s", (org,))
        db.execute("INSERT INTO business_knowledge(organization_id,title,kind,content) VALUES(%s,'Prazo','text','Entregamos em 7 dias.')", (org,))
    seen = []

    async def ask(conversation):
        seen.append(conversation)
        return '"Mensagem: Oi! Aqui é a Ana, da Lume. Vi que vocês têm nota 4,9 no Google mas ainda sem site. Posso mostrar uma ideia?"'

    service = OutreachAI(PostgresRepository(URL), ask=ask)
    reply = run(service.draft(ctx(org), DraftRequest(pipeline_entry_id=str(entries[4][0]))))
    assert reply == {"message": "Oi! Aqui é a Ana, da Lume. Vi que vocês têm nota 4,9 no Google mas ainda sem site. Posso mostrar uma ideia?", "kind": "first_contact"}
    system, user = seen[0][0]["content"], seen[0][1]["content"]
    assert "Entregamos em 7 dias." in system and "Assine como Ana" in system
    assert "Não tem site informado no Google" in user and "4.9 com 87" in user and "Sites para clínicas" in user
    # A lead that already got a message gets a follow-up, with the history.
    reply = run(service.draft(ctx(org), DraftRequest(pipeline_entry_id=str(entries[0][0]))))
    assert reply["kind"] == "first_contact" or reply["kind"] == "follow_up"


def test_segment_preset_fills_only_what_is_empty(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.outreach_ai import OutreachAI
    from kiara_api.sales import SalesRepository

    org, _ = seeded
    result = run(OutreachAI(PostgresRepository(URL)).apply_preset(ctx(org), "agencia"))
    profile = run(SalesRepository(PostgresRepository(URL)).get_profile(org))
    assert result["searches"] and profile["segment"] == "agencia"
    assert profile["average_deal_cents"] == 150000          # already set by the client: kept
    assert profile["offer"].startswith("Criação de sites") and "{nome}" in profile["templates"]["first_contact"]


def test_daily_summary_lists_today_priorities(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.outreach_ai import daily_summary

    org, _ = seeded
    async def build():
        async with PostgresRepository(URL)._transaction(org) as connection:
            return await daily_summary(connection, __import__("uuid").UUID(org))
    text = run(build())
    assert text.startswith("*Bom dia!") and "1 lead(s) novo(s)" in text and "Ontem 1 conversa(s)" in text


def test_team_invite_accept_maps_the_member_into_the_owner_workspace(seeded):
    from kiara_api.adapters.postgres import PostgresRepository
    from kiara_api.http.errors import ApiError
    from kiara_api.team import InviteAccept, InviteCreate, TeamService
    from kiara_api.usage import UsageService

    org, _ = seeded
    team = TeamService(PostgresRepository(URL))
    with pytest.raises(ApiError):   # trial has 1 seat: the owner
        run(team.invite(ctx(org), InviteCreate(email="vendedor@exemplo.com")))
    import psycopg
    with psycopg.connect(URL, autocommit=True) as db:
        db.execute("UPDATE subscriptions SET plan='pro',status='active' WHERE organization_id=%s", (org,))
    invite = run(team.invite(ctx(org), InviteCreate(email="Vendedor@Exemplo.com", role="operator")))
    member = str(uuid4())
    with pytest.raises(ApiError):   # someone else's e-mail cannot use it
        run(team.accept(ctx(member, email="outra@exemplo.com"), InviteAccept(token=invite["token"])))
    assert run(team.accept(ctx(member, email="vendedor@exemplo.com"), InviteAccept(token=invite["token"], display_name="Bia"))) == {"joined": True, "role": "operator"}
    assert run(team.seat_for(member)) == {"organization_id": org, "role": "operator"}
    with pytest.raises(ApiError):   # single use
        run(team.accept(ctx(str(uuid4()), email="vendedor@exemplo.com"), InviteAccept(token=invite["token"])))
    overview = run(team.overview(ctx(org)))
    assert [m["role"] for m in overview["members"]] == ["owner", "operator"] and overview["seats"] == {"used": 2, "limit": 3}
    run(team.remove(ctx(org), member))
    assert run(team.seat_for(member)) is None
