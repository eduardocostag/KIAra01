import base64

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from kiara_api import chat, chat_video
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError

JOB = "a" * 32


def build(monkeypatch, reply, fail_start=False):
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "")
    monkeypatch.setenv("KIARA_CHAT_MODEL", "claude/claude-sonnet-5-5")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw")
    seen = {"jobs": [], "system": ""}

    class Provider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def _complete(self, messages):
            seen["system"] = messages[0]["content"]
            return reply

    def call(method, path, body=None, timeout=30, limit=0):
        if method == "POST":
            if fail_start:
                raise RuntimeError("video_service_503")
            seen["jobs"].append(body)
            return {"id": JOB, "status": "queued", "progress": 0, "message": "Na fila", "title": body["title"], "prompt": "hidden"}
        if path.endswith("/file"):
            return b"mp4-bytes"
        return {"id": JOB, "status": "done", "progress": 1, "message": "Pronto", "duration": 5.0, "engine": "ltx"}

    monkeypatch.setattr(chat_video, "_call", call)

    async def no_image(prompt):
        return b"", ""

    app = FastAPI()
    app.include_router(chat.create_chat_router(Provider, image_generator=no_image))

    @app.exception_handler(ApiError)
    async def error(_request, exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status_code)

    app.dependency_overrides[authenticated_context] = lambda: RequestContext("u", "org", "m", "owner", "req", email="admin@kiara.local")
    return TestClient(app), seen


ASK = [{"role": "user", "content": "Faz um vídeo de ondas do mar ao pôr do sol pro meu Reels"}]


def test_chat_marker_starts_a_real_job(monkeypatch):
    api, seen = build(monkeypatch, "Vou preparar!\n[[VIDEO vertical 8s: ocean waves at sunset, slow dolly, golden light]]")
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert chat_video.VIDEO_STYLE in seen["system"]
    assert body["text"] == "Vou preparar!" and body["video"]["id"] == JOB and body["video"]["status"] == "queued"
    job = seen["jobs"][0]
    assert job["prompt"] == "ocean waves at sunset, slow dolly, golden light" and job["portrait"] is True and job["seconds"] == 8
    assert "vertical composition" in job["image_prompt"] and "prompt" not in body["video"]


def test_service_down_is_said_plainly(monkeypatch):
    api, _ = build(monkeypatch, "[[VIDEO: waves]]", fail_start=True)
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert "video" not in body and body["text"] == "Não consegui começar o vídeo agora. Tente de novo em instantes."


def test_voice_never_starts_videos(monkeypatch):
    api, seen = build(monkeypatch, "Claro. [[VIDEO: waves]]")
    body = api.post("/v1/chat/messages", json={"messages": ASK, "voice": True}).json()
    assert seen["jobs"] == [] and body["text"] == "Claro." and chat_video.VIDEO_STYLE not in seen["system"]


def test_video_mode_start_status_download(monkeypatch):
    plan = '{"prompt": "ocean waves at sunset", "portrait": true, "seconds": 6, "title": "Ondas"}'
    api, seen = build(monkeypatch, plan)
    started = api.post("/v1/chat/video", json={"action": "start", "prompt": "ondas do mar pro reels"}).json()
    assert started["video"]["id"] == JOB and seen["jobs"][0]["prompt"] == "ocean waves at sunset"
    assert seen["jobs"][0]["portrait"] is True and seen["jobs"][0]["seconds"] == 6 and seen["jobs"][0]["title"] == "Ondas"
    status = api.post("/v1/chat/video", json={"action": "status", "job_id": JOB}).json()
    assert status["video"]["status"] == "done" and status["video"]["duration"] == 5.0
    download = api.post("/v1/chat/video", json={"action": "download", "job_id": JOB}).json()
    assert download == {"mime": "video/mp4", "data_base64": base64.b64encode(b"mp4-bytes").decode()}
    assert api.post("/v1/chat/video", json={"action": "status", "job_id": "../etc"}).status_code == 422
    assert api.post("/v1/chat/video", json={"action": "start", "prompt": ""}).status_code == 422
    capabilities = api.get("/v1/chat/status").json()["capabilities"]
    assert next(item for item in capabilities if item["id"] == "video")["available"] is True


def test_helpers():
    assert chat_video.parse_options(" vertical 12s") == (True, 10)
    assert chat_video.parse_options("") == (False, 5)
    assert chat_video.parse_plan("nada", "fallback") == ("fallback", False, 5, "")
    assert chat_video.MARKER.search("[[VÍDEO horizontal 4s: a cat]]").group("prompt") == "a cat"
