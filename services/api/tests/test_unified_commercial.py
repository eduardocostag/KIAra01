import hashlib
import hmac
import json
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api import channel_webhooks, unified_inbox
from kiara_api.channel_webhooks import chatwoot_message, verify_chatwoot_signature
from kiara_api.commercial_qualification import qualify_messages
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError
from kiara_api.unified_inbox import (
    InboxReply,
    OutboxCompletion,
    UnifiedInboxRepository,
    create_unified_inbox_router,
)
from kiara_api.whatsapp_web import WhatsAppConfig


@pytest.mark.parametrize(("text", "temperature"), [
    ("Quero contratar, pode mandar preço e agendar hoje?", "hot"),
    ("Qual o preço do serviço?", "warm"),
    ("Olá, bom dia", "cold"),
    ("Não quero contratar e estou sem orçamento", "cold"),
    ('O anúncio dizia "quero comprar hoje"', "cold"),
    ("Não tenho interesse, pare de me enviar mensagens", "cold"),
])
def test_qualification_explains_observed_evidence_without_negated_purchase(text, temperature):
    result = qualify_messages([{"direction": "inbound", "text": text}])
    assert result["temperature"] == temperature
    assert result["reasons"]
    assert result["stage"] not in {"won", "lost"}


def test_outgoing_sales_copy_does_not_qualify_customer():
    result = qualify_messages([{"direction": "outbound", "text": "quero comprar hoje preço urgente"}])
    assert result["score"] == 0


def test_recent_purchase_refusal_overrides_old_interest_without_marking_won():
    result = qualify_messages([
        {"direction": "inbound", "text": "Quero contratar hoje, qual o preço?"},
        {"direction": "inbound", "text": "Não quero contratar, estou sem orçamento"},
    ])
    assert result["temperature"] == "cold"
    assert "recente" in result["reasons"][0]


def test_multicontact_operation_requires_explicit_mode_and_authorisation():
    contacts = [{"phone": "5511999999999"}, {"phone": "5511888888888"}]
    config = WhatsAppConfig(pilot_mode=False, enabled=True, pilot_consent_confirmed=True,
                            ai_context="Informações aprovadas da empresa", contacts=contacts)
    assert len(config.contacts) == 2
    assert config.initial_outreach_enabled is False
    with pytest.raises(ValueError):
        WhatsAppConfig(pilot_mode=True, contacts=contacts)
    with pytest.raises(ValueError):
        WhatsAppConfig(pilot_mode=False, enabled=True, contacts=contacts)


def test_chatwoot_hmac_authenticates_exact_body_and_expiry():
    raw, secret, timestamp = b'{"event":"message_created"}', "synthetic-webhook-secret", str(int(time.time()))
    signature = "sha256=" + hmac.new(secret.encode(), timestamp.encode()+b"."+raw, hashlib.sha256).hexdigest()
    verify_chatwoot_signature(raw, timestamp, signature, secret)
    with pytest.raises(ValueError):
        verify_chatwoot_signature(raw+b" ", timestamp, signature, secret)
    with pytest.raises(ValueError):
        verify_chatwoot_signature(raw, "1", signature, secret)


def test_chatwoot_private_notes_and_cross_account_never_enter_customer_inbox():
    payload = {"event": "message_created", "private": True}
    assert chatwoot_message(payload, "4") is None
    with pytest.raises(ValueError):
        chatwoot_message({"event": "message_created", "account": {"id": 5}}, "4")


class Cursor:
    def __init__(self, row=None):
        self.row = row
    async def fetchone(self):
        return self.row


