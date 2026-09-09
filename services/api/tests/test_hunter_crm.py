"""CRM integration contracts; local-Postgres test is opt-in and rolls back all data."""
import asyncio
import json
import os
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.adapters.postgres import PostgresRepository
from kiara_api.hunter_crm import identity_keys, sync_hunter_results


class Cursor:
    def __init__(self, row=None):
        self.row = row

    async def fetchone(self):
        return deepcopy(self.row)


class MemoryConnection:
    """Small SQL boundary fake, not evidence that PostgreSQL constraints ran."""
    def __init__(self):
        self.consumers = {}
        self.entries = {}
        self.result_updates = {}
        self.statements = []

    async def execute(self, sql, params):
        normalized = " ".join(sql.split())
        self.statements.append(normalized)
        if normalized.startswith("SELECT pg_advisory_xact_lock"):
            return Cursor()
        if normalized.startswith("SELECT id,display_name,attributes,consent_status,lifecycle_status FROM consumers"):
            org, consumer_id, keys, username = params
            assert "organization_id=%s" in normalized and "FOR UPDATE" in normalized
            matches = [c for (tenant, _), c in self.consumers.items()
                       if tenant == org and (c["id"] == consumer_id
                          or set(c["attributes"].get("hunter_identity_keys", [])) & set(keys)
                          or username and c["instagram_username"] == username)]
            matches.sort(key=lambda c: c["lifecycle_status"] == "active" and c["consent_status"] not in {"revoked", "opted_out"})
            return Cursor(matches[0] if matches else None)
        if normalized.startswith("INSERT INTO consumers"):
            org, consumer_id, title, username, attrs = params
            if (org, consumer_id) in self.consumers:
                return Cursor()
            self.consumers[org, consumer_id] = {
                "id": consumer_id, "display_name": title, "instagram_username": username,
                "attributes": json.loads(attrs), "consent_status": "unknown", "lifecycle_status": "active",
            }
            return Cursor({"id": consumer_id})
        if normalized.startswith("UPDATE consumers SET attributes="):
            attrs, title, org, consumer_id = params
            c = self.consumers[org, consumer_id]
            c["attributes"] = json.loads(attrs)
            c["display_name"] = c["display_name"] or title
            return Cursor()
        if normalized.startswith("INSERT INTO pipeline_entries"):
            org, consumer_id = params
            if (org, consumer_id) in self.entries:
                return Cursor()
            entry = {"id": uuid4(), "stage": "new", "version": 1, "next_action": "Review",
                     "owner_membership_id": None, "consumer_id": consumer_id}
            self.entries[org, consumer_id] = entry
            return Cursor({"id": entry["id"]})
        if normalized.startswith("SELECT id FROM pipeline_entries"):
            assert "organization_id=%s" in normalized
            return Cursor(self.entries.get(tuple(params)))
        if normalized.startswith("UPDATE hunter_results SET public_data="):
            attrs, org, search_id, result_id = params
            assert "organization_id=%s AND search_id=%s AND id=%s" in normalized
            self.result_updates[org, search_id, result_id] = json.loads(attrs)
            return Cursor()
        raise AssertionError(f"Unexpected SQL: {normalized}")


def search(**overrides):
    return {"id": uuid4(), "query": "psicólogos", "location": "São Paulo", "market": "b2b",
            "research_mode": "broad", **overrides}


def result(**overrides):
    return {"id": uuid4(), "title": "Clínica teste", "source": "google_maps",
            "url": "https://www.google.com/maps/place/Clinica/data=!4m2!3m1!1s0x123:0xabc?hl=pt",
            "public_data": {"phone": "+55 11 99999-0000", "website_status": "not_listed",
                            "criterion_status": "verified", "website_evidence": "No website listed on public Maps detail"},
            **overrides}


def run(connection, org, job, rows):
    return asyncio.run(sync_hunter_results(connection, org, job, rows))


def test_new_discovery_creates_real_consumer_and_pipeline_without_fake_conversation():
    conn, org, job, row = MemoryConnection(), uuid4(), search(), result()
    assert run(conn, org, job, [row]) == {"created": 1, "existing": 0, "skipped": 0}
    consumer = next(iter(conn.consumers.values()))
    assert consumer["consent_status"] == "unknown"
    assert consumer["instagram_username"] is None
    assert consumer["attributes"]["hunter"]["phone"] == "+55 11 99999-0000"
    assert "whatsapp_url" not in consumer["attributes"]["hunter"]
    assert row["public_data"]["crm_status"] == "synced"
    assert row["public_data"]["lead_id"] == str(consumer["id"])
    assert all("messages" not in sql and "conversation_threads" not in sql for sql in conn.statements)


