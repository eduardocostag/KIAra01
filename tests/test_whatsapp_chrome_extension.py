import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from app.whatsapp.browser import ChromeExtensionBrowser
from app.whatsapp.chrome_extension import ChromeExtensionBridge, ExtensionBridgeError
from app.whatsapp.engine import Engine
from app.whatsapp.store import Store


def scan_payload(job_id=None):
    return {
        "job_id": job_id or str(uuid4()),
        "scanned": 1,
        "skipped": 0,
        "conversations": [{
            "phone": "5511999999999",
            "name": "Contato",
            "messages": [{"id": "true_5511999999999@c.us_1", "direction": "in", "text": "Olá"}],
        }],
    }


def test_extension_scan_is_correlated_and_consumed_once():
    bridge = ChromeExtensionBridge()
    payload = scan_payload()
    bridge._accept_scan(payload)

    result = asyncio.run(bridge.wait_for_scan(payload["job_id"], 30, timeout=0.1))

    assert result == {key: payload[key] for key in ("scanned", "skipped", "conversations")}
    with pytest.raises(ExtensionBridgeError, match="extensão Kiara"):
        asyncio.run(bridge.wait_for_scan(payload["job_id"], 30, timeout=0.01))


@pytest.mark.parametrize("change", [
    {"job_id": "invalid"},
    {"scanned": 31},
    {"conversations": [{"phone": "invalid", "name": "Contato", "messages": []}]},
    {"conversations": [
        {"phone": "5511999999999", "name": "Um", "messages": [{"id": "1", "direction": "in", "text": "oi"}]},
        {"phone": "5511999999999", "name": "Dois", "messages": [{"id": "2", "direction": "in", "text": "oi"}]},
    ]},
])
def test_extension_rejects_invalid_scan_payload(change):
    bridge = ChromeExtensionBridge()
    payload = scan_payload()
    payload.update(change)

    with pytest.raises(ValueError):
        bridge._accept_scan(payload)


def test_extension_bridge_heartbeat_expires():
    bridge = ChromeExtensionBridge()
    assert not bridge.online()
    with bridge._condition:
        import time
        bridge._last_heartbeat = time.monotonic()
    assert bridge.online()


def session_fixture(subject=None, expires=None):
    import base64
    import json
    import time
    claims = {"sub": subject or str(uuid4()), "exp": expires or time.time() + 300}
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "header." + encoded + ".signature"


def test_extension_session_is_memory_only_expires_and_clears(monkeypatch):
    import time
    now = time.time()
    monkeypatch.setattr("app.whatsapp.chrome_extension.time.time", lambda: now)
    bridge = ChromeExtensionBridge()
    token = session_fixture(expires=now + 300)
    bridge.accept_session({"access_token": token, "expires_at": now + 300})
    assert bridge.session_token() == token
    now += 91
    assert bridge.session_token() == ""
    bridge.accept_session({"access_token": token, "expires_at": now + 100})
    bridge.accept_session({"access_token": None})
    assert bridge.session_token() == ""


def test_extension_session_rejects_account_switch_and_invalid_tokens():
    import time
    bridge = ChromeExtensionBridge()
    bridge.accept_session({"access_token": session_fixture(), "expires_at": time.time() + 60})
    with pytest.raises(ValueError, match="restart"):
        bridge.accept_session({"access_token": session_fixture(), "expires_at": time.time() + 60})
    assert bridge.session_token() == ""
    with pytest.raises(ValueError):
        bridge.accept_session({"access_token": "invalid", "expires_at": time.time() + 60})


def test_explicit_read_only_adapter_never_runs_automatic_replies():
    with TemporaryDirectory() as directory:
        store = Store(Path(directory) / "state.sqlite3")
        config = store.config()
        config.update({
            "enabled": True,
            "pilot_consent_confirmed": True,
            "ai_context": "Contexto aprovado",
            "contacts": [{"phone": "5511999999999", "name": "Contato", "enabled": True}],
        })
        store.configure(config)

        class OnlineBridge:
            @staticmethod
            def online():
                return True

        try:
            browser = ChromeExtensionBrowser(OnlineBridge())
            browser.read_only = True
            asyncio.run(Engine(store, browser).cycle())
            assert store.db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
            assert store.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        finally:
            store.close()


def test_extension_manifest_uses_bridge_origin_id():
    import hashlib
    import json
    from base64 import b64decode
    manifest = json.loads((Path(__file__).parents[1] / "extensions/kiara-whatsapp/manifest.json").read_text())
    extension_id = "".join(chr(ord("a") + int(value, 16)) for value in hashlib.sha256(b64decode(manifest["key"])).hexdigest()[:32])

    from app.whatsapp.chrome_extension import EXTENSION_ID
    assert extension_id == EXTENSION_ID
