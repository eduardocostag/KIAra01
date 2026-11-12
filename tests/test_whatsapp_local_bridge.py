import pytest

from scripts import run_whatsapp_local_bridge as bridge


def test_bridge_masks_contact_phone():
    assert bridge.mask_phone("5511999999999@c.us") == "+55*******9999"


def test_bridge_allows_only_explicit_secure_origins(monkeypatch):
    monkeypatch.setenv(
        "KIARA_WHATSAPP_ALLOWED_ORIGINS",
        "https://kiaralead.vercel.app,http://localhost:3000,http://example.com",
    )
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "public-key")

    assert bridge.configured_origins() == frozenset({
        "https://kiaralead.vercel.app",
        "http://localhost:3000",
    })


def test_bridge_requires_a_valid_site_origin(monkeypatch):
    monkeypatch.setenv("KIARA_WHATSAPP_ALLOWED_ORIGINS", "http://example.com")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "public-key")

    with pytest.raises(RuntimeError, match="KIARA_WHATSAPP_ALLOWED_ORIGINS"):
        bridge.configured_origins()


def test_bridge_requires_one_valid_configured_phone(monkeypatch):
    monkeypatch.setenv("KIARA_WHATSAPP_ANALYSIS_PHONE", "+55 (11) 99999-9999")
    assert bridge._configured_phone() == "5511999999999@c.us"

    monkeypatch.setenv("KIARA_WHATSAPP_ANALYSIS_PHONE", "5511999999999@lid")
    with pytest.raises(ValueError):
        bridge._configured_phone()


def test_bridge_exposes_only_read_operations():
    handler = bridge.handler_for(object())
    assert hasattr(handler, "do_POST")
    assert hasattr(handler, "do_OPTIONS")
    assert not hasattr(handler, "do_GET")
    assert not hasattr(handler, "do_PUT")
    assert not hasattr(handler, "do_DELETE")


class _FakeOpenWA:
    def __init__(self, sessions=None, after_start="qr_ready"):
        self.sessions = dict(sessions or {})
        self.after_start = after_start
        self.calls = []

    async def status(self, identifier):
        self.calls.append(("status", identifier))
        if identifier not in self.sessions:
            raise bridge.OpenWAError("not found")
        return self.sessions[identifier]

    async def find_session(self, name):
        self.calls.append(("find", name))
        return next((item for item in self.sessions.values() if item["name"] == name), None)

    async def create_session(self, name):
        self.calls.append(("create", name))
        self.sessions["uuid-1"] = {"id": "uuid-1", "name": name, "status": "created"}
        return self.sessions["uuid-1"]

    async def start_session(self, identifier):
        self.calls.append(("start", identifier))
        self.sessions[identifier] = {**self.sessions[identifier], "status": self.after_start}
        return self.sessions[identifier]

    async def qr_code(self, identifier):
        return {"qrCode": "data:image/png;base64,QUJD", "status": "qr_ready"}


def _bridge(client, phone=None):
    instance = object.__new__(bridge.WhatsAppLocalBridge)
    instance.client, instance.phone, instance.model = client, phone, "kiara-stable:latest"
    instance.session_id, instance.session_name = None, "kiara"
    return instance


def test_connect_creates_and_starts_the_session_and_returns_the_qr():
    client = _FakeOpenWA()
    result = _bridge(client).connect()
    assert result == {"connected": False, "state": "qr_ready", "qr": "data:image/png;base64,QUJD"}
    assert ("create", "kiara") in client.calls and ("start", "uuid-1") in client.calls


def test_connect_reuses_a_ready_session_without_restarting_it():
    client = _FakeOpenWA({"abc": {"id": "abc", "name": "kiara", "status": "ready", "engineLoaded": True}})
    result = _bridge(client).connect()
    assert result == {"connected": True, "state": "ready", "qr": ""}
    assert not any(call[0] in {"create", "start"} for call in client.calls)


def test_status_without_session_and_analysis_without_contact():
    instance = _bridge(_FakeOpenWA())
    assert instance.status() == {"connected": False, "state": "not_created", "phone": "", "model": "kiara-stable:latest"}
    with pytest.raises(bridge.BridgeError) as error:
        instance.analyze()
    assert error.value.status == 409


class _ScanOpenWA(_FakeOpenWA):
    def __init__(self):
        super().__init__({"s1": {"id": "s1", "name": "kiara", "status": "ready", "engineLoaded": True}})

    async def list_chats(self, identifier, *, limit=200):
        return [
            {"id": "5511999990001@c.us", "name": "Clínica Antiga", "isGroup": False, "timestamp": 10},
            {"id": "5511999990002@c.us", "name": "Clínica Nova", "isGroup": False, "timestamp": 99},
            {"id": "120363000@g.us", "name": "Grupo", "isGroup": True, "timestamp": 100},
            {"id": "5511999990003@c.us", "name": "Arquivada", "isGroup": False, "timestamp": 98, "archived": True},
        ]

    async def read_messages(self, identifier, phone, *, limit=20):
        return [{"waMessageId": f"{phone}-1", "body": "Quanto custa o site?", "direction": "incoming", "timestamp": 1}]


def test_scan_reads_recent_people_only_and_lowers_unsure_stages(monkeypatch):
    answers = iter(['{"stage": "opportunity", "summary": "Pediu preço", "next_action": "Enviar proposta", "confidence": 0.9}',
                    '{"stage": "qualified", "summary": "Curioso", "next_action": "", "confidence": 0.3}'])
    seen = []
    monkeypatch.setattr(bridge, "_model_request", lambda messages, *args, **kwargs: (seen.append(messages[1]["content"]), next(answers))[1])
    instance = _bridge(_ScanOpenWA())
    instance.endpoint, instance.api_key = "http://127.0.0.1:11434/api/chat", ""
    result = instance.scan()
    assert result["scanned"] == 2 and result["skipped"] == 0
    assert [lead["phone"] for lead in result["leads"]] == ["5511999990002", "5511999990001"]
    assert result["leads"][0]["stage"] == "opportunity" and result["leads"][0]["next_action"] == "Enviar proposta"
    assert result["leads"][1]["stage"] == "new" and result["leads"][1]["summary"].startswith("[Baixa confiança")
    assert "Clínica Nova" in seen[0] and not any("Grupo" in prompt or "Arquivada" in prompt for prompt in seen)
