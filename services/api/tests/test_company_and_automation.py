import asyncio
import io
import json
import time
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

from kiara_api.automation import (
    AutomationRepository,
    Decision,
    FlowSave,
    RunEnv,
    RunState,
    initial_queue,
    next_schedule,
    run_flow,
    run_status,
)
from kiara_api.company_data import CompanyLookupError, clean_cnpj, fetch_company, find_cnpjs, lead_fit
from kiara_api.http.context import RequestContext
from kiara_api.http.errors import ApiError
from kiara_api.lead_company import LeadCompanyRepository

VALID = "11222333000181"
REGISTRY = {"razao_social": "ACME LTDA", "nome_fantasia": "Acme", "descricao_situacao_cadastral": "ATIVA",
            "data_inicio_atividade": "2015-03-10", "porte": "DEMAIS", "cnae_fiscal_descricao": "Clínica odontológica",
            "municipio": "PORTO ALEGRE", "uf": "RS", "capital_social": 50000, "opcao_pelo_mei": False,
            "qsa": [{"nome_socio": "ANA SOUZA", "qualificacao_socio": "Sócio-Administrador", "cnpj_cpf_do_socio": "***123***"}]}


# ------------------------------------------------------------- CNPJ and fit score

def test_cnpj_check_digits_and_page_discovery():
    assert clean_cnpj("11.222.333/0001-81") == VALID
    assert clean_cnpj("11.222.333/0001-82") is None
    assert clean_cnpj("00000000000000") is None
    page = "Rodapé © Acme — CNPJ 11.222.333/0001-81 · telefone 51 99999-0000 · 11222333000182"
    assert find_cnpjs(page) == [VALID]


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_company_normalizes_registry_and_drops_partner_ids():
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        return _Response(json.dumps(REGISTRY).encode())

    company = fetch_company("11.222.333/0001-81", opener=opener)
    assert calls == [f"https://brasilapi.com.br/api/cnpj/v1/{VALID}"]
    assert company["legal_name"] == "ACME LTDA" and company["active"] and company["cnpj_formatted"] == "11.222.333/0001-81"
    assert company["partners"] == [{"name": "ANA SOUZA", "role": "Sócio-Administrador"}]
    assert "***123***" not in json.dumps(company)


def test_fetch_company_falls_back_and_reports_not_found():
    def missing(request, timeout):
        raise HTTPError(request.full_url, 404, "not found", None, None)

    with pytest.raises(CompanyLookupError) as error:
        fetch_company(VALID, opener=missing)
    assert error.value.code == "cnpj_not_found"

    def flaky(request, timeout):
        if "brasilapi" in request.full_url:
            raise OSError("down")
        return _Response(json.dumps(REGISTRY).encode())

    assert fetch_company(VALID, opener=flaky)["source"] == "minhareceita"


def test_lead_fit_explains_the_score():
    strong = lead_fit({"whatsapp_url": "https://wa.me/5551999990000", "rating": 4.8, "user_rating_count": 230,
                       "website_status": "not_listed", "company": {"active": True, "opened_at": "2015-03-10", "size": "DEMAIS"}},
                      today=date(2026, 11, 13))
    assert strong["grade"] == "A" and strong["score"] >= 70
    texts = " ".join(reason["text"] for reason in strong["reasons"])
    assert "230 avaliações" in texts and "Sem site" in texts and "11 anos" in texts
    closed = lead_fit({"phone": "51 3333-0000", "company": {"active": False, "status": "BAIXADA"}})
    assert closed["grade"] == "D" and any("baixada" in reason["text"] for reason in closed["reasons"])
    assert lead_fit({})["score"] == 0


def _consumer_store(attributes):
    state = {"attributes": attributes}

    class Connection:
        async def execute(self, sql, params):
            if sql.startswith("UPDATE consumers"):
                state["attributes"] = json.loads(params[0])
            return self

        async def fetchone(self):
            return {"attributes": state["attributes"]}

    class Store:
        @asynccontextmanager
        async def _transaction(self, organization_id):
            yield Connection()

    return Store(), state


def test_enrich_finds_cnpj_on_website_and_saves_company():
    store, state = _consumer_store({"hunter": {"website_url": "https://acme.com.br", "phone": "51 3333-0000"}, "notes": "manter"})
    repository = LeadCompanyRepository(store, lookup=lambda cnpj: {"cnpj": cnpj, "active": True, "opened_at": "2015-01-01"},
                                       discover=lambda url: VALID)
    context = RequestContext("user", "org", "member", "operator", "test")
    result = asyncio.run(repository.enrich(context, "lead-1", None))
    assert result["company"]["cnpj_source"] == "website"
    assert state["attributes"]["company"]["cnpj"] == VALID and state["attributes"]["notes"] == "manter"
    assert result["fit"]["has_company_data"]


