from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.automation.instagram_governance import InstagramDMGovernance
from app.consumers import ConsumerStore, InstagramB2CFlow
from app.consumers.instagram_pilot import InstagramPilotService
from app.integrations.instagram import InstagramContractError, InstagramMessagingClient


class Response:
    def __init__(self):
        self.status = 200
        self.body = {"message_id": "sent-1"}


class Http:
    def __init__(self):
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return Response()


def _signed_event(secret: str, *, text: str = "Qual o preço?") -> tuple[bytes, str]:
    body = json.dumps({
        "object": "instagram",
        "entry": [{
            "id": "business-1",
            "messaging": [{
                "sender": {"id": "person-1"},
                "recipient": {"id": "business-1"},
                "timestamp": 1_788_500_000_000,
                "message": {"mid": "event-1", "text": text},
            }],
        }],
    }).encode()
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, f"sha256={digest}"


@pytest.mark.asyncio
async def test_inbound_qualifies_drafts_and_only_sends_after_named_approval(tmp_path):
    secret = "test-secret"
    store = ConsumerStore(tmp_path / "consumers.db")
    governance = InstagramDMGovernance(tmp_path / "governance.db")
    http = Http()
    service = InstagramPilotService(
        app_secret=secret,
        flow=InstagramB2CFlow(store),
        governance=governance,
        messaging=InstagramMessagingClient(
            http, access_token="test-token", api_version="v25.0", account_id="business-1"
        ),
    )
    body, signature = _signed_event(secret)

    item = service.receive(body, signature)[0]
    assert item.outcome == "pending_approval"
    assert item.result is not None and item.result.draft is not None
    assert item.result.room.qualification.status.value == "research"
    assert http.calls == []
    assert await service.approve_and_send(item.action_id or "", actor="operador") == "blocked"
    assert http.calls == []

    governance.set_enabled(True, actor="operador")
    second_body = body.replace(b"event-1", b"event-2")
    second_signature = "sha256=" + hmac.new(
        secret.encode(), second_body, hashlib.sha256
    ).hexdigest()
    second = service.receive(second_body, second_signature)[0]
    assert await service.approve_and_send(second.action_id or "", actor="operador") == "sent-1"
    assert len(http.calls) == 1
    assert governance.get(second.action_id or "").status == "sent"


def test_opt_out_is_persisted_and_never_creates_draft(tmp_path):
    secret = "test-secret"
    store = ConsumerStore(tmp_path / "consumers.db")
    governance = InstagramDMGovernance(tmp_path / "governance.db")
    service = InstagramPilotService(
        app_secret=secret,
        flow=InstagramB2CFlow(store),
        governance=governance,
        messaging=InstagramMessagingClient(
            Http(), access_token="token", api_version="v25.0", account_id="business-1"
        ),
    )
    body, signature = _signed_event(secret, text="parar")

    item = service.receive(body, signature)[0]

    assert item.outcome == "opt_out"
    assert item.action_id is None
    assert item.result is None


def test_wrong_account_is_rejected_before_persistence(tmp_path):
    secret = "test-secret"
    governance = InstagramDMGovernance(tmp_path / "governance.db")
    service = InstagramPilotService(
        app_secret=secret,
        flow=InstagramB2CFlow(ConsumerStore(tmp_path / "consumers.db")),
        governance=governance,
        messaging=InstagramMessagingClient(
            Http(), access_token="token", api_version="v25.0", account_id="other-business"
        ),
    )
    body, signature = _signed_event(secret)
    item = service.receive(body, signature)[0]
    assert item.outcome == "wrong_account"
    assert governance.action_for_event("business-1:event-1") is None


def test_replayed_webhook_does_not_repeat_qualification(tmp_path):
    secret = "test-secret"
    calls = 0

    def build_draft(room, message):
        nonlocal calls
        calls += 1
        return "Resposta segura"

    governance = InstagramDMGovernance(tmp_path / "governance.db")
    service = InstagramPilotService(
        app_secret=secret,
        flow=InstagramB2CFlow(
            ConsumerStore(tmp_path / "consumers.db"), draft_builder=build_draft
        ),
        governance=governance,
        messaging=InstagramMessagingClient(
            Http(), access_token="token", api_version="v25.0", account_id="business-1"
        ),
    )
    body, signature = _signed_event(secret)
    first = service.receive(body, signature)[0]
    second = service.receive(body, signature)[0]
    assert first.event_id == "business-1:event-1"
    assert second.outcome == "duplicate"
    assert second.action_id == first.action_id
    assert calls == 1


def test_malformed_json_and_echo_fail_without_pipeline_side_effects(tmp_path):
    secret = "test-secret"
    store = ConsumerStore(tmp_path / "consumers.db")
    governance = InstagramDMGovernance(tmp_path / "governance.db")
    service = InstagramPilotService(
        app_secret=secret, flow=InstagramB2CFlow(store), governance=governance,
        messaging=InstagramMessagingClient(
            Http(), access_token="token", api_version="v25.0", account_id="business-1"
        ),
    )
    malformed = b"{"
    signature = "sha256=" + hmac.new(secret.encode(), malformed, hashlib.sha256).hexdigest()
    with pytest.raises(InstagramContractError):
        service.receive(malformed, signature)

    body, _ = _signed_event(secret)
    payload = json.loads(body)
    payload["entry"][0]["messaging"][0]["message"]["is_echo"] = True
    echo = json.dumps(payload).encode()
    echo_signature = "sha256=" + hmac.new(secret.encode(), echo, hashlib.sha256).hexdigest()
    assert service.receive(echo, echo_signature)[0].outcome == "ignored"
    assert store.list_people() == []


def test_webhook_redelivery_does_not_repeat_consumer_side_effects(tmp_path):
    secret = "test-secret"
    store = ConsumerStore(tmp_path / "consumers.db")
    governance = InstagramDMGovernance(tmp_path / "governance.db")
    service = InstagramPilotService(
        app_secret=secret, flow=InstagramB2CFlow(store), governance=governance,
        messaging=InstagramMessagingClient(
            Http(), access_token="token", api_version="v25.0", account_id="business-1"
        ),
    )
    body, signature = _signed_event(secret)
    first = service.receive(body, signature)[0]
    duplicate = service.receive(body, signature)[0]
    assert duplicate.outcome == "duplicate"
    assert duplicate.action_id == first.action_id
    person = store.list_people()[0]
    assert len(store.touchpoints(person.id)) == 1


@pytest.mark.asyncio
async def test_approved_action_can_resume_after_kill_switch_and_retry_wait(tmp_path):
    secret = "test-secret"
    store = ConsumerStore(tmp_path / "consumers.db")
    governance = InstagramDMGovernance(tmp_path / "governance.db")
    http = Http()
    service = InstagramPilotService(
        app_secret=secret, flow=InstagramB2CFlow(store), governance=governance,
        messaging=InstagramMessagingClient(
            http, access_token="token", api_version="v25.0", account_id="business-1"
        ),
    )
    body, signature = _signed_event(secret)
    item = service.receive(body, signature)[0]
    action_id = item.action_id or ""
    assert await service.approve_and_send(action_id, actor="operador") == "blocked"
    governance.set_enabled(True, actor="operador")
    assert await service.approve_and_send(action_id, actor="operador") == "sent-1"
