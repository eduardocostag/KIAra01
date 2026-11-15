"""Kiara video service (Debian, 127.0.0.1:8891, reachable only through the gateway's /video route).

The server has no GPU, so the heavy models run elsewhere and this service only orchestrates, queues and
normalizes. Engines, best first; each one that fails hands over to the next:

1. Pollinations (paid, only when POLLINATIONS_KEY is set): Veo, Seedance, Kling, Wan...
2. Wan 2.2 image-to-video on a Hugging Face ZeroGPU Space (only with HF_TOKEN: anonymous quota is too small)
3. LTX-Video on a Hugging Face ZeroGPU Space: animates Kiara's picture, or straight from the text
4. Always available: Kiara's picture with a slow camera move (ffmpeg on this machine)

Every result is re-encoded to H.264 MP4 under 3 MB (the Vercel API relays it as base64). Jobs run one at a time.
"""
from __future__ import annotations

import base64
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.getenv("VIDEO_DATA", "/data"))
JOBS, FILES, WORK = DATA / "jobs", DATA / "files", DATA / "work"
GATEWAY = os.getenv("KIARA_GATEWAY_URL", "http://127.0.0.1:8088")
GATEWAY_TOKEN = os.getenv("KIARA_GATEWAY_TOKEN", "")
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
POLLINATIONS_KEY = os.getenv("POLLINATIONS_KEY", "").strip()
POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "bytedance/seedance-1-pro-fast")
IMAGE_MODELS = [m.strip() for m in os.getenv("KIARA_IMAGE_MODELS", "antigravity/gemini-3.1-flash-image,codex/gpt-image-2").split(",") if m.strip()]
WAN_SPACE = os.getenv("WAN_SPACE", "zerogpu-aoti/wan2-2-fp8da-aoti-faster")
LTX_SPACE = os.getenv("LTX_SPACE", "Lightricks/ltx-video-distilled")
KEEP_HOURS = 72
MAX_QUEUE = 12
MAX_BYTES = 3_000_000  # base64 in JSON must stay under Vercel's 4.5 MB response limit
NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted, watermark, text"
ID = re.compile(r"^[0-9a-f]{32}$")

pending: queue.Queue[str] = queue.Queue()
lock = threading.Lock()


# ---------- job storage ----------

def job_path(job_id: str) -> Path:
    return JOBS / f"{job_id}.json"


def load(job_id: str) -> dict | None:
    try:
        return json.loads(job_path(job_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(job: dict) -> None:
    tmp = job_path(job["id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    tmp.replace(job_path(job["id"]))


def update(job: dict, **changes) -> None:
    with lock:
        job.update(changes, updated_at=time.time())
        save(job)


def public(job: dict) -> dict:
    keys = ("id", "status", "progress", "message", "title", "duration", "error", "engine", "warnings")
    return {key: job.get(key) for key in keys}


def cleanup() -> None:
    limit = time.time() - KEEP_HOURS * 3600
    for folder in (JOBS, FILES):
        for item in folder.glob("*"):
            if item.stat().st_mtime < limit:
                item.unlink(missing_ok=True)
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)


# ---------- media helpers ----------

def run(cmd: list[str], timeout: int = 240) -> None:
    subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)


def probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return round(float(out), 1)
    except (ValueError, subprocess.SubprocessError):
        return None


def normalize(source: Path, target: Path, portrait: bool) -> None:
    """H.264 MP4 at most 720p, small enough to relay through Vercel."""
    scale = "scale='min(720,iw)':-2" if portrait else "scale=-2:'min(720,ih)'"
    for crf in (24, 28, 32):
        run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-vf", f"{scale},fps=30,format=yuv420p", "-an",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-movflags", "+faststart", str(target)])
        if target.stat().st_size <= MAX_BYTES:
            return
    raise RuntimeError("video_too_large")