class Pg:
    def __init__(self, consent="observed_inbound"):
        self.orgs, self.calls = [], []
        self.thread = {"id": uuid4(), "channel": "whatsapp", "status": "open", "consumer_id": uuid4(),
                       "provider_thread_id": "5511999999999", "consent_status": consent}
        self.outbox = None
    @asynccontextmanager
    async def _transaction(self, org):
        self.orgs.append(org)
        yield self
    async def execute(self, sql, args):
        self.calls.append((sql, args))
        if "SELECT t.*,c.consent_status" in sql:
            return Cursor(self.thread)
        if "SELECT id,status,body,thread_id" in sql:
            return Cursor(self.outbox)
        if "INSERT INTO commercial_outbox" in sql:
            self.outbox = {"id": uuid4(), "status": "queued", "phone": args[2], "body": args[3],
                           "thread_id": self.thread["id"]}
            return Cursor(self.outbox)
        if "SELECT * FROM commercial_outbox" in sql:
            return Cursor(self.outbox)
        if "SELECT config" in sql:
            return Cursor(None)
        if "UPDATE commercial_outbox SET status=%s" in sql:
            self.outbox["status"] = args[0]
        return Cursor()


@pytest.mark.asyncio
async def test_manual_reply_is_tenant_scoped_and_replayed_without_duplicate_send():
    pg = Pg()
    repo = UnifiedInboxRepository(pg)
    payload = InboxReply(text="Resposta humana", idempotency_key="same-request-key")
    first = await repo.reply("workspace-a", str(pg.thread["id"]), payload)
    second = await repo.reply("workspace-a", str(pg.thread["id"]), payload)
    assert first == second
    assert first["status"] == "queued"
    assert pg.orgs == ["workspace-a", "workspace-a"]
    assert sum("INSERT INTO commercial_outbox" in sql for sql, _ in pg.calls) == 1
    assert any("automation_enabled=%s" in sql and args[0] is False for sql, args in pg.calls)
    with pytest.raises(ApiError) as error:
        await repo.reply("workspace-a", str(pg.thread["id"]), InboxReply(text="Outro texto", idempotency_key="same-request-key"))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_optout_contact_cannot_be_recontacted():
    pg = Pg(consent="opted_out")
    with pytest.raises(ApiError) as error:
        await UnifiedInboxRepository(pg).reply("workspace-a", str(pg.thread["id"]), InboxReply(text="Olá", idempotency_key="test-request-key"))
    assert error.value.status_code == 409
    assert pg.outbox is None


@pytest.mark.asyncio
async def test_claimed_reply_without_delivery_receipt_remains_unknown(monkeypatch):
    pg = Pg()
    repo = UnifiedInboxRepository(pg)
    await repo.reply("a", str(pg.thread["id"]), InboxReply(text="Oi", idempotency_key="test-request-key"))
    pg.outbox["status"] = "sending"
    events = []
    async def ingest(*args, **kwargs):
        events.append(kwargs)
    monkeypatch.setattr(unified_inbox, "ingest_message", ingest)
    result = await repo.complete_outbound("a", str(pg.outbox["id"]), OutboxCompletion(status="sent"))
    assert result == {"status": "unknown"}
    assert events == []
    result = await repo.complete_outbound("a", str(pg.outbox["id"]), OutboxCompletion(status="sent", provider_message_id="late"))
    assert result["status"] == "unknown"


def test_unified_actions_reject_viewer_before_repository_access():
    app = FastAPI()
    app.include_router(create_unified_inbox_router(UnifiedInboxRepository(None)))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("user", "org", "member", "viewer", "request")
    @app.exception_handler(ApiError)
    async def error_handler(_request, error):
        return JSONResponse({"error": error.code}, status_code=error.status_code)
    client = TestClient(app)
    assert client.post("/v1/inbox/threads/thread/messages", json={"text": "oi", "idempotency_key": "test-request-key"}).status_code == 403
    assert client.patch("/v1/inbox/threads/thread/automation", json={"enabled": True}).status_code == 403


def test_operator_cannot_send_or_enable_bot_but_can_request_pause():
    class Repository:
        async def automation(self, organization, thread, enabled):
            assert organization == "org" and enabled is False
            return {"automation_enabled": False, "handoff": True}
    app = FastAPI()
    app.include_router(create_unified_inbox_router(Repository()))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("user", "org", "member", "operator", "request")
    @app.exception_handler(ApiError)
    async def error_handler(_request, error):
        return JSONResponse({"error": error.code}, status_code=error.status_code)
    client = TestClient(app)
    assert client.post("/v1/inbox/threads/thread/messages", json={"text": "oi", "idempotency_key": "test-request-key"}).status_code == 403
    assert client.patch("/v1/inbox/threads/thread/automation", json={"enabled": True}).status_code == 403
    assert client.patch("/v1/inbox/threads/thread/automation", json={"enabled": False}).json()["handoff"] is True
    assert client.get("/v1/whatsapp-web/outbox/next").status_code == 403