def test_repeated_search_deduplicates_maps_identity_and_preserves_manual_crm_state():
    conn, org, first = MemoryConnection(), uuid4(), result()
    run(conn, org, search(), [first])
    consumer = next(iter(conn.consumers.values()))
    consumer["display_name"] = "Nome editado pelo cliente"
    consumer["attributes"]["notes"] = "Não sobrescrever"
    consumer["consent_status"] = "granted"
    entry = next(iter(conn.entries.values()))
    entry.update(stage="opportunity", version=9, next_action="Reunião amanhã", owner_membership_id=str(uuid4()))
    before = deepcopy(entry)
    second = result(url="https://google.com/maps/place/Nome-Novo/data=!4m2!3m1!1s0x123:0xabc?entry=ttu&hl=en")
    assert run(conn, org, search(), [second]) == {"created": 0, "existing": 1, "skipped": 0}
    assert len(conn.consumers) == len(conn.entries) == 1
    assert entry == before
    assert consumer["display_name"] == "Nome editado pelo cliente"
    assert consumer["attributes"]["notes"] == "Não sobrescrever"
    assert consumer["consent_status"] == "granted"
    assert first["public_data"]["lead_id"] == second["public_data"]["lead_id"]


def test_same_identity_in_two_tenants_is_two_distinct_consumers():
    conn, org_a, org_b, job = MemoryConnection(), uuid4(), uuid4(), search()
    a, b = result(), result()
    run(conn, org_a, job, [a])
    run(conn, org_b, job, [b])
    assert len(conn.consumers) == len(conn.entries) == 2
    assert a["public_data"]["lead_id"] != b["public_data"]["lead_id"]
    assert {key[0] for key in conn.result_updates} == {org_a, org_b}


@pytest.mark.parametrize("field,value", [("lifecycle_status", "blocked"), ("lifecycle_status", "deleted"),
                                         ("consent_status", "revoked"), ("consent_status", "opted_out")])
def test_restricted_contact_is_never_reactivated_or_reimported(field, value):
    conn, org = MemoryConnection(), uuid4()
    run(conn, org, search(), [result()])
    consumer = next(iter(conn.consumers.values()))
    consumer[field] = value
    before = deepcopy(consumer)
    conn.entries.clear()
    row = result()
    assert run(conn, org, search(), [row]) == {"created": 0, "existing": 0, "skipped": 1}
    assert not conn.entries and consumer == before
    assert row["public_data"]["crm_skip_reason"] == "contact_restricted"
    assert "lead_id" not in row["public_data"]


@pytest.mark.parametrize("mode,status", [("focused", "not_verified"), ("focused", None),
                                       ("broad", "unverified"), ("broad", "not_verified"), ("broad", "rejected")])
def test_unverified_or_rejected_criteria_are_visible_but_not_imported(mode, status):
    conn, org = MemoryConnection(), uuid4()
    row = result(public_data={"criterion_status": status})
    assert run(conn, org, search(research_mode=mode, objective="com estacionamento"), [row])["skipped"] == 1
    assert not conn.consumers and not conn.entries
    assert row["public_data"]["crm_status"] == "skipped"


def test_observed_whatsapp_link_is_preserved_but_phone_is_not_converted():
    conn, org = MemoryConnection(), uuid4()
    row = result(public_data={"whatsapp_url": "https://wa.me/5511999990000", "phone": "+55 11 99999-0000"})
    run(conn, org, search(), [row])
    assert next(iter(conn.consumers.values()))["attributes"]["hunter"]["whatsapp_url"] == "https://wa.me/5511999990000"


def test_rediscovery_does_not_erase_prior_observed_contact_details():
    conn, org = MemoryConnection(), uuid4()
    first = result(public_data={"whatsapp_url": "https://wa.me/5511999990000", "phone": "+55 11 99999-0000",
                                "criterion_status": "verified"})
    run(conn, org, search(), [first])
    run(conn, org, search(), [result(public_data={"criterion_status": "not_requested"})])
    metadata = next(iter(conn.consumers.values()))["attributes"]["hunter"]
    assert metadata["phone"] == "+55 11 99999-0000"
    assert metadata["whatsapp_url"] == "https://wa.me/5511999990000"
    assert metadata["criterion_status"] == "not_requested"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://user:secret@example.com", "https://example.com:invalid/", ""])
