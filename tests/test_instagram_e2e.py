"""Release-gate tests for the Instagram B2C pilot.

These tests use the real flow and SQLite stores.  Only the Meta HTTP boundary is
replaced, so this module can never deliver a real Instagram message.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.automation.instagram_governance import InstagramDMGovernance
from app.consumers import ConsumerStore, InstagramB2CFlow
from app.consumers.instagram_pilot import InstagramPilotService
from app.integrations.instagram import InstagramApiError, InstagramMessagingClient

APP_SECRET = "e2e-secret-not-a-real-secret"


@dataclass(frozen=True)
class StubResponse:
    status: int
    body: dict


class ClosedMetaTransport:
    """In-memory test double that permits no socket or external HTTP client."""

    def __init__(self, responses: list[StubResponse] | None = None) -> None:
        self.responses = list(responses or [StubResponse(200, {"message_id": "mock-mid-1"})])
        self.calls: list[dict] = []

    async def request(self, method, url, *, token, payload=None, idempotency_key=None):
        assert method == "POST"
        assert url == "https://graph.instagram.com/v25.0/business-e2e/messages"
        assert token == "mock-access-token"
        self.calls.append({"payload": payload, "idempotency_key": idempotency_key})
        response = self.responses.pop(0)
        return response


def signed_dm(*, event_id: str, sender: str = "ig-person-42", text: str) -> tuple[bytes, str]:
    body = json.dumps(
        {
            "object": "instagram",
            "entry": [
                {
                    "id": "business-e2e",
                    "messaging": [
                        {
                            "sender": {"id": sender},
                            "recipient": {"id": "business-e2e"},
                            "timestamp": 1_788_500_000_000,
                            "message": {"mid": event_id, "text": text},
                        }
                    ],
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, f"sha256={signature}"


def build_service(tmp_path, transport, *, governance=None, store=None):
    store = store or ConsumerStore(tmp_path / "consumers.db")
    governance = governance or InstagramDMGovernance(tmp_path / "governance.db")
    service = InstagramPilotService(
        app_secret=APP_SECRET,
        flow=InstagramB2CFlow(store, draft_builder=lambda room, _message: (
            f"Olá, {room.display_name}. Posso entender melhor o que você procura?"
        )),
        governance=governance,
        messaging=InstagramMessagingClient(
            transport,
            access_token="mock-access-token",
            api_version="v25.0",
            account_id="business-e2e",
        ),
    )
    return service, store, governance


@pytest.mark.asyncio
async def test_webhook_persistence_qualification_draft_approval_and_mock_send(tmp_path):
    transport = ClosedMetaTransport()
    service, store, governance = build_service(tmp_path, transport)
    body, signature = signed_dm(event_id="evt-full-story", text="Oi, qual o preço?")

    item = service.receive(body, signature)[0]

    assert item.outcome == "pending_approval"
    assert item.result is not None and item.result.draft is not None
    assert item.result.room.qualification.status.value == "research"
    assert store.get_person(item.result.person_id) is not None
    assert store.touchpoints(item.result.person_id)[0].content == "Oi, qual o preço?"
    assert governance.get(item.action_id or "").status == "pending_approval"
    assert transport.calls == []

    # Human approval alone is insufficient while the kill switch is off.
    assert await service.approve_and_send(item.action_id or "", actor="operadora-ana") == "blocked"
    assert transport.calls == []

    # A fresh event is explicitly approved after the operator enables delivery.
    governance.set_enabled(True, actor="operadora-ana")
    body, signature = signed_dm(event_id="evt-full-story-2", text="Quero conhecer o plano")
    approved = service.receive(body, signature)[0]
    sent_id = await service.approve_and_send(approved.action_id or "", actor="operadora-ana")

    assert sent_id == "mock-mid-1"
    assert governance.get(approved.action_id or "").status == "sent"
    assert transport.calls == [{
        "payload": {
            "recipient": {"id": "ig-person-42"},
            "message": {"text": approved.result.draft.content},
        },
        "idempotency_key": None,
    }]


@pytest.mark.asyncio
async def test_restart_loses_recipient_mapping_and_fails_closed_without_http(tmp_path):
    transport = ClosedMetaTransport()
    first, store, governance = build_service(tmp_path, transport)
    governance.set_enabled(True, actor="operadora-ana")
    body, signature = signed_dm(event_id="evt-restart", text="Quero comprar")
    action_id = first.receive(body, signature)[0].action_id or ""

    # Simulate process restart against the persisted stores. Recipient IDs are
    # deliberately not restored, preventing an accidental delivery.
    restarted, _, _ = build_service(tmp_path, transport, governance=governance, store=store)
    outcome = await restarted.approve_and_send(action_id, actor="operadora-ana")

    assert outcome == "recipient_unavailable"
    assert governance.get(action_id).status == "failed"
    assert transport.calls == []


@pytest.mark.parametrize("status", [429, 500, 503])
@pytest.mark.asyncio
async def test_retryable_meta_failures_are_persisted_for_bounded_retry(tmp_path, status):
    response = StubResponse(status, {"error": {"message": "temporary", "code": 2}})
    transport = ClosedMetaTransport([response])
    service, _, governance = build_service(tmp_path, transport)
    governance.set_enabled(True, actor="operadora-ana")
    body, signature = signed_dm(event_id=f"evt-http-{status}", text="Tenho interesse")
    action_id = service.receive(body, signature)[0].action_id or ""

    with pytest.raises(InstagramApiError) as raised:
        await service.approve_and_send(action_id, actor="operadora-ana")

    action = governance.get(action_id)
    assert raised.value.http_status == status
    assert raised.value.retryable is True
    assert action.status == "retry_wait"
    assert action.attempts == 1
    assert datetime.fromisoformat(action.next_attempt_at or "") > datetime.now(UTC)
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_opt_out_after_draft_suppresses_pending_delivery_and_any_http(tmp_path):
    transport = ClosedMetaTransport()
    service, _, governance = build_service(tmp_path, transport)
    governance.set_enabled(True, actor="operadora-ana")
    body, signature = signed_dm(event_id="evt-before-optout", text="Pode me passar detalhes?")
    pending = service.receive(body, signature)[0]

    stop_body, stop_signature = signed_dm(event_id="evt-optout", text="parar")
    stopped = service.receive(stop_body, stop_signature)[0]
    outcome = await service.approve_and_send(pending.action_id or "", actor="operadora-ana")

    assert stopped.outcome == "opt_out"
    assert stopped.action_id is None
    assert outcome == "blocked"
    assert governance.get(pending.action_id or "").status == "cancelled_opt_out"
    assert transport.calls == []


def test_invalid_signature_persists_nothing_and_never_reaches_transport(tmp_path):
    transport = ClosedMetaTransport()
    service, store, _ = build_service(tmp_path, transport)
    body, _ = signed_dm(event_id="evt-forged", text="Olá")

    with pytest.raises(ValueError, match="Assinatura"):
        service.receive(body, "sha256=forged")

    assert store.list_people() == []
    assert transport.calls == []
    with sqlite3.connect(tmp_path / "governance.db") as db:
        assert db.execute("SELECT COUNT(*) FROM instagram_inbound_events").fetchone()[0] == 0
