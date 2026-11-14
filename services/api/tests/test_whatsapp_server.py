import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api import whatsapp_server
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError

from app.integrations.openwa import OpenWAError


class FakeOpenWA:
    def __init__(self, status="ready", fail=False):
        self.session = {"id": "s-1", "name": "kiara", "status": status, "phone": "5511999990000", "connectedAt": "2026-01-01T00:00:00Z"}
        self.fail = fail
        self.started = False
        self.presence = []
        self.history_reads = []

    async def _request(self, method, path, payload=None, idempotency_key=None):
        assert method == "PUT" and path.endswith("/presence")
        self.presence.append(payload)
        return {"success": True}

    async def find_session(self, name):
        if self.fail:
            raise OpenWAError("down")
        return self.session if self.session["status"] != "absent" else None

    async def create_session(self, name):
        self.session = {"id": "s-1", "name": name, "status": "created"}
        return self.session

    async def start_session(self, identifier):
        self.started = True
        self.session = {**self.session, "status": "qr_ready"}
        return self.session

    async def qr_code(self, identifier):
        return {"qrCode": "data:image/png;base64,AAAA", "status": "qr_ready"}

    async def list_chats(self, identifier, limit=200):
        return [
            {"id": "5511911112222@c.us", "name": "Maria", "timestamp": 200},
            {"id": "5511933334444@c.us", "name": "João", "timestamp": 300},
            {"id": "120363@g.us", "name": "Grupo", "isGroup": True},
            {"id": "99887766554433@lid", "name": "Ana (lid)", "timestamp": 400},
            {"id": "11223344556677@lid", "name": "Sem número", "timestamp": 100},
            {"id": "status@broadcast"},
        ]

    async def phone_for(self, identifier, chat_id):
        return {"5511911112222@c.us": "5511911112222", "5511933334444@c.us": "5511933334444",
                "99887766554433@lid": "5551988887777"}.get(chat_id, "")

    async def live_history(self, identifier, chat_id, limit=40):
        self.history_reads.append(chat_id)
        return [
            {"id": f"{chat_id}-2", "fromMe": True, "body": "Claro, envio o orçamento.", "timestamp": 1_700_000_100, "chatId": chat_id},
            {"id": f"{chat_id}-1", "fromMe": False, "body": "Oi, quanto custa?", "timestamp": 1_700_000_000, "chatId": chat_id},
            {"id": f"{chat_id}-3", "fromMe": False, "body": "", "type": "image", "timestamp": 1_700_000_200_000, "chatId": chat_id},
            {"id": f"{chat_id}-s", "fromMe": False, "body": "story", "isStatusBroadcast": True, "timestamp": 1_700_000_300, "chatId": chat_id},
        ]


class FakePostgres:
    @asynccontextmanager
    async def _transaction(self, organization_id):
        yield "connection"


def build(monkeypatch, client, *, role="owner"):
    ingested = []

    async def fake_ingest(connection, organization_id, **message):
        ingested.append(message)
        return {"inserted": True}

    monkeypatch.setattr("kiara_api.unified_inbox.ingest_message", fake_ingest)
    last_seen = {}

    async def fake_last(connection, organization_id, phone):
        return last_seen.get(phone)

    monkeypatch.setattr(whatsapp_server, "last_message_at", fake_last)
    known = {}
    remembered = []

    async def fake_known(connection, organization_id):
        return known

    async def fake_remember(connection, organization_id, phone, chat_id):
        remembered.append((phone, chat_id))

    monkeypatch.setattr(whatsapp_server, "known_chats", fake_known)
    monkeypatch.setattr(whatsapp_server, "remember_chat", fake_remember)
    monkeypatch.setattr(whatsapp_server, "_quiet_presence", {})
    monkeypatch.setattr(whatsapp_server, "SYNC_PAUSE_SECONDS", (0, 0))
    ingested_last = last_seen  # tests can mark a contact as already synced
    app = FastAPI()
    app.include_router(whatsapp_server.create_whatsapp_server_router(
        whatsapp_server.WhatsAppServerService(FakePostgres(), client_factory=lambda: client)))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status_code)

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", role, "req", email="admin@kiara.local")
    api = TestClient(app)
    api.last_seen = ingested_last
    api.known = known
    api.remembered = remembered
    return api, ingested