def kiara_image(prompt: str, folder: Path) -> Path | None:
    """A picture from Kiara's own image models (through the gateway), used as the first frame."""
    for model in IMAGE_MODELS:
        try:
            body = json.dumps({"model": model, "prompt": prompt[:3000], "n": 1, "size": "1024x1024"}).encode()
            request = urllib.request.Request(f"{GATEWAY}/ai/v1/images/generations", data=body, method="POST", headers={
                "Authorization": f"Bearer {GATEWAY_TOKEN}", "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=90) as response:
                item = (json.load(response).get("data") or [{}])[0]
            raw = base64.b64decode(item.get("b64_json") or "")
            if raw:
                path = folder / ("frame.png" if raw[:4] == b"\x89PNG" else "frame.jpg")
                path.write_bytes(raw)
                return path
        except Exception:  # noqa: BLE001 - next image model
            continue
    return None


def video_from(result) -> Path:
    first = result[0] if isinstance(result, (list, tuple)) else result
    path = first.get("video") if isinstance(first, dict) else first
    if not path or not Path(path).is_file():
        raise RuntimeError("no_video")
    return Path(path)


# ---------- engines ----------

def engine_pollinations(job: dict, image: Path | None, folder: Path) -> Path:
    if not POLLINATIONS_KEY:
        raise RuntimeError("not_configured")
    query = {"model": POLLINATIONS_MODEL, "duration": str(job["seconds"]), "aspectRatio": "9:16" if job["portrait"] else "16:9"}
    url = "https://gen.pollinations.ai/video/" + urllib.parse.quote(job["prompt"][:1500], safe="") + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {POLLINATIONS_KEY}"})
    with urllib.request.urlopen(request, timeout=300) as response:
        if not response.headers.get("Content-Type", "").startswith("video/"):
            raise RuntimeError("not_video")
        out = folder / "pollinations.mp4"
        out.write_bytes(response.read(80_000_000))
    return out


def _client(space: str, folder: Path):
    from gradio_client import Client
    return Client(space, token=HF_TOKEN, verbose=False, download_files=str(folder))


def engine_wan(job: dict, image: Path | None, folder: Path) -> Path:
    if not HF_TOKEN or image is None:
        raise RuntimeError("needs_token_and_image")
    from gradio_client import handle_file
    result = _client(WAN_SPACE, folder).predict(
        input_image=handle_file(str(image)), prompt=job["prompt"], steps=6,
        duration_seconds=min(5.0, float(job["seconds"])), api_name="/generate_video")
    return video_from(result)


def engine_ltx(job: dict, image: Path | None, folder: Path) -> Path:
    from gradio_client import handle_file
    height, width = (704, 512) if job["portrait"] else (512, 704)
    common = dict(negative_prompt=NEGATIVE, input_video_filepath=None, height_ui=height, width_ui=width,
                  duration_ui=min(8.0, float(job["seconds"])), ui_frames_to_use=9, seed_ui=42, randomize_seed=True,
                  ui_guidance_scale=1, improve_texture_flag=True)
    client = _client(LTX_SPACE, folder)
    if image is not None:
        try:
            return video_from(client.predict(prompt=job["prompt"], input_image_filepath=handle_file(str(image)),
                                             mode="image-to-video", api_name="/image_to_video", **common))
        except Exception:  # noqa: BLE001 - try straight from the text
            pass
    return video_from(client.predict(prompt=job["prompt"], input_image_filepath=None, mode="text-to-video",
                                     api_name="/text_to_video", **common))


def engine_camera(job: dict, image: Path | None, folder: Path) -> Path:
    """Kiara's picture with a slow zoom and drift; needs only ffmpeg."""
    if image is None:
        raise RuntimeError("no_image")
    seconds = max(3, min(10, int(job["seconds"])))
    frames = seconds * 30
    w, h = (720, 1280) if job["portrait"] else (1280, 720)
    out = folder / "camera.mp4"
    # Cover-crop to the target shape at 2x (smooth sub-pixel motion), then a slow push-in with a gentle drift.
    zoom = (f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase:flags=lanczos,crop={w * 2}:{h * 2},"
            f"zoompan=z='1+0.16*on/{frames}':x='(iw-iw/zoom)*(0.5+0.2*on/{frames})':y='(ih-ih/zoom)/2':d={frames}:s={w}x{h}:fps=30,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={seconds - 0.6}:d=0.6")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(image), "-vf", zoom, "-frames:v", str(frames), "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", str(out)], timeout=300)
    return out


ENGINES = (("pollinations", engine_pollinations, "Gerando o vídeo"), ("wan", engine_wan, "Animando a imagem"),
           ("ltx", engine_ltx, "Gerando o vídeo"), ("camera", engine_camera, "Montando o vídeo"))


