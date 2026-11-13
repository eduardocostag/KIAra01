import asyncio

from kiara_api import chat, server_gateway


def test_gateway_requires_https_url_and_token(monkeypatch):
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "t" * 64)
    for url in ("", "http://kiara-debian.example.ts.net", "https://user:pw@kiara.example", "https://kiara.example/?x=1", "not a url"):
        monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", url)
        assert server_gateway.gateway_configuration() == ("", ""), url
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net/")
    assert server_gateway.gateway_configuration() == ("https://kiara-debian.example.ts.net", "t" * 64)
    monkeypatch.delenv("KIARA_SERVER_GATEWAY_TOKEN")
    assert server_gateway.gateway_configuration() == ("", "")


def test_status_reports_each_service_without_secrets(monkeypatch):
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "secret-token")
    seen = []

    def fake_get(url, token):
        seen.append((url, token))
        if url.endswith("/healthz"):
            return 200, None
        if url.endswith("/ai/v1/models"):
            return 200, {"data": [{"id": "ollama/qwen3:1.7b"}, {"nope": 1}]}
        if url.endswith("/wa/api/health"):
            return 200, {"status": "ok"}
        return 200, [{"name": "kiara", "status": "qr", "phone": "5551999990000"}]

    monkeypatch.setattr(server_gateway, "_get", fake_get)
    result = asyncio.run(server_gateway.server_status())
    assert result == {"configured": True, "gateway": "ok", "ai": {"state": "ok", "models": ["ollama/qwen3:1.7b"]},
                      "whatsapp": {"state": "ok", "sessions": [{"name": "kiara", "status": "qr"}]}}
    assert ("https://kiara-debian.example.ts.net/healthz", None) in seen  # health check never sends the token
    assert "secret-token" not in repr(result)


def test_status_maps_failures(monkeypatch):
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "x")
    monkeypatch.setattr(server_gateway, "_get", lambda url, token: (0, None) if "healthz" in url else (401, None))
    result = asyncio.run(server_gateway.server_status())
    assert result["gateway"] == "unreachable" and result["ai"]["state"] == "unauthorized" and result["whatsapp"]["sessions"] == []
    monkeypatch.delenv("KIARA_SERVER_GATEWAY_URL")
    assert asyncio.run(server_gateway.server_status()) == {"configured": False}


def test_cloud_chat_uses_the_debian_gateway_when_no_explicit_provider(monkeypatch):
    for name in ("KIARA_CHAT_API_BASE_URL", "KIARA_CHAT_API_KEY", "AI_GATEWAY_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KIARA_CHAT_MODEL", "kiara-local")
    assert chat._configuration() == ("", "", "")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw-token")
    assert chat._configuration() == ("https://kiara-debian.example.ts.net/ai/v1", "kiara-local", "gw-token")
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "https://other.example/v1")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "other")
    assert chat._configuration() == ("https://other.example/v1", "kiara-local", "other")
