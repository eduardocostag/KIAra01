from __future__ import annotations

import io
import json
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.integrations.chatwoot import ChatwootClient, ChatwootError, validate_base_url
from app.models import AutonomyMode, PermissionLevel
from app.security.audit import AuditLog
from app.security.permissions import PermissionGate
from app.tools.chatwoot import ChatwootReadTool, ChatwootSendMessageTool
from app.tools.registry import ToolRegistry


@pytest.mark.parametrize("url", ["http://chatwoot.example", "https://u:pass@example.com",
                                 "https://example.com/api", "https://127.0.0.1",
                                 "https://10.0.0.1", "https://example.com?token=private",
                                 "https://example.com#private", "https://example.com:wrong",
                                 "https://example.com\n/", "file:///tmp/file"])
def test_base_url_rejects_unsafe_targets(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_local_urls_are_explicit_and_private_lan_is_never_allowed():
    assert validate_base_url("http://127.0.0.1:3000/", allow_private_hosts=True) == (
        "http://127.0.0.1:3000"
    )
    with pytest.raises(ValueError):
        validate_base_url("https://192.168.0.5", allow_private_hosts=True)


@pytest.mark.parametrize("account", [True, -1, 0, "1", 1.0, 2**53])
def test_invalid_account_ids(account):
    with pytest.raises(ValueError):
        ChatwootClient("https://chatwoot.example", "synthetic", account)


@pytest.mark.asyncio
async def test_contracts_are_account_scoped_and_filter_inbox_secrets():
    client = ChatwootClient("https://chatwoot.example", "synthetic", 7)
    client._request = AsyncMock(side_effect=[
        {"payload": [{"id": 2, "name": "Support", "channel_type": "Channel::Api",
                      "provider_config": {"api_key": "DO-NOT-RETURN"}}]},
        {"data": {"payload": [{"id": 8, "status": "open"}]}},
        {"payload": [{"id": 4, "content": "Hello"}]},
        {"id": 99, "status": "sent", "content": "PRIVATE-CONTENT"},
    ])
    assert await client.list_inboxes() == [{"id": 2, "name": "Support",
                                           "channel_type": "Channel::Api"}]
    assert (await client.list_conversations("open", 2))[0]["id"] == 8
    assert (await client.list_messages(8, before=5))[0]["id"] == 4
    result = await client.send_message(8, "PRIVATE-CONTENT")
    assert result == {"id": 99, "status": "sent"}
    calls = client._request.call_args_list
    assert calls[1].args[1] == "conversations?status=open&page=2"
    assert calls[2].args[1] == "conversations/8/messages?before=5"
    assert calls[3].args == ("POST", "conversations/8/messages", {
        "content": "PRIVATE-CONTENT", "message_type": "outgoing", "private": False,
        "content_type": "text",
    })


@pytest.mark.asyncio
async def test_write_requires_human_confirmation_and_redacts_audit(tmp_path: Path):
    client = ChatwootClient("https://chatwoot.example", "synthetic", 1)
    client.send_message = AsyncMock(return_value={"id": 12})
    summaries = []
    log = AuditLog(tmp_path / "audit.jsonl")
    gate = PermissionGate(AutonomyMode.AUTONOMOUS, confirm=lambda text: summaries.append(text) or False)
    registry = ToolRegistry(gate, log)
    registry.register(ChatwootSendMessageTool(client))
    assert registry.permission_for("chatwoot_send_message") == PermissionLevel.CRITICAL_ACTION
    assert not (await registry.execute("chatwoot_send_message", conversation_id=1,
                                      content="PRIVATE-CONTENT")).success
    client.send_message.assert_not_awaited()
    gate.confirm = lambda text: summaries.append(text) or True
    assert (await registry.execute("chatwoot_send_message", conversation_id=1,
                                   content="PRIVATE-CONTENT")).success
    assert "PRIVATE-CONTENT" not in str(summaries)
    assert "PRIVATE-CONTENT" not in log.path.read_text()
    assert client.send_message.await_count == 1


@pytest.mark.asyncio
async def test_read_tool_exposes_items():
    client = ChatwootClient("https://chatwoot.example", "synthetic", 1)
    client.list_conversations = AsyncMock(return_value=[{"id": 1}])
    result = await ChatwootReadTool(client).execute(action="conversations", limit=5)
    assert result.metadata == {"items": [{"id": 1}]}
    with pytest.raises(ValueError):
        ChatwootReadTool(client).validate({"action": "messages", "conversation_id": "1/secret"})


def test_dns_private_destinations_blocked_before_transport(monkeypatch):
    client = ChatwootClient("https://chatwoot.example", "synthetic", 1)
    monkeypatch.setattr("app.integrations.chatwoot.socket.getaddrinfo",
                        lambda *a, **kw: [(2, 1, 6, "", ("169.254.169.254", 443))])
    with pytest.raises(ChatwootError, match="privado"):
        client._request_sync("GET", "inboxes", None)


@pytest.fixture
def chatwoot_server():
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observed.append((self.path, self.headers.get("api_access_token")))
            if self.path == "/collect":
                raw = b'{}'
                status = 200
            elif self.server.redirect:
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/collect")
                self.send_header("Content-Length", "0")
                self.end_headers()
                self.wfile.flush()
                return
            else:
                status = self.server.status_code
                raw = self.server.payload
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            self.wfile.flush()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.redirect = False
    server.status_code = 200
    server.payload = b'{"payload":[{"id":1,"name":"Support"}]}'
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, observed
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_real_transport_header_scoping_and_redirect_denial(chatwoot_server):
    server, observed = chatwoot_server
    client = ChatwootClient(f"http://127.0.0.1:{server.server_port}", "synthetic", 42,
                            allow_private_hosts=True)
    assert await client.list_inboxes() == [{"id": 1, "name": "Support"}]
    assert observed == [("/api/v1/accounts/42/inboxes", "synthetic")]
    server.redirect = True
    with pytest.raises(ChatwootError, match="Redirecionamento"):
        await client.list_inboxes()
    assert len(observed) == 2
    assert not any(path == "/collect" for path, _ in observed)


@pytest.mark.asyncio
@pytest.mark.parametrize(("payload", "status", "expected"), [
    (b'{"token":"synthetic","content":"PRIVATE"}', 401, "HTTP 401"),
    (b"PRIVATE invalid json", 200, "incompativel"),
    (b"x" * 1_000_001, 200, "limite"),
    (json.dumps([]).encode(), 200, "incompativel"),
], ids=["unauthorized", "invalid-json", "oversized", "wrong-shape"])
async def test_remote_errors_do_not_expose_payload(chatwoot_server, payload, status, expected):
    server, _ = chatwoot_server
    server.status_code, server.payload = status, payload
    client = ChatwootClient(f"http://127.0.0.1:{server.server_port}", "synthetic", 1,
                            allow_private_hosts=True)
    with pytest.raises(ChatwootError, match=expected) as error:
        await client.list_inboxes()
    assert "synthetic" not in str(error.value)
    assert "PRIVATE" not in str(error.value)


def test_pinned_tcp_uses_one_dns_lookup_and_keeps_tls_hostname(monkeypatch):
    observed = {"dns": [], "connect": [], "tls": [], "sent": []}

    def resolving_host(host, port, **_kwargs):
        observed["dns"].append((host, port))
        # A malicious resolver changes to a private address on a second lookup.
        address = "93.184.216.34" if len(observed["dns"]) == 1 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))]

    class Transport:
        def settimeout(self, timeout):
            assert timeout == 15

        def connect(self, address):
            observed["connect"].append(address)

        def sendall(self, data):
            observed["sent"].append(data)

        def makefile(self, mode):
            assert mode == "rb"
            payload = b'{"payload":[]}'
            return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: "
                              + str(len(payload)).encode() + b"\r\n\r\n" + payload)

        def close(self):
            pass

    transport = Transport()
    context = ssl.create_default_context()

    def wrap_socket(sock, *, server_hostname):
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        observed["tls"].append(server_hostname)
        return sock

    monkeypatch.setattr("app.integrations.chatwoot.socket.getaddrinfo", resolving_host)
    monkeypatch.setattr("app.integrations.chatwoot.socket.socket", lambda *_a: transport)
    monkeypatch.setattr(context, "wrap_socket", wrap_socket)
    monkeypatch.setattr("app.integrations.chatwoot.ssl.create_default_context", lambda: context)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    client = ChatwootClient("https://support.example.com", "synthetic", 1)
    assert client._request_sync("GET", "inboxes", None) == {"payload": []}
    assert observed["dns"] == [("support.example.com", 443)]
    assert observed["connect"] == [("93.184.216.34", 443)]
    assert observed["tls"] == ["support.example.com"]
    headers = b"".join(observed["sent"])
    assert b"Host: support.example.com" in headers
    assert b"api_access_token: synthetic" in headers


def test_failed_post_connection_never_retries_another_ip(monkeypatch):
    attempts = []

    class FailingTransport:
        def settimeout(self, _timeout):
            pass

        def connect(self, address):
            attempts.append(address)
            raise TimeoutError("untrusted detail")

        def close(self):
            pass

    monkeypatch.setattr("app.integrations.chatwoot.socket.getaddrinfo", lambda *_a, **_kw: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))
        for address in ("93.184.216.34", "93.184.216.35")
    ])
    monkeypatch.setattr("app.integrations.chatwoot.socket.socket", lambda *_a: FailingTransport())
    client = ChatwootClient("https://support.example.com", "synthetic", 1)
    with pytest.raises(ChatwootError, match="antes de repetir"):
        client._request_sync("POST", "conversations/1/messages", {"content": "PRIVATE"})
    assert attempts == [("93.184.216.34", 443)]