def test_sync_imports_recent_one_to_one_chats_only(monkeypatch):
    api, ingested = build(monkeypatch, FakeOpenWA())
    response = api.post("/v1/whatsapp-server/sync")
    assert response.status_code == 200
    body = response.json()
    # @lid contacts are resolved to their phone; one without a resolvable phone, a group and a broadcast are skipped.
    assert body["connected"] is True and body["conversations"] == 3 and body["messages"] == 9 and body["skipped"] == 3
    assert "5511999990000" not in response.text  # phone is masked
    # Newest chat first, messages oldest first, media labelled, status posts dropped, names kept.
    assert [item["identity"] for item in ingested[:3]] == ["5551988887777"] * 3
    assert [item["text"] for item in ingested[:3]] == ["Oi, quanto custa?", "Claro, envio o orçamento.", "[imagem]"]
    assert [item["direction"] for item in ingested[:3]] == ["inbound", "outbound", "inbound"]
    assert ingested[0]["name"] == "Ana (lid)" and all(item["channel"] == "whatsapp" for item in ingested)


def test_second_sync_only_writes_new_messages(monkeypatch):
    from datetime import UTC, datetime
    api, ingested = build(monkeypatch, FakeOpenWA())
    api.last_seen["5551988887777"] = datetime.fromtimestamp(1_700_000_100, UTC)
    api.post("/v1/whatsapp-server/sync")
    texts = [item["text"] for item in ingested if item["identity"] == "5551988887777"]
    assert texts == ["Claro, envio o orçamento.", "[imagem]"]  # the older inbound message is skipped


def test_unchanged_chats_are_not_read_again_and_presence_stays_offline(monkeypatch):
    from datetime import UTC, datetime
    client = FakeOpenWA()
    api, ingested = build(monkeypatch, client)
    api.post("/v1/whatsapp-server/sync")
    assert client.presence == [{"available": False}]
    assert ("5551988887777", "99887766554433@lid") in api.remembered
    # Second run: every chat is known up to its last activity -> no history reads, presence not re-sent.
    api.known.update({chat_id: datetime.fromtimestamp(1_000, UTC) for chat_id in client.history_reads})
    client.history_reads.clear()
    body = api.post("/v1/whatsapp-server/sync").json()
    assert client.history_reads == [] and body["conversations"] == 0
    assert client.presence == [{"available": False}]


def test_no_reads_while_whatsapp_web_finishes_its_first_load(monkeypatch):
    from datetime import UTC, datetime, timedelta
    client = FakeOpenWA()
    client.session["connectedAt"] = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
    api, ingested = build(monkeypatch, client)
    body = api.post("/v1/whatsapp-server/sync").json()
    assert body["warming_up"] is True and client.history_reads == [] and ingested == []


def test_sync_without_connected_session_imports_nothing(monkeypatch):
    api, ingested = build(monkeypatch, FakeOpenWA(status="qr_ready"))
    body = api.post("/v1/whatsapp-server/sync").json()
    assert body["connected"] is False and body["conversations"] == 0 and ingested == []


def test_connect_creates_session_and_returns_qr(monkeypatch):
    client = FakeOpenWA(status="absent")
    api, _ = build(monkeypatch, client)
    body = api.post("/v1/whatsapp-server/connect").json()
    assert client.started and body["state"] == "qr_ready" and body["qr"].startswith("data:image/png;base64,")
    operator, _ = build(monkeypatch, FakeOpenWA(), role="operator")
    assert operator.post("/v1/whatsapp-server/connect").status_code == 403


def test_status_failure_does_not_leak(monkeypatch):
    api, _ = build(monkeypatch, FakeOpenWA(fail=True))
    response = api.get("/v1/whatsapp-server/status")
    assert response.status_code == 503 and "down" not in response.text


def test_gateway_client_refuses_sends():
    client = whatsapp_server.GatewayOpenWAClient("https://gw.example", "t")
    try:
        asyncio.run(client.send_text("s-1", "5511999990000", "oi", idempotency_key="k"))
    except OpenWAError:
        pass
    else:
        raise AssertionError("send must be refused")
