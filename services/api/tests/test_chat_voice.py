import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api import chat
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError


def build(monkeypatch, failing_models=()):
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "")
    monkeypatch.setenv("KIARA_CHAT_MODEL", "auto/best-chat")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw")
    monkeypatch.delenv("KIARA_VOICE_MODEL", raising=False)
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def _complete(self, messages):
            calls.append({"model": self.kwargs["model"], "max_tokens": self.kwargs["max_output_tokens"], "messages": messages})
            if self.kwargs["model"] in failing_models:
                raise RuntimeError("provider down")
            return f"resposta de {self.kwargs['model']}"

    app = FastAPI()
    app.include_router(chat.create_chat_router(Provider))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status_code)

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", "owner", "req", email="admin@kiara.local")
    return TestClient(app), calls


HISTORY = [{"role": "user", "content": "Oi"}, {"role": "assistant", "content": "Olá!"}, {"role": "user", "content": "Ideia para clínica?"}]


def test_text_chat_sends_a_real_conversation_with_roles(monkeypatch):
    api, calls = build(monkeypatch)
    response = api.post("/v1/chat/messages", json={"messages": HISTORY})
    assert response.status_code == 200 and response.json()["model"] == "auto/best-chat"
    messages = calls[0]["messages"]
    assert messages[0]["role"] == "system" and "Kiara" in messages[0]["content"] and "voz" not in messages[0]["content"].lower()
    assert messages[1:] == HISTORY
    assert calls[0]["max_tokens"] == 4096


def test_voice_uses_fast_model_short_style_and_falls_back(monkeypatch):
    api, calls = build(monkeypatch)
    response = api.post("/v1/chat/messages", json={"messages": HISTORY, "voice": True})
    assert response.json()["model"] == chat.DEFAULT_VOICE_MODEL
    assert chat.VOICE_STYLE in calls[0]["messages"][0]["content"] and calls[0]["max_tokens"] == 2048

    api, calls = build(monkeypatch, failing_models=(chat.DEFAULT_VOICE_MODEL,))
    response = api.post("/v1/chat/messages", json={"messages": HISTORY, "voice": True})
    assert response.status_code == 200 and response.json()["model"] == "auto/best-chat"
    assert [call["model"] for call in calls] == [chat.DEFAULT_VOICE_MODEL, "auto/best-chat"]


def test_speech_returns_francisca_audio_without_leaking_errors(monkeypatch):
    api, _calls = build(monkeypatch)

    async def fake_synthesize(text):
        assert text == "Olá, tudo bem?"
        return b"ID3audio"

    monkeypatch.setattr(chat, "speech_available", lambda: True)
    monkeypatch.setattr(chat, "synthesize_speech", fake_synthesize)
    response = api.post("/v1/chat/speech", json={"text": "Olá, tudo bem?"})
    assert response.status_code == 200 and response.json()["mime"] == "audio/mpeg"
    assert response.headers["cache-control"] == "no-store, private"

    async def broken(_text):
        raise RuntimeError("wss://secret.example failed")

    monkeypatch.setattr(chat, "synthesize_speech", broken)
    failed = api.post("/v1/chat/speech", json={"text": "Olá"})
    assert failed.status_code == 503 and "secret" not in failed.text
    assert api.post("/v1/chat/speech", json={"text": "x" * 4001}).status_code == 422
    status = api.get("/v1/chat/status").json()
    assert next(item for item in status["capabilities"] if item["id"] == "speech")["available"] is True


def test_real_francisca_voice_is_synthesized():
    import pytest
    if not chat.speech_available():
        pytest.skip("edge-tts not installed")
    try:
        audio = asyncio.run(chat.synthesize_speech("Oi, eu sou a Kiara."))
    except Exception:  # noqa: BLE001 - offline machines cannot reach the voice service
        pytest.skip("voice service unreachable")
    assert len(audio) > 2000
