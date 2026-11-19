"""Kiara image generation through the Debian gateway (OmniRoute image models).

Each model in the chain is a different account, so when one runs out of quota the next one answers.
The picture always leaves as a JPEG under ~1 MB: Vercel responses are capped at 4.5 MB and the
GPT image model only returns large PNGs.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import time

# Measured 2026-11-14 via the gateway: Gemini ~10 s (JPEG), GPT Image 2 ~18 s (PNG ~3 MB).
# 2026-11-18 both were out (Gemini quota for 3 h, ChatGPT login expired) and every image failed, so the chain now
# goes on to the Gemini API account and, last, the free AI Horde network (Flux, ~16 s when its queue is short).
# 2026-11-19: no ChatGPT plan, so codex is out; Cloudflare Workers AI (FLUX.2 klein, ~104 of the 10k free daily neurons
# per 1024px image, ~95 a day) comes right after Gemini. Cloudflare models are skipped while its account is not set.
DEFAULT_IMAGE_MODELS = ("antigravity/gemini-3.1-flash-image", "cloudflare/@cf/black-forest-labs/flux-2-klein-4b",
                        "gemini/gemini-3.1-flash-image", "cloudflare/@cf/black-forest-labs/flux-1-schnell",
                        "aihorde/Flux.1-Schnell fp8 (Compact)")
CLOUDFLARE = "cloudflare/"
IMAGE_DEADLINE_SECONDS = 100
MAX_IMAGE_BYTES = 12_000_000
MAX_SIDE = 1536
# What the chat model writes when the person asks for a picture; the API swaps it for the real image.
MARKER = re.compile(r"\[\[\s*IMAGEM\s*:\s*(.+?)\s*\]\]", re.DOTALL | re.IGNORECASE)

IMAGE_STYLE = (
    "Você também cria imagens. Quando a pessoa pedir uma imagem, foto, ilustração, desenho, logo ou arte (ou pedir "
    "para ajustar uma imagem que você já criou nesta conversa), escreva uma frase curta e natural e, em seguida, "
    "uma linha exatamente assim: [[IMAGEM: descrição completa e visual da imagem, com assunto, estilo, cores, "
    "enquadramento e luz]]. Ao ajustar uma imagem anterior, descreva a imagem inteira de novo com a mudança pedida. "
    "Nunca diga que não consegue gerar imagens e nunca invente links. Só use a marcação quando a pessoa realmente "
    "quiser uma imagem (para vídeo, use a marcação de vídeo quando ela existir)."
)


def cloudflare_configuration() -> tuple[str, str]:
    return os.getenv("KIARA_CLOUDFLARE_ACCOUNT_ID", "").strip(), os.getenv("KIARA_CLOUDFLARE_API_TOKEN", "").strip()


def image_models() -> list[str]:
    configured = [item.strip() for item in os.getenv("KIARA_IMAGE_MODELS", "").split(",") if item.strip()]
    models = configured or list(DEFAULT_IMAGE_MODELS)
    if not all(cloudflare_configuration()):
        models = [model for model in models if not model.startswith(CLOUDFLARE)]
    return models


def cloudflare_image(model: str, prompt: str, timeout: float, width: int = 1024, height: int = 1024) -> bytes:
    """Workers AI REST: FLUX.2 models take a multipart form, the older ones JSON; both answer result.image (base64)."""
    import urllib.request
    import uuid

    account, token = cloudflare_configuration()
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if "/flux-2" in model:
        boundary = uuid.uuid4().hex
        fields = {"prompt": prompt[:2000], "width": str(width), "height": str(height)}
        body = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
                        for name, value in fields.items()) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        body = json.dumps({"prompt": prompt[:2000], "steps": 6, "width": width, "height": height}).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        answer = json.loads(response.read(MAX_IMAGE_BYTES * 2))
    raw = base64.b64decode((answer.get("result") or {}).get("image") or "")
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise RuntimeError("image_invalid")
    return raw


def image_available() -> bool:
    from .server_gateway import gateway_configuration
    return bool(gateway_configuration()[0])


def to_jpeg(raw: bytes) -> bytes:
    """Any model output (PNG, WebP, JPEG) as a JPEG of at most MAX_SIDE pixels."""
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as source:
        image = source.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE))
        output = io.BytesIO()
        image.save(output, "JPEG", quality=86, optimize=True, progressive=True)
    return output.getvalue()


def _request(model: str, prompt: str, timeout: float) -> bytes:
    import urllib.request

    if model.startswith(CLOUDFLARE):
        return cloudflare_image(model[len(CLOUDFLARE):], prompt, timeout)
    from .server_gateway import _opener, gateway_configuration
    base, token = gateway_configuration()
    if not base:
        raise RuntimeError("gateway_not_configured")
    payload = json.dumps({"model": model, "prompt": prompt, "n": 1, "size": "1024x1024"}).encode("utf-8")
    request = urllib.request.Request(f"{base}/ai/v1/images/generations", data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
    with _opener.open(request, timeout=timeout) as response:
        body = response.read(MAX_IMAGE_BYTES * 2)
    item = (json.loads(body).get("data") or [{}])[0]
    encoded = item.get("b64_json") or ""
    if not encoded and str(item.get("url", "")).startswith("data:image/"):
        encoded = item["url"].split(",", 1)[1]
    raw = base64.b64decode(encoded) if encoded else b""
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise RuntimeError("image_invalid")
    return raw


async def generate_image(prompt: str, *, request=None) -> tuple[bytes, str]:
    """Returns (jpeg bytes, model) or (b"", "") when every image model failed; never leaks provider details."""
    send = request or _request
    deadline = time.monotonic() + IMAGE_DEADLINE_SECONDS
    for model in image_models():
        remaining = deadline - time.monotonic()
        if remaining < 5:
            break
        budget = min(remaining, 70)
        try:
            raw = await asyncio.wait_for(asyncio.to_thread(send, model, prompt[:3000], budget), timeout=budget + 2)
            return await asyncio.to_thread(to_jpeg, raw), model
        except Exception:  # noqa: BLE001 - quota, safety refusals and timeouts all fall through to the next model
            continue
    return b"", ""
