from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from app.whatsapp.engine import Engine, LeadAnalyzer, ReplyUnavailable, Responder
from app.whatsapp.store import Store, validate_config


def active_config():
    return {
        "pilot_mode": True,
        "pilot_consent_confirmed": True,
        "enabled": True,
        "ai_context": "Empresa de teste; encaminhe para a equipe quando faltar informação.",
        "contacts": [{"phone": "5511999999999", "name": "Teste autorizado", "enabled": True}],
    }


def test_pilot_requires_consent_and_only_one_enabled_contact():
    with pytest.raises(ValueError, match="somente um contato"):
        validate_config({
            "contacts": [
                {"phone": "5511999999999", "enabled": True},
                {"phone": "5511888888888", "enabled": True},
            ],
        })

    with pytest.raises(ValueError, match="autorizou"):
        validate_config({
            "enabled": True,
            "contacts": [{"phone": "5511999999999", "enabled": True}],
        })


def test_operation_mode_allows_multiple_explicitly_authorized_contacts():
    config = active_config()
    config["pilot_mode"] = False
    config["contacts"].append({"phone": "5511888888888", "enabled": True})
    assert len(validate_config(config)["contacts"]) == 2


def test_responder_fails_closed_without_local_model(monkeypatch):
    monkeypatch.delenv("KIARA_WHATSAPP_OLLAMA_MODEL", raising=False)
    responder = Responder()
    with pytest.raises(ReplyUnavailable, match="não configurado"):
        responder.reply([], active_config())


def test_responder_uses_approved_business_context(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, limit):
            return json.dumps({"message": {"content": json.dumps({"text": "Olá", "handoff": False})}}).encode()

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        prompt = payload["messages"][0]["content"]
        assert "SERVIÇO APROVADO" in prompt
        assert "TEXTO DESATUALIZADO" not in prompt
        return Response()

    monkeypatch.setenv("KIARA_WHATSAPP_OLLAMA_MODEL", "local-test-model")
    monkeypatch.setattr("app.whatsapp.engine.urlopen", fake_urlopen)
    config = active_config()
    config["ai_context"] = "SERVIÇO APROVADO"
    config["reply_template"] = "TEXTO DESATUALIZADO"

    assert Responder().reply([], config) == ("Olá", False)


def test_lead_analyzer_returns_crm_fields_without_sending(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, limit):
            result = {"stage": "qualified", "summary": "Pediu uma proposta.",
                      "next_action": "Enviar proposta", "confidence": 0.92}
            return json.dumps({"message": {"content": json.dumps(result)}}).encode()

    def fake_urlopen(request, timeout):
        payload = json.loads(request.data)
        assert payload["messages"][0]["role"] == "system"
        assert "Retorne somente JSON válido" in payload["messages"][0]["content"]
        return Response()

    monkeypatch.setenv("KIARA_WHATSAPP_OLLAMA_MODEL", "local-test-model")
    monkeypatch.setattr("app.whatsapp.engine.urlopen", fake_urlopen)
    conversation = {
        "phone": "5511999999999", "name": "Contato",
        "messages": [{"direction": "in", "text": "Quero uma proposta"}],
    }
    lead = LeadAnalyzer().analyze(conversation)
    assert lead["phone"] == conversation["phone"]
    assert lead["name"] == conversation["name"]
    assert lead["stage"] == "qualified"
    assert lead["next_action"] == "Enviar proposta"


class FakeBrowser:
    def __init__(self):
        self.messages = [
            {"id": "old", "direction": "in", "text": "Mensagem anterior"},
            {"id": "new", "direction": "in", "text": "Olá, tenho interesse"},
        ]
        self.sent = []

    async def status(self):
        return "ready"

    async def read(self, phone):
        return self.messages

    async def send(self, phone, text, expected_ids=None):
        self.sent.append((phone, text))
        return "sent-id"


def test_engine_pauses_inbound_without_model_without_sending(monkeypatch):
    monkeypatch.delenv("KIARA_WHATSAPP_OLLAMA_MODEL", raising=False)
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        store = Store(Path(directory) / "pilot.sqlite3")
        browser = FakeBrowser()
        try:
            store.configure(active_config())
            store.ingest("5511999999999", [browser.messages[0]])

            asyncio.run(Engine(store, browser).cycle())

            assert browser.sent == []
            contact = store.db.execute("SELECT handoff FROM contacts WHERE phone=?", ("5511999999999",)).fetchone()
            assert contact["handoff"] == 1
            events = store.pending_events()
            assert any("IA local indisponível" in event["text"] for event in events)
        finally:
            store.close()


def test_config_defaults_to_disabled_pilot():
    config = validate_config({})
    assert config["pilot_mode"] is True
    assert config["pilot_consent_confirmed"] is False
    assert config["enabled"] is False


def test_enabled_pilot_requires_approved_ai_context():
    with pytest.raises(ValueError, match="informações autorizadas"):
        validate_config({
            "enabled": True,
            "pilot_consent_confirmed": True,
            "contacts": [{"phone": "5511999999999", "enabled": True}],
        })


def test_engine_uses_handoff_template_when_model_requests_human(monkeypatch):
    monkeypatch.setattr("app.whatsapp.store.within_window", lambda config, now: True)
    class HandoffResponder:
        def reply(self, history, config):
            assert "ai_context" in config
            return "Vou encaminhar para a equipe.", True

    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        store = Store(Path(directory) / "pilot.sqlite3")
        browser = FakeBrowser()
        try:
            config = active_config()
            config["reply_template"] = "Olá {name}, vou encaminhar sua dúvida."
            store.configure(config)
            store.ingest("5511999999999", [browser.messages[0]])

            asyncio.run(Engine(store, browser, responder=HandoffResponder()).cycle())

            assert browser.sent == [("5511999999999", "Olá Teste autorizado, vou encaminhar sua dúvida.")]
            assert store.db.execute("SELECT handoff FROM contacts WHERE phone=?", ("5511999999999",)).fetchone()["handoff"] == 1
        finally:
            store.close()


def test_analysis_command_imports_visible_chats_without_sending(monkeypatch):
    monkeypatch.setattr("app.whatsapp.store.within_window", lambda config, now: True)

    class AnalysisBrowser(FakeBrowser):
        async def scan_visible_conversations(self, limit):
            assert limit == 30
            return {
                "conversations": [{
                    "phone": "5511999999999", "name": "Teste autorizado",
                    "messages": [{"direction": "in", "text": "Tenho interesse"}],
                }],
                "scanned": 1, "skipped": 0,
            }

    class Bridge:
        configured = True

        def __init__(self):
            self.completed = None

        def config(self):
            return active_config()

        def next_analysis(self):
            return {"id": "job-1", "status": "running", "limit": 30}

        def complete_analysis(self, job_id, result):
            self.completed = (job_id, result)

    class Analyzer:
        def analyze(self, conversation):
            return {"phone": conversation["phone"], "name": conversation["name"],
                    "stage": "qualified", "summary": "Demonstra interesse.",
                    "next_action": "Agendar atendimento", "confidence": 0.9}

    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        store = Store(Path(directory) / "pilot.sqlite3")
        browser = AnalysisBrowser()
        bridge = Bridge()
        try:
            engine = Engine(store, browser, bridge=bridge)
            engine.lead_analyzer = Analyzer()
            asyncio.run(engine.cycle())
            assert bridge.completed[0] == "job-1"
            assert bridge.completed[1]["leads"][0]["stage"] == "qualified"
            assert browser.sent == []
        finally:
            store.close()