def test_enrich_requires_cnpj_when_lead_has_no_site():
    store, _ = _consumer_store({"hunter": {}})
    repository = LeadCompanyRepository(store, lookup=lambda cnpj: {}, discover=lambda url: None)
    context = RequestContext("user", "org", "member", "operator", "test")
    with pytest.raises(ApiError) as error:
        asyncio.run(repository.enrich(context, "lead-1", None))
    assert error.value.code == "cnpj_required"
    with pytest.raises(ApiError) as error:
        asyncio.run(repository.enrich(context, "lead-1", "123"))
    assert error.value.code == "cnpj_invalid"


# ------------------------------------------------------------- automation runner

def _node(node_id, kind, **config):
    return {"id": node_id, "type": kind, "x": 0, "y": 0, "config": config}


def _env(answers=None, approvals=None, notices=None):
    answers = list(answers or [])
    approvals = approvals if approvals is not None else []
    notices = notices if notices is not None else []

    async def ask(prompt):
        return answers.pop(0) if answers else f"texto sobre {prompt[:20]}"

    async def leads(stage, limit):
        return [f"Lead {index} · etapa: {stage}" for index in range(min(limit, 2))]

    async def latest():
        return "Clínica Sorriso · 51 99999-0000"

    async def http_get(url):
        return '{"ok": true}'

    async def request_approval(node, kind, title, payload):
        approvals.append({"kind": kind, "title": title, "payload": payload})
        return f"req-{len(approvals)}"

    async def notify(title, text):
        notices.append((title, text))

    return RunEnv(ask=ask, leads=leads, latest_lead=latest, http_get=http_get, request_approval=request_approval, notify=notify)


def _run(definition, trigger="manual", value="", env=None, state=None):
    state = state or RunState(pending=initial_queue(definition, trigger, value))
    return asyncio.run(run_flow(definition, state, env or _env(), deadline=time.monotonic() + 30))


def test_lead_welcome_flow_sends_message_to_approval_not_to_customer():
    definition = {"nodes": [_node("t", "trigger.lead"), _node("c", "ai.classify", question="Vale abordar? {{entrada}}"),
                            _node("if", "logic.condition", contains="SIM"), _node("w", "ai.generate", prompt="Mensagem para {{entrada}}"),
                            _node("send", "messages.whatsapp", to="{{lead}}", text="{{entrada}}"), _node("skip", "logic.notify", title="Descartado")],
                  "edges": [{"id": "1", "from": "t", "to": "c"}, {"id": "2", "from": "c", "to": "if"},
                            {"id": "3", "from": "if", "to": "w", "port": "yes"}, {"id": "4", "from": "w", "to": "send"},
                            {"id": "5", "from": "if", "to": "skip", "port": "no"}]}
    approvals, notices = [], []
    state = _run(definition, "lead", "Clínica Sorriso · 51 99999-0000", _env(["Sim, parece adequado.", "Olá! Tudo bem?"], approvals, notices))
    statuses = [(step["node_id"], step["status"]) for step in state.steps]
    assert statuses == [("t", "done"), ("c", "done"), ("if", "done"), ("w", "done"), ("send", "approval")]
    assert approvals[0]["kind"] == "whatsapp" and approvals[0]["payload"]["text"] == "Olá! Tudo bem?"
    assert notices == [] and run_status(state) == "done"


def test_classify_no_goes_to_other_branch_and_notifies():
    definition = {"nodes": [_node("t", "trigger.manual"), _node("c", "ai.classify", question="?"), _node("if", "logic.condition", contains="SIM"),
                            _node("skip", "logic.notify", title="Descartado")],
                  "edges": [{"id": "1", "from": "t", "to": "c"}, {"id": "2", "from": "c", "to": "if"}, {"id": "3", "from": "if", "to": "skip", "port": "no"}]}
    notices = []
    _run(definition, env=_env(["Não, sem interesse."], notices=notices))
    assert notices == [("Descartado", "NÃO")]


def test_long_delay_pauses_run_and_resumes_on_next_tick():
    definition = {"nodes": [_node("t", "trigger.manual"), _node("d", "logic.delay", seconds=3600), _node("n", "logic.notify", title="Depois")],
                  "edges": [{"id": "1", "from": "t", "to": "d"}, {"id": "2", "from": "d", "to": "n"}]}
    notices = []
    state = _run(definition, env=_env(notices=notices))
    assert run_status(state) == "waiting" and state.resume_at and notices == []
    state.resume_at = None
    state = _run(definition, env=_env(notices=notices), state=state)
    assert notices == [("Depois", "")] and run_status(state) == "done"