# ---------- worker ----------

def process(job: dict) -> None:
    folder = WORK / job["id"]
    folder.mkdir(parents=True, exist_ok=True)
    try:
        update(job, status="running", progress=0.1, message="Criando a primeira imagem")
        image = kiara_image(job["image_prompt"], folder)
        for index, (name, engine, label) in enumerate(ENGINES):
            update(job, progress=0.2 + 0.15 * index, message=label)
            try:
                raw = engine(job, image, folder)
                target = FILES / f"{job['id']}.mp4"
                normalize(raw, target, job["portrait"])
                warnings = [] if name != "camera" else ["Os geradores de vídeo estavam sem cota; o vídeo usa a imagem da Kiara com movimento de câmera."]
                update(job, status="done", progress=1.0, message="Pronto", engine=name, duration=probe_duration(target), warnings=warnings)
                return
            except Exception as error:  # noqa: BLE001 - next engine
                job.setdefault("tries", []).append(f"{name}: {type(error).__name__}: {str(error)[:160]}")
        update(job, status="failed", progress=1.0, message="Falhou", error="Não consegui gerar o vídeo agora. Tente de novo em alguns minutos.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def worker() -> None:
    while True:
        job_id = pending.get()
        job = load(job_id)
        if job:
            try:
                process(job)
            except Exception:  # noqa: BLE001 - one bad job never stops the queue
                update(job, status="failed", progress=1.0, error="Não consegui gerar o vídeo agora.")


def janitor() -> None:
    while True:
        time.sleep(3600)
        try:
            limit = time.time() - KEEP_HOURS * 3600
            for folder in (JOBS, FILES):
                for item in folder.glob("*"):
                    if item.stat().st_mtime < limit:
                        item.unlink(missing_ok=True)
        except OSError:
            pass


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "kiara-video"

    def log_message(self, *_args):  # prompts are private; no access log
        pass

    def send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parts = self.path.split("?")[0].strip("/").split("/")
        if parts == ["healthz"]:
            return self.send(200, {"ok": True, "queue": pending.qsize()})
        if len(parts) >= 2 and parts[0] == "jobs" and ID.fullmatch(parts[1]):
            job = load(parts[1])
            if not job:
                return self.send(404, {"error": "not_found"})
            if len(parts) == 2:
                return self.send(200, public(job))
            if parts[2:] == ["file"] and job.get("status") == "done":
                data = (FILES / f"{parts[1]}.mp4").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        return self.send(404, {"error": "not_found"})

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0].strip("/") != "jobs":
            return self.send(404, {"error": "not_found"})
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 16000)) or b"{}")
            prompt = str(body.get("prompt", "")).strip()[:2000]
            assert len(prompt) >= 3
        except (ValueError, AssertionError):
            return self.send(400, {"error": "invalid_prompt"})
        if pending.qsize() >= MAX_QUEUE:
            return self.send(429, {"error": "queue_full"})
        job = {"id": uuid.uuid4().hex, "status": "queued", "progress": 0.0, "message": "Na fila", "error": None,
               "title": str(body.get("title") or "Vídeo da Kiara")[:120], "duration": None, "engine": None, "warnings": [],
               "prompt": prompt, "image_prompt": str(body.get("image_prompt") or prompt)[:3000],
               "seconds": max(2, min(10, int(body.get("seconds") or 5))), "portrait": bool(body.get("portrait")),
               "created_at": time.time()}
        with lock:
            save(job)
        pending.put(job["id"])
        ahead = pending.qsize() - 1
        if ahead > 0:
            update(job, message=f"Na fila ({ahead} na frente)")
        return self.send(202, public(job))


def main() -> None:
    for folder in (JOBS, FILES, WORK):
        folder.mkdir(parents=True, exist_ok=True)
    cleanup()
    for path in JOBS.glob("*.json"):  # jobs interrupted by a restart
        job = load(path.stem)
        if job and job.get("status") in {"queued", "running"}:
            update(job, status="failed", progress=1.0, error="O servidor reiniciou durante a geração. Peça de novo.")
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=janitor, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", int(os.getenv("PORT", "8891"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
