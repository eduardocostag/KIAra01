import asyncio
import time
from datetime import UTC, datetime
from itertools import pairwise

import pytest

from app.whatsapp.chrome_extension import ChromeExtensionBridge, ExtensionBridgeError
from app.whatsapp.engine import Engine
from app.whatsapp.store import Store, validate_config

PHONE = "5511999999999"


def test_snapshot_preserves_observed_order_in_utc_without_retimestamping_replays(tmp_path):
    store = Store(tmp_path / "state.db")
    store.configure({"contacts": [{"phone": PHONE}]})
    snapshot = [{"id": f"m{index}", "direction": "in" if index % 2 == 0 else "out",
                 "text": str(index)} for index in range(4)]
    observed = datetime(2026, 11, 9, 14, 0, tzinfo=UTC)
    try:
        assert store.ingest(PHONE, snapshot, now=observed) == []
        events = [item for item in store.pending_events() if item.get("external_message_id")]
        times = [datetime.fromisoformat(item["occurred_at"]) for item in events]
        assert all(item.tzinfo == UTC for item in times)
        assert all(first < second for first, second in pairwise(times))
        assert [item["external_message_id"] for item in events] == ["m0", "m1", "m2", "m3"]
        store.ingest(PHONE, snapshot, now=datetime(2026, 11, 10, tzinfo=UTC))
        assert store.pending_events() == events
    finally:
        store.close()


@pytest.mark.asyncio
async def test_bridge_commands_are_claimed_once_and_require_correlated_phone():
    bridge = ChromeExtensionBridge()
    bridge._last_heartbeat = time.monotonic()
    task = asyncio.create_task(bridge.execute("read", PHONE, timeout=2))
    command = None
    for _ in range(100):
        command = bridge.next_command()
        if command:
            break
        await asyncio.sleep(0.005)
    assert command["phone"] == PHONE
    assert bridge.next_command() is None
    with pytest.raises(ValueError):
        bridge.accept_command_result({"id": command["id"], "phone": "5511888888888", "ok": True, "messages": []})
    messages = [{"id": "m1", "direction": "in", "text": "Oi"}]
    bridge.accept_command_result({"id": command["id"], "phone": PHONE, "ok": True, "messages": messages})
    assert (await task)["messages"] == messages
    with pytest.raises(ValueError):
        bridge.accept_command_result({"id": command["id"], "phone": PHONE, "ok": True, "messages": messages})


@pytest.mark.asyncio
async def test_expired_send_command_cannot_be_replayed():
    bridge = ChromeExtensionBridge()
    bridge._last_heartbeat = time.monotonic()
    with pytest.raises(ExtensionBridgeError):
        await bridge.execute("send", PHONE, text="Oi", expected_ids=[], timeout=0.01)
    assert bridge.next_command() is None


def test_disabled_automation_syncs_history_without_responding(tmp_path):
    store = Store(tmp_path / "state.db")
    config = validate_config({"contacts": [{"phone": PHONE, "enabled": True}]})
    store.configure(config)

    class Browser:
        async def status(self): return "ready"
        async def read(self, phone):
            return [{"id": "history-1", "direction": "in", "text": "Tenho interesse"}]
        async def send(self, *_args, **_kwargs): raise AssertionError("No automatic send")

    try:
        asyncio.run(Engine(store, Browser()).cycle())
        asyncio.run(Engine(store, Browser()).cycle())
        events = [event for event in store.pending_events() if event.get("external_message_id")]
        assert len(events) == 1
        assert events[0]["external_message_id"] == "history-1"
        assert events[0]["status"] == "historical"
        assert store.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        store.close()


