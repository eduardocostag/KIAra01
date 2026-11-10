from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError

import pytest

from app.config import Settings
from app.providers.factory import build_llm_provider
from app.providers.freellmapi import FreeLLMAPIProvider
from app.providers.guarded import CloudUsageLimitError, GuardedRemoteProvider
from app.providers.llm import FallbackProvider, LocalFallbackProvider
from app.providers.remote import ProviderConfigurationError


@pytest.mark.parametrize("url", [
    "http://example.com/v1", "https://secret@example.com/v1",
    "https://example.com/v1?key=secret", "file:///v1", "http://localhost:3001",
])
def test_rejects_unsafe_endpoint(url):
    with pytest.raises(ProviderConfigurationError):
        FreeLLMAPIProvider("key", base_url=url)


def test_missing_key_fails_without_request():
    with pytest.raises(ProviderConfigurationError, match="FREELLMAPI_API_KEY"):
        FreeLLMAPIProvider("")


@pytest.mark.asyncio
async def test_factory_sanitizes_loopback_router_and_enforces_budget(tmp_path):
    provider = build_llm_provider(
        Settings(raw={"llm": {"provider": "freellmapi", "routing": {
            "daily_cloud_request_limit": 1,
        }}}, root=tmp_path),
        {"FREELLMAPI_API_KEY": "test-key"},
    )
    assert isinstance(provider, GuardedRemoteProvider)
    calls = []

    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"choices": [{"message": {"content": "ready"}}]}

    provider.provider._transport = transport
    assert await provider.generate(json.dumps({
        "request": "help", "nested": {"relevant_memories": "private"},
        "active_screen": "pixels",
    })) == "ready"
    url, payload, timeout = calls[0]
    assert url == "http://127.0.0.1:3001/v1/chat/completions"
    assert payload["model"] == "auto"
    assert "private" not in payload["messages"][0]["content"]
    assert "pixels" not in payload["messages"][0]["content"]
    assert timeout == 30
    assert provider.capabilities == frozenset({"generate"})
    with pytest.raises(CloudUsageLimitError):
        await provider.generate("second")


@pytest.mark.asyncio
async def test_timeout_and_fallback():
    def slow_transport(*_args):
        time.sleep(0.05)
        return {"choices": [{"message": {"content": "late"}}]}

    provider = FreeLLMAPIProvider("key", timeout_seconds=0.005, transport=slow_transport)
    with pytest.raises(TimeoutError):
        await provider.generate("hello")
    chain = FallbackProvider([provider, LocalFallbackProvider()])
    assert "ferramentas locais" in await chain.generate("hello")


def test_factory_supports_https_remote_and_explicit_profile(tmp_path):
    provider = build_llm_provider(
        Settings(raw={"llm": {"provider": "freellmapi", "model": "auto:fast"}}, root=tmp_path),
        {"FREELLMAPI_API_KEY": "key", "FREELLMAPI_BASE_URL": "https://router.example/v1"},
    )
    assert provider.provider.model == "auto:fast"
    assert provider.provider.base_url == "https://router.example/v1"


def test_hybrid_has_one_guard_per_freellmapi_candidate(tmp_path):
    router = build_llm_provider(
        Settings(raw={"llm": {"provider": "ollama", "model": "local-model", "routing": {
            "enabled": True, "mode": "hybrid", "fast": {"candidates": [
                {"provider": "freellmapi", "model": "auto", "daily_request_limit": 7},
            ]},
        }}}, root=tmp_path),
        {"FREELLMAPI_API_KEY": "key"},
    )
    remote = router.profiles["fast"].providers[0]
    assert isinstance(remote, GuardedRemoteProvider)
    assert isinstance(remote.provider, FreeLLMAPIProvider)
    assert remote.daily_request_limit == 7


@pytest.fixture
def redirect_servers():
    observed = {"source": [], "destination": []}

    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            observed["destination"].append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{}')

        do_POST = do_GET

        def log_message(self, *_args):
            pass

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)

    class Source(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            observed["source"].append(self.headers.get("Authorization"))
            self.send_response(int(self.server.redirect_status))
            self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/collect")
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.wfile.flush()

        def log_message(self, *_args):
            pass

    source = ThreadingHTTPServer(("127.0.0.1", 0), Source)
    threads = [threading.Thread(target=server.serve_forever, daemon=True)
               for server in (source, destination)]
    for thread in threads:
        thread.start()
    try:
        yield source, observed
    finally:
        for server in (source, destination):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("streaming", [False, True])
async def test_real_http_redirect_never_forwards_bearer(redirect_servers, status, streaming):
    server, observed = redirect_servers
    server.redirect_status = status
    provider = FreeLLMAPIProvider(
        "synthetic-secret", base_url=f"http://127.0.0.1:{server.server_port}/v1",
    )
    with pytest.raises((RuntimeError, HTTPError)):
        if streaming:
            _ = [chunk async for chunk in provider.stream("hello")]
        else:
            await provider.generate("hello")
    assert observed["source"] == ["Bearer synthetic-secret"]
    assert observed["destination"] == []
