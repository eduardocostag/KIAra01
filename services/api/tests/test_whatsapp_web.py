from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from kiara_api.whatsapp_web import (
    AnalysisCompletion,
    AnalysisRequest,
    EventBatch,
    WhatsAppConfig,
    WhatsAppWebRepository,
    create_whatsapp_web_router,
)
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError


def batch(event_id="one", kind="heartbeat"):
    return EventBatch(events=[dict(id=event_id, kind=kind, occurred_at=datetime.now(UTC), text="hello")])


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
        EventBatch(events=[dict(id="a", kind="outbound", occurred_at=datetime.now())])
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