def test_invalid_identity_url_does_not_create_a_contact(url):
    conn = MemoryConnection()
    assert run(conn, uuid4(), search(), [result(url=url)])["skipped"] == 1
    assert not conn.consumers


def test_canonical_url_removes_tracking_not_entity_paths():
    a = identity_keys(result(source="web", url="http://www.example.com/professional/1/?utm_source=test#about"))
    b = identity_keys(result(source="web", url="https://example.com/professional/1"))
    c = identity_keys(result(source="web", url="https://example.com/professional/2"))
    assert a == b and a != c


def test_instagram_profile_identity_is_real_but_post_is_not_a_username():
    assert "instagram:clinica.teste" in identity_keys(result(source="instagram", url="https://instagram.com/Clinica.Teste/"))
    assert not any(key.startswith("instagram:") for key in identity_keys(result(source="instagram", url="https://instagram.com/p/123/")))


@pytest.mark.parametrize("mismatch", ["search_tenant", "result_tenant", "search_id"])
def test_mismatched_tenant_or_search_fails_before_any_database_action(mismatch):
    conn, org, job, row = MemoryConnection(), uuid4(), search(), result()
    if mismatch == "search_tenant":
        job["organization_id"] = uuid4()
    elif mismatch == "result_tenant":
        row["organization_id"] = uuid4()
    else:
        row["search_id"] = uuid4()
    with pytest.raises(ValueError, match="mismatch"):
        run(conn, org, job, [row])
    assert not conn.statements


def test_pipeline_serializes_real_contact_fields_without_fabricated_instagram():
    repo = PostgresRepository("postgresql://localhost/unused")
    row = {"id": uuid4(), "consumer_id": uuid4(), "display_name": "Clínica teste", "instagram_username": None,
           "stage": "new", "next_action": None, "version": 1, "updated_at": datetime.now(UTC),
           "attributes": {"private_notes": "Never expose", "hunter": {"phone": "+5511999990000",
               "source": "google_maps", "source_url": "https://google.com/maps/place/test", "website_status": "not_listed"}}}
    response = repo._pipeline(row)
    assert response["consumer"]["instagram_username"] is None
    assert response["consumer"]["phone"] == "+5511999990000"
    assert response["consumer"]["website_status"] == "not_listed"
    assert "whatsapp_url" not in response["consumer"]
    assert "attributes" not in response and "private_notes" not in json.dumps(response)


def test_postgres_local_transaction_rolls_back_sync_and_preserves_stage():
    url = os.getenv("KIARA_TEST_POSTGRES_URL", "")
    if not url:
        pytest.skip("Set KIARA_TEST_POSTGRES_URL to a local database with Kiara migrations to run real SQL")
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("This rollback fixture is restricted to a local test database; never production")

    async def exercise():
        import psycopg
        from psycopg.rows import dict_row
        org, actor, job, row = uuid4(), uuid4(), search(), result()
        async with await psycopg.AsyncConnection.connect(url, row_factory=dict_row) as conn:
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.organization_id',%s,true)", (str(org),))
                await conn.execute("INSERT INTO organizations (id,slug,name) VALUES (%s,%s,'CRM rollback test')", (org, f"crm-test-{org}"))
                await conn.execute("INSERT INTO users (id,identity_provider,external_subject) VALUES (%s,'test',%s)", (actor, str(actor)))
                await conn.execute("""INSERT INTO hunter_searches
                    (organization_id,id,requested_by,market,query,sources,result_limit)
                    VALUES (%s,%s,%s,'b2b','rollback test',ARRAY['google_maps'],1)""", (org, job["id"], actor))
                await conn.execute("""INSERT INTO hunter_results
                    (organization_id,id,search_id,source,title,url,public_data)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)""", (org, row["id"], job["id"], row["source"], row["title"], row["url"], json.dumps(row["public_data"])))
                assert (await sync_hunter_results(conn, org, job, [row]))["created"] == 1
                await conn.execute("UPDATE pipeline_entries SET stage='opportunity',version=7 WHERE organization_id=%s", (org,))
                assert (await sync_hunter_results(conn, org, job, [row]))["existing"] == 1
                entry = await (await conn.execute("SELECT stage,version FROM pipeline_entries WHERE organization_id=%s", (org,))).fetchone()
                assert entry == {"stage": "opportunity", "version": 7}
                raise psycopg.Rollback()
            remaining = await (await conn.execute("SELECT count(*) n FROM organizations WHERE id=%s", (org,))).fetchone()
            assert remaining["n"] == 0

    asyncio.run(exercise())
