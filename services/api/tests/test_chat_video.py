import base64
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from kiara_api import chat, chat_video
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError

JOB = "a" * 32
SCRIPT = json.dumps({
    "meta": {"brand": "Mar Azul Pousada", "cta": "Reserve: @marazul", "presenter": True},
    "scenes": [
        {"id": "Abertura!", "layout": "photo", "accent": "#38bdf8", "kicker": "Mar Azul", "title": "Seu refúgio no mar.",
         "image": "beach at sunset, golden light", "text": "Imagine acordar com o som do mar.",
         "cards": [{"text": "Vista para o mar", "cue": "mar"}]},
        {"id": "final", "layout": "photo", "title": "Venha. Reserve já.", "text": "Reserve agora pelo Instagram."},
    ],
})


def build(monkeypatch, replies, fail_start=False):
    """`replies`: what the model answers, in order (the chat reply, then the video script)."""
    monkeypatch.setenv("KIARA_CHAT_API_BASE_URL", "")
    monkeypatch.setenv("KIARA_CHAT_API_KEY", "")
    monkeypatch.setenv("KIARA_CHAT_MODEL", "claude/claude-sonnet-5-5")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_URL", "https://kiara-debian.example.ts.net")
    monkeypatch.setenv("KIARA_SERVER_GATEWAY_TOKEN", "gw")
    seen = {"jobs": [], "systems": [], "paths": []}
    queue = list(replies)

    class Provider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def _complete(self, messages):
            seen["systems"].append(messages[0]["content"])
            return queue.pop(0) if len(queue) > 1 else queue[0]

    def call(method, path, body=None, timeout=30, limit=0, with_headers=False):
        seen["paths"].append(path)
        if method == "POST":
            if fail_start:
                raise RuntimeError("video_service_503")
            seen["jobs"].append(body)
            return {"id": JOB, "status": "queued", "progress": 0, "message": "Na fila", "title": body["title"], "script": "hidden"}
        if "/file" in path:
            return (b"mp4-part", "3") if with_headers else b"mp4-part"
        return {"id": JOB, "status": "done", "progress": 1, "message": "Pronto", "duration": 41.0, "engine": "studio", "parts": 3}

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


ASK = [{"role": "user", "content": "Faz um vídeo da minha pousada Mar Azul pro meu Reels"}]


def test_chat_marker_writes_a_script_and_starts_a_studio_job(monkeypatch):
    api, seen = build(monkeypatch, ["Vou produzir!\n[[VIDEO vertical 30s: vídeo da pousada Mar Azul para o Reels, tom acolhedor]]", SCRIPT])
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert chat_video.VIDEO_STYLE in seen["systems"][0]
    assert body["text"] == "Vou produzir!" and body["video"]["id"] == JOB and body["video"]["status"] == "queued"
    assert "diretora de vídeos" in seen["systems"][1] and "pousada Mar Azul" in seen["systems"][1]
    job = seen["jobs"][0]
    assert job["kind"] == "studio" and "script" not in body["video"]
    meta, scenes = job["script"]["meta"], job["script"]["scenes"]
    assert meta["portrait"] is True and meta["presenter"] is True           # the narrator orb, as in the presentation
    assert [scene["id"] for scene in scenes] == ["abertura", "final"] and scenes[-1]["layout"] == "outro"
    assert scenes[0]["image"] == "beach at sunset, golden light" and scenes[0]["cards"] == [{"text": "Vista para o mar", "cue": "mar"}]


def test_a_broken_script_or_a_down_service_is_said_plainly(monkeypatch):
    api, _ = build(monkeypatch, ["[[VIDEO: ondas]]", "não sei fazer JSON"])
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert "video" not in body and body["text"].startswith("Não consegui começar o vídeo agora")
    api, _ = build(monkeypatch, ["[[VIDEO: ondas]]", SCRIPT], fail_start=True)
    body = api.post("/v1/chat/messages", json={"messages": ASK}).json()
    assert "video" not in body and body["text"].startswith("Não consegui começar o vídeo agora")