@pytest.mark.parametrize("confirmed", [False, True])
def test_manual_site_reply_has_fresh_snapshot_no_retry_and_handoff(tmp_path, confirmed):
    store = Store(tmp_path / "state.db")

    class Bridge:
        configured = True
        def __init__(self): self.completed = []
        def config(self): return validate_config({})
        def next_analysis(self): return None
        def next_outbound(self): return {"id": "outbox-1", "phone": PHONE, "text": "Resposta humana"}
        def complete_outbound(self, identifier, **result): self.completed.append((identifier, result))
        def _request(self, *_args): return {}

    class Browser:
        def __init__(self): self.sent = []
        async def status(self): return "ready"
        async def read(self, phone): return [{"id": "latest", "direction": "in", "text": "Pergunta"}]
        async def send(self, phone, text, expected_ids):
            assert expected_ids == ["latest"]
            self.sent.append((phone, text))
            return "sent-1" if confirmed else False

    bridge, browser = Bridge(), Browser()
    try:
        asyncio.run(Engine(store, browser, bridge=bridge).cycle())
        assert len(browser.sent) == 1
        assert bridge.completed[0][1]["status"] == ("sent" if confirmed else "unknown")
        assert store.db.execute("SELECT handoff FROM contacts WHERE phone=?", (PHONE,)).fetchone()[0] == 1
    finally:
        store.close()


def test_resume_handoff_never_clears_optout(tmp_path):
    store = Store(tmp_path / "state.db")
    config = validate_config({"contacts": [{"phone": PHONE, "handoff": True}]})
    try:
        store.configure(config)
        store.pause(PHONE, optout=True)
        config["contacts"][0]["handoff"] = False
        store.configure(config)
        row = store.db.execute("SELECT handoff,optout FROM contacts WHERE phone=?", (PHONE,)).fetchone()
        assert tuple(row) == (1, 1)
    finally:
        store.close()


@pytest.mark.parametrize("outcome", ["sent-initial", False])
def test_initial_outreach_is_explicit_and_never_repeated_after_restart_or_template_edit(tmp_path, monkeypatch, outcome):
    monkeypatch.setattr("app.whatsapp.store.within_window", lambda *_args: True)
    filename = tmp_path / "state.db"
    config = validate_config({
        "pilot_mode": False, "pilot_consent_confirmed": True, "enabled": True,
        "ai_context": "Serviço aprovado", "auto_reply_enabled": False,
        "initial_outreach_enabled": True, "outreach_template": "Olá {name}! Posso ajudar?",
        "contacts": [{"phone": PHONE, "name": "Cliente", "enabled": True}],
    })

    class Browser:
        def __init__(self): self.sent = []
        async def status(self): return "ready"
        async def read(self, _phone): return []
        async def send(self, phone, text, expected_ids):
            assert expected_ids == []
            self.sent.append((phone, text))
            return outcome

    browser = Browser()
    store = Store(filename)
    try:
        store.configure(config)
        asyncio.run(Engine(store, browser).cycle())
        assert browser.sent == [(PHONE, "Olá Cliente! Posso ajudar?")]
    finally:
        store.close()
    store = Store(filename)
    try:
        config["outreach_template"] = "Texto alterado {name}"
        store.configure(config)
        store.resume(PHONE)
        asyncio.run(Engine(store, browser).cycle())
        assert len(browser.sent) == 1
        rows = store.db.execute("SELECT status,source_id FROM outbox WHERE kind='outreach'").fetchall()
        assert len(rows) == 1
        assert rows[0]["source_id"] == f"initial:{PHONE}"
        assert rows[0]["status"] == ("sent" if outcome else "unknown")
    finally:
        store.close()


@pytest.mark.parametrize("enabled,existing", [(False, False), (True, True)])
def test_initial_outreach_never_targets_existing_conversations_or_disabled_policy(tmp_path, monkeypatch, enabled, existing):
    monkeypatch.setattr("app.whatsapp.store.within_window", lambda *_args: True)
    store = Store(tmp_path / "state.db")
    store.configure({"pilot_consent_confirmed": True, "enabled": True,
                     "ai_context": "Informações autorizadas", "auto_reply_enabled": False,
                     "initial_outreach_enabled": enabled,
                     "contacts": [{"phone": PHONE, "enabled": True}]})

    class Browser:
        async def status(self): return "ready"
        async def read(self, _phone):
            return [{"id": "old", "direction": "in", "text": "Mensagem anterior"}] if existing else []
        async def send(self, *_args, **_kwargs): raise AssertionError("No initial message allowed")

    try:
        asyncio.run(Engine(store, Browser()).cycle())
        assert store.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        store.close()