def test_read_receipt_is_explicit_authenticated_and_scoped():
    calls = []
    class Repository:
        async def mark_read(self, organization, thread):
            calls.append((organization, thread))
            return {"read": True}
    app = FastAPI()
    app.include_router(create_unified_inbox_router(Repository()))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("user", "org", "member", "viewer", "request")
    client = TestClient(app)
    assert client.post("/v1/inbox/threads/active-thread/read").json() == {"read": True}
    assert calls == [("org", "active-thread")]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_external_delivery_reserves_before_post_and_unknown_never_retries(monkeypatch, failure):
    from kiara_api import chatwoot
    pg = Pg()
    pg.thread["channel"] = "chatwoot"
    pg.thread["provider_thread_id"] = "42"
    class Integrations:
        async def credentials_for(self, organization, channel):
            assert organization == "a" and channel == "chatwoot"
            return {"account_id": "1"}
    calls = []
    class Adapter:
        async def send_message(self, identifier, text):
            assert any("SET status='sending'" in sql for sql, _ in pg.calls)
            calls.append((identifier, text))
            if failure:
                raise RuntimeError("Timeout after delivery is uncertain")
            return {"id": 123}
    monkeypatch.setattr(chatwoot, "_runtime_client", lambda credentials: Adapter())
    ingested = []
    async def ingest(*args, **kwargs):
        ingested.append(kwargs)
    monkeypatch.setattr(unified_inbox, "ingest_message", ingest)
    repo = UnifiedInboxRepository(pg, Integrations())
    payload = InboxReply(text="Resposta humana", idempotency_key="delivery-request-key")
    result = await repo.reply("a", str(pg.thread["id"]), payload)
    assert result["status"] == ("unknown" if failure else "sent")
    assert len(ingested) == (0 if failure else 1)
    replay = await repo.reply("a", str(pg.thread["id"]), payload)
    assert replay == result
    assert calls == [(42, "Resposta humana")]


def test_signed_instagram_webhook_uses_configured_account_and_dedupes_via_ingestion(monkeypatch):
    org = str(uuid4())
    credentials = {"app_secret": "synthetic-meta-secret", "instagram_account_id": "123", "verify_token": "verify"}
    async def fetch(*args):
        return credentials
    calls = []
    async def ingest(connection, organization_id, **message):
        assert organization_id == org
        key = message["external_id"]
        duplicate = any(item["external_id"] == key for item in calls)
        calls.append(message)
        return {"inserted": not duplicate}
    monkeypatch.setattr(channel_webhooks, "credentials_for_webhook", fetch)
    monkeypatch.setattr(channel_webhooks, "ingest_message", ingest)
    class Repository:
        _postgres = Pg()
    app = FastAPI()
    app.include_router(channel_webhooks.create_channel_webhook_router(Repository()))
    @app.exception_handler(ApiError)
    async def error_handler(_request, error):
        return JSONResponse({"error": error.code}, status_code=error.status_code)
    client = TestClient(app)
    payload = {"object": "instagram", "entry": [{"id": "123", "messaging": [{"sender": {"id": "456"}, "recipient": {"id": "123"}, "timestamp": int(datetime.now(UTC).timestamp()*1000), "message": {"mid": "m-1", "text": "Quero orçamento"}}]}]}
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(credentials["app_secret"].encode(), raw, hashlib.sha256).hexdigest()
    url = f"/v1/channels/instagram/{org}/webhook"
    assert client.post(url, content=raw, headers={"x-hub-signature-256": signature}).json() == {"accepted": 1}
    assert client.post(url, content=raw, headers={"x-hub-signature-256": signature}).json() == {"accepted": 0}
    assert calls[0]["identity"] == "123:456"
    assert client.post(url, content=raw+b" ", headers={"x-hub-signature-256": signature}).status_code == 401
