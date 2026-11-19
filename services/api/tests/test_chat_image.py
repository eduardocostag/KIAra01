import asyncio
import base64
import io

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from PIL import Image

from kiara_api import chat, chat_image
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError


def png(size=(2048, 1024)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 90, 200)).save(out, "PNG")
    return out.getvalue()


def build(monkeypatch, reply, picture=b"jpeg-bytes"):
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "")
    monkeypatch.setenv("KIARA_CHAT_MODEL", "claude/claude-sonnet-5-5")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw")
    seen = {"prompts": [], "system": ""}

    class Provider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def _complete(self, messages):
            seen["system"] = messages[0]["content"]
            return reply

    async def make(prompt):
        seen["prompts"].append(prompt)
        return (picture, "model-x") if picture else (b"", "")

    app = FastAPI()
    app.include_router(chat.create_chat_router(Provider, image_generator=make))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status_code)

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", "owner", "req", email="admin@kiara.local")
    return TestClient(app), seen


ASK = [{"role": "user", "content": "Gera uma imagem de um gato astronauta perto de Saturno, aquarela"}]


def test_chat_turns_the_marker_into_a_real_image(monkeypatch):
    api, seen = build(monkeypatch, "Claro! Olha só:\n[[IMAGEM: gato astronauta flutuando perto de Saturno, aquarela suave]]")
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert chat_image.IMAGE_STYLE in seen["system"]
    assert seen["prompts"] == ["gato astronauta flutuando perto de Saturno, aquarela suave"]
    assert body["text"] == "Claro! Olha só:" and "[[" not in body["text"]
    assert body["image"] == {"mime": "image/jpeg", "data_base64": base64.b64encode(b"jpeg-bytes").decode(),
                             "prompt": "gato astronauta flutuando perto de Saturno, aquarela suave"}
    assert body["model"] == "claude/claude-sonnet-5-5"


def test_plain_answers_have_no_image(monkeypatch):
    api, seen = build(monkeypatch, "O céu é azul pelo espalhamento de Rayleigh.")
    body = api.post("/v1/chat/messages", json={"messages": [{"role": "user", "content": "Por que o céu é azul?"}]}).json()
    assert "image" not in body and seen["prompts"] == []


def test_failed_generation_is_said_plainly(monkeypatch):
    api, _ = build(monkeypatch, "[[IMAGEM: um farol]]", picture=b"")
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert "image" not in body and body["text"].startswith("Não consegui criar a imagem agora")


def test_voice_never_generates_images(monkeypatch):
    api, seen = build(monkeypatch, "Posso sim. [[IMAGEM: um farol]]")
    body = api.post("/v1/chat/messages", json={"messages": ASK, "voice": True}).json()
    assert "image" not in body and seen["prompts"] == [] and body["text"] == "Posso sim."
    assert chat_image.IMAGE_STYLE not in seen["system"]


def test_image_mode_endpoint_and_status(monkeypatch):
    api, seen = build(monkeypatch, "")
    body = api.post("/v1/chat/image", json={"prompt": "um farol ao amanhecer"}).json()
    assert body["image"]["mime"] == "image/jpeg" and seen["prompts"] == ["um farol ao amanhecer"]
    status = api.get("/v1/chat/status").json()
    assert next(item for item in status["capabilities"] if item["id"] == "image")["available"] is True
    api, _ = build(monkeypatch, "", picture=b"")
    assert api.post("/v1/chat/image", json={"prompt": "um farol"}).status_code == 502


def test_generator_falls_back_and_returns_a_small_jpeg(monkeypatch):
    monkeypatch.delenv("KIARA_IMAGE_MODELS", raising=False)
    calls = []

    def request(model, prompt, timeout):
        calls.append(model)
        if model == chat_image.DEFAULT_IMAGE_MODELS[0]:
            raise RuntimeError("quota")
        return png()

    picture, model = asyncio.run(chat_image.generate_image("um farol", request=request))
    chain = chat_image.image_models()
    assert calls == chain[:2] and model == chain[1]
    with Image.open(io.BytesIO(picture)) as image:
        assert image.format == "JPEG" and max(image.size) == chat_image.MAX_SIDE
    assert asyncio.run(chat_image.generate_image("x", request=lambda *_: (_ for _ in ()).throw(RuntimeError()))) == (b"", "")


def test_cloudflare_models_join_the_chain_only_when_its_account_is_set(monkeypatch):
    from kiara_api import chat_image
    monkeypatch.delenv("KIARA_IMAGE_MODELS", raising=False)
    monkeypatch.delenv("KIARA_CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("KIARA_CLOUDFLARE_API_TOKEN", raising=False)
    assert not any(model.startswith("cloudflare/") for model in chat_image.image_models())
    assert "codex/gpt-image-2" not in chat_image.image_models()
    monkeypatch.setenv("KIARA_CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setenv("KIARA_CLOUDFLARE_API_TOKEN", "tok")
    assert chat_image.image_models()[1] == "cloudflare/@cf/black-forest-labs/flux-2-klein-4b"
