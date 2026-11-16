"""Speech to text on the Kiara server (Whisper, open weights, CPU) through the gateway's /stt route.

Used for WhatsApp voice notes: the inbox shows what the person said and the SDR can answer it.
Nothing leaves the Kiara server: no paid transcription API is involved.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
import uuid

from .server_gateway import _opener, gateway_configuration

MAX_AUDIO_BYTES = 8_000_000          # about 8 minutes of WhatsApp voice (opus)
DEFAULT_MODEL = "Systran/faster-whisper-small"


def transcription_model() -> str:
    return os.getenv("KIARA_STT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _multipart(fields: dict[str, str], name: str, filename: str, mime: str, raw: bytes) -> tuple[bytes, str]:
    boundary = "kiara" + uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n".encode() + raw + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _transcribe_sync(raw: bytes, mime: str, timeout: float) -> str:
    base, token = gateway_configuration()
    if not base or not raw or len(raw) > MAX_AUDIO_BYTES:
        return ""
    extension = "ogg" if "ogg" in mime or "opus" in mime else "mp3" if "mpeg" in mime else "m4a" if "mp4" in mime else "wav" if "wav" in mime else "ogg"
    body, content_type = _multipart({"model": transcription_model(), "language": "pt", "response_format": "json"},
                                    "file", f"audio.{extension}", mime or "audio/ogg", raw)
    request = urllib.request.Request(f"{base}/stt/v1/audio/transcriptions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": content_type})
    try:
        with _opener.open(request, timeout=timeout) as response:
            data = json.loads(response.read(200_000))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return ""
    text = data.get("text") if isinstance(data, dict) else ""
    return " ".join(str(text or "").split())[:4000]


async def transcribe(raw: bytes, mime: str = "audio/ogg", *, timeout: float = 40) -> str:
    """The words in an audio clip (Portuguese), or "" when the server cannot transcribe it now."""
    return await asyncio.to_thread(_transcribe_sync, raw, mime, timeout)