def test_blocked_and_failing_blocks_stop_only_their_branch():
    definition = {"nodes": [_node("t", "trigger.manual"), _node("js", "code.js", code="return 1"), _node("crm", "crm.read", stage="new", limit=5)],
                  "edges": [{"id": "1", "from": "t", "to": "js"}, {"id": "2", "from": "t", "to": "crm"}]}
    state = _run(definition)
    by_node = {step["node_id"]: step for step in state.steps}
    assert by_node["js"]["status"] == "blocked" and by_node["crm"]["status"] == "done"
    assert "Lead 0 · etapa: new" in by_node["crm"]["output"] and run_status(state) == "partial"


def test_cycles_stop_at_the_step_limit():
    definition = {"nodes": [_node("t", "trigger.manual"), _node("a", "logic.condition", contains="x")],
                  "edges": [{"id": "1", "from": "t", "to": "a"}, {"id": "2", "from": "a", "to": "a", "port": "no"}]}
    state = _run(definition)
    assert state.steps[-1]["status"] == "error" and "passou de 60 passos" in state.steps[-1]["message"]


def test_schedule_respects_sao_paulo_time_and_weekdays():
    friday_evening = datetime(2026, 11, 13, 22, 0, tzinfo=UTC)  # 19:00 in São Paulo, Friday
    assert next_schedule({"cadence": "daily", "time": "08:00"}, friday_evening) == datetime(2026, 11, 14, 11, 0, tzinfo=UTC)
    assert next_schedule({"cadence": "weekdays", "time": "08:00"}, friday_evening) == datetime(2026, 11, 16, 11, 0, tzinfo=UTC)
    assert next_schedule({"cadence": "weekly", "weekday": "1", "time": "10:00"}, friday_evening) == datetime(2026, 11, 16, 13, 0, tzinfo=UTC)
    assert next_schedule({"cadence": "weekly", "weekday": "5", "time": "20:00"}, friday_evening) == datetime(2026, 11, 13, 23, 0, tzinfo=UTC)


def test_flow_payload_rejects_unknown_blocks_and_tenant_fields():
    good = {"name": "Fluxo", "definition": {"nodes": [_node("t", "trigger.manual")], "edges": []}}
    assert FlowSave.model_validate(good).name == "Fluxo"
    with pytest.raises(ValidationError):
        FlowSave.model_validate({**good, "definition": {"nodes": [_node("t", "shell.exec")], "edges": []}})
    with pytest.raises(ValidationError):
        FlowSave.model_validate({**good, "organization_id": "other"})


def test_only_owners_and_admins_decide_approvals():
    repository = AutomationRepository(postgres=object())
    viewer = RequestContext("user", "org", "member", "operator", "test")
    with pytest.raises(ApiError) as error:
        asyncio.run(repository.decide(viewer, "req", Decision(decision="approve", version=1)))
    assert error.value.status_code == 403


def test_tick_requires_worker_token(monkeypatch):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from kiara_api.automation import create_automation_router

    class Repo:
        async def tick(self, worker):
            return {"runs_created": 0, "runs_processed": 0, "statuses": []}

    app = FastAPI()

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = "test"
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status_code)

    app.include_router(create_automation_router(Repo()))
    monkeypatch.setenv("KIARA_WORKER_TOKEN", "s3cret-token")
    monkeypatch.delenv("CRON_SECRET", raising=False)
    client = TestClient(app)
    assert client.post("/v1/automation/internal/tick").status_code == 401
    assert client.post("/v1/automation/internal/tick", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/v1/automation/internal/tick", headers={"Authorization": "Bearer s3cret-token"}).json()["runs_created"] == 0


def test_automation_migration_is_atomic_and_tenant_scoped():
    sql = (Path(__file__).parents[1] / "migrations" / "0030_automation_and_approvals.sql").read_text(encoding="utf-8")
    assert sql.lstrip().startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    for table in ("automation_flows", "automation_runs", "action_requests"):
        assert f"CREATE TABLE {table}" in sql and f"'{table}'" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON automation_triggers, automation_work_queue FROM PUBLIC, anon, authenticated" in sql


def test_maps_search_is_anchored_on_brazil():
    from kiara_api.hunter import maps_search_url

    url = maps_search_url("padaria")
    assert url.startswith("https://www.google.com/maps/search/padaria/@-14.235,-51.9253,5z")
    assert "gl=br" in url and "hl=pt-BR" in url
    assert "/maps/search/padaria%20Porto%20Alegre/" in maps_search_url("padaria Porto Alegre")
