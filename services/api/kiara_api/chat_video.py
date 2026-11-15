"""Kiara video generation: jobs run on the Debian video service (kiara-video) behind the gateway's /video route.

The API starts a job, relays its status and hands the finished MP4 (at most 3 MB) to the site as base64.
Video models understand English best, so the chat model (or a quick translation here) writes the prompt in English.
"""
from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from typing import Any

JOB_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_VIDEO_BYTES = 3_200_000
# [[VIDEO: ...]] or [[VIDEO vertical 8s: ...]] written by the chat model; the API swaps it for a real job.
MARKER = re.compile(r"\[\[\s*V[IÍ]DEO\b(?P<options>[^:\]]*):\s*(?P<prompt>.+?)\s*\]\]", re.DOTALL | re.IGNORECASE)

VIDEO_STYLE = (
    "Você também cria vídeos curtos, sem som, de até 10 segundos. Quando a pessoa pedir um vídeo, clipe ou animação, "
    "escreva uma frase curta avisando que vai preparar o vídeo (leva cerca de um minuto) e, em seguida, uma linha "
    "exatamente assim: [[VIDEO horizontal 5s: cinematic description in English with subject, action, camera movement, "
    "light and style]]. Use vertical para Instagram, Reels, TikTok, Stories ou celular, e horizontal nos outros casos; "
    "a duração vai de 3s a 10s (5s se a pessoa não disser). Vídeos longos com narração, música ou vários trechos você "
    "ainda não faz: explique isso em uma frase e ofereça um clipe curto. Só use a marcação quando a pessoa realmente "
    "quiser um vídeo."
)


def video_available() -> bool:
    from .server_gateway import gateway_configuration
    return bool(gateway_configuration()[0])


def parse_options(options: str) -> tuple[bool, int]:
    portrait = bool(re.search(r"vertical|portrait|9:16|retrato", options, re.IGNORECASE))
    seconds = re.search(r"(\d{1,2})\s*s", options)
    return portrait, max(3, min(10, int(seconds.group(1)))) if seconds else 5


def job_request(prompt: str, *, portrait: bool, seconds: int, title: str = "") -> dict[str, Any]:
    framing = "vertical composition, subject centered" if portrait else "wide composition, subject centered"
    return {"prompt": prompt[:2000], "image_prompt": f"{prompt[:2500]}. {framing}, cinematic still frame, highly detailed",
            "seconds": seconds, "portrait": portrait, "title": (title or "Vídeo da Kiara")[:120]}


def _call(method: str, path: str, body: dict | None = None, timeout: float = 30, limit: int = 1_000_000) -> Any:
    from .server_gateway import _opener, gateway_configuration
    base, token = gateway_configuration()
    if not base:
        raise RuntimeError("gateway_not_configured")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{base}/video{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with _opener.open(request, timeout=timeout) as response:
            raw = response.read(limit + 1)
            kind = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"video_service_{error.code}") from None
    if len(raw) > limit:
        raise RuntimeError("video_service_response_too_large")
    return raw if kind.startswith("video/") else json.loads(raw)


def public_job(job: Any) -> dict[str, Any]:
    if not isinstance(job, dict) or not JOB_ID.fullmatch(str(job.get("id", ""))):
        raise RuntimeError("video_service_invalid")
    return {"id": job["id"], "status": job.get("status") if job.get("status") in {"queued", "running", "done", "failed"} else "failed",
            "progress": job.get("progress") or 0, "message": str(job.get("message") or "")[:200],
            "title": str(job.get("title") or "Vídeo da Kiara")[:120], "duration": job.get("duration"),
            "warnings": [str(item)[:300] for item in (job.get("warnings") or [])][:5], "error": job.get("error")}


async def start_video(prompt: str, *, portrait: bool = False, seconds: int = 5, title: str = "") -> dict[str, Any]:
    job = await asyncio.to_thread(_call, "POST", "/jobs", job_request(prompt, portrait=portrait, seconds=seconds, title=title))
    return public_job(job)


async def video_status(job_id: str) -> dict[str, Any]:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("invalid_job")
    return public_job(await asyncio.to_thread(_call, "GET", f"/jobs/{job_id}", None, 15))


async def video_file(job_id: str) -> bytes:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError("invalid_job")
    data = await asyncio.to_thread(_call, "GET", f"/jobs/{job_id}/file", None, 60, MAX_VIDEO_BYTES)
    if not isinstance(data, bytes):
        raise RuntimeError("video_not_ready")
    return data


PLAN_PROMPT = (
    "Transforme o pedido de vídeo abaixo em JSON, sem texto fora do JSON: "
    '{"prompt": "cinematic description in English (subject, action, camera movement, light, style)", '
    '"portrait": true se for para Instagram/Reels/TikTok/Stories/celular ou pedir vertical, senão false, '
    '"seconds": duração de 3 a 10 (5 se não disser), "title": "título curto em português"}'
)


def parse_plan(text: str, fallback: str) -> tuple[str, bool, int, str]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
    except ValueError:
        data = {}
    prompt = str(data.get("prompt") or "").strip() or fallback
    try:
        seconds = max(3, min(10, int(data.get("seconds") or 5)))
    except (TypeError, ValueError):
        seconds = 5
    return prompt[:2000], bool(data.get("portrait")), seconds, str(data.get("title") or "")[:120]
