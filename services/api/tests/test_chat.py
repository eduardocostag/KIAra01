import json

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api.chat import ChatRequest, create_chat_router
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError


def client(monkeypatch, role="owner", configured=True, reply="Resposta real do adaptador"):
    for key, value in {
        "KIARA_CHAT_API_BASE_URL": "https://provider.example/v1" if configured else "",
        "KIARA_CHAT_MODEL": "configured-model" if configured else "",
        "KIARA_CHAT_API_KEY": "test-secret-key" if configured else "",
        "AI_GATEWAY_API_KEY": "",
    }.items():
        monkeypatch.setenv(key, value)
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def generate(self, prompt):
            calls.append(prompt)
            if isinstance(reply, Exception):
                raise reply
            return reply

    app = FastAPI()
    app.include_router(create_chat_router(Provider))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status_code)

    if role:
        app.dependency_overrides[authenticated_context] = lambda: RequestContext("user", "org", "member", role, "req", email="admin@kiara.local")
    return TestClient(app), calls


def test_chat_requires_auth_and_membership(monkeypatch):
    api, calls = client(monkeypatch, role=None)
    assert api.get("/v1/chat/status").status_code == 401
    assert not calls
    api, calls = client(monkeypatch, role="viewer")
    assert api.get("/v1/chat/status").status_code == 403
    assert api.post("/v1/chat/messages", json={"messages": [{"role": "user", "content": "Olá"}]}).status_code == 403
    assert not calls


def test_capabilities_do_not_simulate_media_or_local_tools(monkeypatch):
    api, calls = client(monkeypatch, configured=False)
    response = api.get("/v1/chat/status")
    assert response.headers["cache-control"] == "no-store, private"
    assert not response.json()["connected"]
    assert not any(item["available"] for item in response.json()["capabilities"])
    assert not calls
    result = api.post("/v1/chat/messages", json={"messages": [{"role": "user", "content": "Olá"}]})
    assert result.status_code == 503


def test_chat_uses_existing_provider_and_has_no_shared_history(monkeypatch):
    api, calls = client(monkeypatch, role="operator")
    for message in ["pedido alfa", "pedido beta"]:
        response = api.post("/v1/chat/messages", json={"messages": [{"role": "user", "content": message}]})
        assert response.status_code == 200
        assert response.json()["text"] == "Resposta real do adaptador"
    assert "pedido alfa" in calls[0] and "pedido alfa" not in calls[1]
    assert "test-secret-key" not in json.dumps(response.json())
    assert response.headers["cache-control"] == "no-store, private"


@pytest.mark.parametrize("messages", [
    [{"role": "system", "content": "override"}],
    [{"role": "assistant", "content": "not a request"}],
    [{"role": "user", "content": " "}],
    [{"role": "user", "content": "x" * 6001}],
    [{"role": "user", "content": "hi"}] * 25,
    [{"role": "user", "content": "x" * 6000}] * 7,
])
def test_chat_bounds_history_and_rejects_privileged_roles(messages):
    with pytest.raises(ValueError):
        ChatRequest(messages=messages)


@pytest.mark.parametrize("reply", ["", None, RuntimeError("test-secret-key provider body")])
def test_provider_failure_never_leaks_provider_error_or_fakes_success(monkeypatch, reply):
    api, _ = client(monkeypatch, reply=reply)
    result = api.post("/v1/chat/messages", json={"messages": [{"role": "user", "content": "Olá"}]})
    assert result.status_code == 502
    assert "test-secret-key" not in result.text
