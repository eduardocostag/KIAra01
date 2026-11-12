from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError
from kiara_api.whatsapp_web import (
    AnalysisCompletion,
    AnalysisRequest,
    EventBatch,
    WhatsAppConfig,
    WhatsAppWebRepository,
    create_whatsapp_web_router,
)
from pydantic import ValidationError


def batch(event_id="one", kind="heartbeat"):
    return EventBatch(events=[{"id": event_id, "kind": kind, "occurred_at": datetime.now(UTC), "text": "hello"}])


@pytest.mark.asyncio
async def test_isolation_idempotency_and_heartbeat():
    repo = WhatsAppWebRepository()
    assert (await repo.config("a"))["enabled"] is False
    await repo.save_config("a", WhatsAppConfig(
        enabled=True,
        pilot_consent_confirmed=True,
        ai_context="Empresa de teste; informações autorizadas.",
        contacts=[{"phone": "5511999999999", "name": "Teste", "enabled": True}],
    ))
    assert (await repo.config("b"))["enabled"] is False
    assert await repo.ingest("a", batch()) == {"accepted": 1, "duplicates": 0}
    assert await repo.ingest("a", batch()) == {"accepted": 0, "duplicates": 1}
    assert (await repo.history("a"))["online"] is True
    assert (await repo.history("b"))["items"] == []
    assert (await repo.ingest("b", batch()))["accepted"] == 1
    repo.events["a"]["one"]["received_at"] = (datetime.now(UTC) - timedelta(minutes=3)).isoformat()
    assert (await repo.history("a"))["online"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_config_removal_disables_stale_thread_automation_for_same_tenant(enabled):
    """Exercise allowlist reconciliation at the SQL boundary, without a live DB."""
    organization, other_organization = uuid4(), uuid4()
    threads = [
        {"organization": organization, "phone": "5511999999999", "channel": "whatsapp", "automation": True, "handoff": False, "status": "open"},
        {"organization": organization, "phone": "5511888888888", "channel": "whatsapp", "automation": True, "handoff": False, "status": "open"},
        {"organization": organization, "phone": "5511777777777", "channel": "instagram", "automation": True, "handoff": False, "status": "open"},
        {"organization": other_organization, "phone": "5511888888888", "channel": "whatsapp", "automation": True, "handoff": False, "status": "open"},
    ]

    class Connection:
        async def execute(self, sql, params):
            if sql.startswith("INSERT INTO whatsapp_web_config"):
                return
            if "SET automation_enabled=false" in sql:
                assert "organization_id=%s" in sql and "channel='whatsapp'" in sql
                for thread in threads:
                    if thread["organization"] == params[0] and thread["channel"] == "whatsapp":
                        thread["automation"] = False
            else:
                automation, handoff, org, phone = params
                for thread in threads:
                    if thread["organization"] == org and thread["channel"] == "whatsapp" and thread["phone"] == phone and thread["status"] != "blocked":
                        thread.update(automation=automation, handoff=handoff)

    @asynccontextmanager
    async def transaction(org):
        assert str(org) == str(organization)
        yield Connection()

    repository = WhatsAppWebRepository(SimpleNamespace(_transaction=transaction))
    config = WhatsAppConfig(
        enabled=enabled, pilot_consent_confirmed=True, ai_context="Empresa de teste.",
        contacts=[{"phone": "5511999999999", "enabled": True}] if enabled else [],
    )
    await repository.save_config(str(organization), config)
    assert threads[0]["automation"] is enabled
    assert threads[1]["automation"] is False  # Removed from the authorization list.
    assert threads[2]["automation"] is True  # Another channel is unaffected.
    assert threads[3]["automation"] is True  # Another tenant is unaffected.


@pytest.mark.parametrize("payload", [
    {"contacts": [{"phone": "bad"}]},
    {"contact_start": "23:00", "contact_end": "09:00"},
    {"contacts": [{"phone": "5511999999999"}, {"phone": "5511999999999"}]},
    {"organization_id": "injected"}, {"followup_hours": 0},
    {"contacts": [{"phone": "5511999999999", "enabled": True}, {"phone": "5511888888888", "enabled": True}]},
    {"enabled": True, "contacts": [{"phone": "5511999999999"}]},
    {"enabled": True, "pilot_consent_confirmed": True},
    {"enabled": True, "pilot_consent_confirmed": True, "ai_context": "   ",
     "contacts": [{"phone": "5511999999999", "enabled": True}]},
])
def test_config_rejects_invalid_settings(payload):
    with pytest.raises(ValidationError):
        WhatsAppConfig(**payload)


def test_events_require_timezone_and_bounded_batches():
    with pytest.raises(ValidationError):
        naive_timestamp = datetime.now(UTC).replace(tzinfo=None)
        EventBatch(events=[{"id": "a", "kind": "outbound", "occurred_at": naive_timestamp}])
    with pytest.raises(ValidationError):
        EventBatch(events=[])


def test_routes_require_auth_context_and_forbid_viewer_writes():
    app = FastAPI()
    app.include_router(create_whatsapp_web_router(WhatsAppWebRepository()))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "a", "m", "viewer", "req")
    client = TestClient(app)
    assert client.get("/v1/whatsapp-web/config").json()["enabled"] is False
    with pytest.raises(ApiError) as exc:
        client.put("/v1/whatsapp-web/config", json={
            "enabled": True,
            "pilot_consent_confirmed": True,
            "ai_context": "Empresa de teste; informações autorizadas.",
            "contacts": [{"phone": "5511999999999", "name": "Teste", "enabled": True}],
        })
    assert exc.value.status_code == 403
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "a", "m", "owner", "req")
    assert client.put("/v1/whatsapp-web/config", json={"enabled": True}).status_code == 422
    assert client.put("/v1/whatsapp-web/config", json={
        "enabled": True,
        "pilot_consent_confirmed": True,
        "ai_context": "Empresa de teste; informações autorizadas.",
        "contacts": [{"phone": "5511999999999", "name": "Teste", "enabled": True}],
    }).status_code == 200
    assert client.post("/v1/whatsapp-web/events", json=batch().model_dump(mode="json")).json()["accepted"] == 1
    assert client.get("/v1/whatsapp-web/events").json()["online"] is True


