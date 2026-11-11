import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import AsyncMock

import pytest

from app.integrations.openwa import (
    OpenWAClient,
    OpenWADeliveryUnknown,
    OpenWAError,
    phone_chat_id,
    verify_webhook_signature,
)


@pytest.mark.parametrize("phone", ["123@lid", "5511999999999@c.us", "123@g.us", "status@broadcast", "abc5511999999999", "0", True])
def test_phone_is_not_guessed_from_private_or_group_id(phone):
    with pytest.raises(ValueError):
        phone_chat_id(phone)


@pytest.mark.parametrize("url", ["http://127.0.0.1:3006", "http://openwa.example", "https://u:pass@openwa.example", "https://openwa.example/api", "https://10.0.0.1"])
def test_gateway_url_requires_explicit_local_or_public_https(url):
    with pytest.raises(ValueError):
        OpenWAClient(url, "synthetic")


@pytest.mark.asyncio
async def test_contract_paths_identity_and_accepted_receipt():
    client = OpenWAClient("https://gateway.example", "synthetic")
    client._request = AsyncMock(side_effect=[
        {"id": "session-1", "status": "ready", "engineLoaded": True, "proxyUrl": "secret"},
        {"qrCode": "data:image/png;base64,YQ==", "status": "qr_ready"},
        {"messages": [{"id": "m1", "chatId": "5511999999999@c.us", "body": "oi", "metadata": {"secret": "hidden"}}]},
        {"messageId": "provider-1", "timestamp": 1700000000},
    ])
    assert "proxyUrl" not in await client.status("session-1")
    assert (await client.qr_code("session-1"))["status"] == "qr_ready"
    assert "metadata" not in (await client.read_messages("session-1", "+55 (11) 99999-9999"))[0]
    assert await client.send_text("session-1", "5511999999999", "olá", idempotency_key="request-1") == {
        "message_id": "provider-1", "status": "accepted", "timestamp": 1700000000,
    }
    args = client._request.call_args_list[-1]
    assert args.args == ("POST", "/api/sessions/session-1/messages/send-text", {"chatId": "5511999999999@c.us", "text": "olá", "linkPreview": False})
    assert args.kwargs == {"idempotency_key": "request-1"}


@pytest.mark.asyncio
async def test_invalid_session_and_reading_another_chat_are_refused():
    client = OpenWAClient("https://gateway.example", "synthetic")
    client._request = AsyncMock(return_value={"messages": [{"chatId": "another@c.us"}]})
    with pytest.raises(ValueError):
        await client.status("../../other")
    client._request.assert_not_awaited()
    with pytest.raises(OpenWAError):
        await client.read_messages("session-1", "5511999999999")


@pytest.mark.asyncio
async def test_unknown_send_has_no_automatic_retry_or_body_exposure():
    client = OpenWAClient("https://gateway.example", "synthetic")
    client._request = AsyncMock(side_effect=OpenWAError("provider-private-text"))
    with pytest.raises(OpenWADeliveryUnknown) as error:
        await client.send_text("session-1", "5511999999999", "private-customer-text", idempotency_key="request-1")
    assert "private" not in str(error.value)
    assert client._request.await_count == 1


def test_signature_uses_exact_raw_bytes_and_requires_secret():
    raw = b'{"event": "message.received"}'
    signature = "sha256=" + hmac.new(b"synthetic", raw, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(raw, signature, "synthetic")
    assert not verify_webhook_signature(raw.replace(b" ", b""), signature, "synthetic")
    assert not verify_webhook_signature(raw, signature, "")
    assert not verify_webhook_signature(raw, None, "synthetic")


def test_real_loopback_auth_path_redirect_and_no_retry():
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            observed.append((self.path, self.headers.get("X-API-Key"), self.headers.get("Idempotency-Key")))
            self.rfile.read(int(self.headers["Content-Length"]))
            if self.server.redirect:
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1/collect")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                raw = json.dumps({"messageId": "receipt-1", "timestamp": 1700000000}).encode()
                self.send_response(201)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.redirect = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        import asyncio
        client = OpenWAClient(f"http://127.0.0.1:{server.server_port}", "synthetic", allow_private_hosts=True)
        assert asyncio.run(client.send_text("session-1", "5511999999999", "oi", idempotency_key="r1"))["status"] == "accepted"
        server.redirect = True
        with pytest.raises(OpenWADeliveryUnknown):
            asyncio.run(client.send_text("session-1", "5511999999999", "oi", idempotency_key="r2"))
        assert observed == [("/api/sessions/session-1/messages/send-text", "synthetic", "r1"),
                            ("/api/sessions/session-1/messages/send-text", "synthetic", "r2")]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