def test_voice_never_starts_videos(monkeypatch):
    api, seen = build(monkeypatch, ["Claro. [[VIDEO: waves]]"])
    body = api.post("/v1/chat/messages", json={"messages": ASK, "voice": True}).json()
    assert seen["jobs"] == [] and body["text"] == "Claro." and chat_video.VIDEO_STYLE not in seen["systems"][0]


def test_video_mode_start_status_and_download_in_parts(monkeypatch):
    api, seen = build(monkeypatch, [SCRIPT])
    started = api.post("/v1/chat/video", json={"action": "start", "prompt": "vídeo de 1 min da pousada pro reels"}).json()
    assert started["video"]["id"] == JOB and seen["jobs"][0]["kind"] == "studio"
    assert seen["jobs"][0]["script"]["meta"]["portrait"] is True and "cerca de 60 segundos" in seen["systems"][0]
    status = api.post("/v1/chat/video", json={"action": "status", "job_id": JOB}).json()
    assert status["video"]["status"] == "done" and status["video"]["duration"] == 41.0 and status["video"]["parts"] == 3
    download = api.post("/v1/chat/video", json={"action": "download", "job_id": JOB, "part": 2}).json()
    assert download == {"mime": "video/mp4", "data_base64": base64.b64encode(b"mp4-part").decode(), "part": 2, "parts": 3}
    assert seen["paths"][-1] == f"/jobs/{JOB}/file?part=2"
    raw = api.post("/v1/chat/video", json={"action": "download", "job_id": JOB, "part": 1, "raw": True})
    assert raw.status_code == 200 and raw.content == b"mp4-part" and raw.headers["content-type"] == "video/mp4"
    assert raw.headers["x-kiara-parts"] == "3" and raw.headers["x-kiara-part"] == "1"
    assert api.post("/v1/chat/video", json={"action": "download", "job_id": JOB, "part": 99}).status_code == 422
    assert api.post("/v1/chat/video", json={"action": "status", "job_id": "../etc"}).status_code == 422
    assert api.post("/v1/chat/video", json={"action": "start", "prompt": ""}).status_code == 422
    capabilities = api.get("/v1/chat/status").json()["capabilities"]
    assert next(item for item in capabilities if item["id"] == "video")["available"] is True


def test_helpers():
    assert chat_video.parse_options(" vertical 60s") == (True, 60)
    assert chat_video.parse_options(" 5s") == (False, 15)
    assert chat_video.parse_options("") == (False, 40)
    assert chat_video.MARKER.search("[[VÍDEO horizontal 40s: a cat]]").group("prompt") == "a cat"
    assert "shot" in chat_video.studio_prompt("Apresentação da Kiara para a Ana", portrait=False, seconds=60)
    assert "shot" not in chat_video.studio_prompt("Apresentação da Kiara para a Ana", portrait=True, seconds=60)
    script = chat_video.parse_script("aqui: " + SCRIPT + " fim", portrait=False)
    assert script["meta"]["presenter"] is True and script["meta"]["portrait"] is False
    assert "hello" in chat_video.studio_prompt("Vídeo da pousada", portrait=False, seconds=45)
    window = json.dumps({"scenes": [{"id": "Quarto", "layout": "shot", "image": "a cozy room", "focus": [900, 500, 1.2], "text": "Veja."},
                                    {"id": "sem", "layout": "shot", "text": "Sem foto."}, {"id": "fim", "layout": "outro", "text": "Tchau."}]})
    scenes = chat_video.parse_script(window, portrait=False)["scenes"]
    assert scenes[0]["shots"] == [{"shot": "gen-quarto", "focus": [900.0, 500.0, 1.2]}] and "focus" not in scenes[0]
    assert scenes[1]["layout"] == "photo"