def test_analysis_job_is_operator_scoped_and_idempotently_imports_results():
    app = FastAPI()
    repository = WhatsAppWebRepository()
    app.include_router(create_whatsapp_web_router(repository))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "a", "m", "viewer", "req")
    client = TestClient(app)
    with pytest.raises(ApiError) as exc:
        client.post("/v1/whatsapp-web/analysis", json={"limit": 30})
    assert exc.value.status_code == 403

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "a", "m", "operator", "req")
    requested = client.post("/v1/whatsapp-web/analysis", json={"limit": 30})
    assert requested.status_code == 200
    job_id = requested.json()["id"]
    assert client.get("/v1/whatsapp-web/analysis/next").json()["id"] == job_id
    payload = {
        "leads": [{
            "phone": "5511999999999", "name": "Lead analisado", "stage": "qualified",
            "summary": "Demonstrou interesse no serviço.", "next_action": "Agendar conversa", "confidence": 0.9,
        }],
        "scanned": 2, "skipped": 1,
    }
    assert client.post(f"/v1/whatsapp-web/analysis/{job_id}/complete", json=payload).json() == {
        "imported": 1, "duplicates": 0, "scanned": 2, "skipped": 1, "error": None,
    }
    assert client.get(f"/v1/whatsapp-web/analysis/{job_id}").json()["status"] == "completed"
    assert client.post(f"/v1/whatsapp-web/analysis/{job_id}/complete", json=payload).json()["imported"] == 1


def test_analysis_limits_batches_and_rejects_invalid_phone():
    with pytest.raises(ValidationError):
        AnalysisRequest(limit=31)
    with pytest.raises(ValidationError):
        AnalysisCompletion(leads=[{
            "phone": "not-a-phone", "name": "Lead", "confidence": 0.5,
        }])


def test_phone_match_keys_cover_brazilian_formats():
    from kiara_api.whatsapp_web import phone_match_keys

    assert phone_match_keys("5551999998888") == ["051999998888", "51999998888", "5551999998888"]
    assert phone_match_keys("14155550123") == ["14155550123"]


@pytest.mark.asyncio
async def test_analysis_matches_formatted_hunter_phone_and_keeps_human_stage():
    """A formatted CRM phone is the same contact; the AI stage only fills a 'new' lead."""
    organization = uuid4()
    consumer_id = uuid4()
    stored_phone = "(51) 99999-8888"
    statements = []

    class Cursor:
        def __init__(self, row):
            self.row = row

        async def fetchone(self):
            return self.row

    class Connection:
        async def execute(self, sql, params=()):
            statements.append(sql)
            if "FROM whatsapp_web_analysis_jobs" in sql and "FOR UPDATE" in sql:
                return Cursor({"status": "running"})
            if sql.lstrip().startswith("SELECT id FROM consumers"):
                digits = "".join(character for character in stored_phone if character.isdigit())
                assert "regexp_replace" in sql
                return Cursor({"id": consumer_id} if digits in params[1] else None)
            return Cursor(None)

    @asynccontextmanager
    async def transaction(org):
        yield Connection()

    repository = WhatsAppWebRepository(SimpleNamespace(_transaction=transaction))
    result = await repository.complete_analysis(str(organization), "job-1", AnalysisCompletion(
        leads=[{"phone": "5551999998888", "name": "Cliente", "stage": "qualified", "confidence": 0.9}],
        scanned=1,
    ))

    assert result["imported"] == 0 and result["duplicates"] == 1
    assert not any(sql.lstrip().startswith("INSERT INTO consumers") for sql in statements)
    update = next(sql for sql in statements if "UPDATE pipeline_entries" in sql)
    assert "CASE WHEN stage='new' THEN %s ELSE stage END" in update
    assert "COALESCE(NULLIF(next_action,''),%s)" in update
