"""Client for the Kiara gateway on the always-on Debian server (OmniRoute + OpenWA behind Tailscale Funnel).

The Vercel API holds one secret, `KIARA_SERVER_GATEWAY_TOKEN`; the gateway injects the real OmniRoute and
OpenWA keys on the server. Only HTTPS, no redirects, short timeouts, and errors never carry bodies or keys.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Response

from .http.context import RequestContext
from .http.dependencies import system_administrator_context

TIMEOUT_SECONDS = 8
MAX_BODY = 512 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003 - urllib signature
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def gateway_configuration() -> tuple[str, str]:
    """(base_url, token) when the gateway is configured with a safe HTTPS URL, else ("", "")."""
    base = os.getenv("KIARA_SERVER_GATEWAY_URL", "").strip().rstrip("/")
    token = os.getenv("KIARA_SERVER_GATEWAY_TOKEN", "").strip()
    if not base or not token:
        return "", ""
    try:
        parsed = urlsplit(base)
        _ = parsed.port
    except ValueError:
        return "", ""
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return "", ""
    return base, token


def _get(url: str, token: str | None) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with _opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_BODY + 1)
            status = response.status
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None
    if len(raw) > MAX_BODY:
        return status, None
    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, None


def _state(status: int) -> str:
    if status == 200:
        return "ok"
    if status == 0:
        return "unreachable"
    if status in (401, 403):
        return "unauthorized"
    return f"http_{status}"


def _session_summary(data: Any) -> list[dict[str, str]]:
    items = data if isinstance(data, list) else (data or {}).get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [{"name": str(item.get("name", ""))[:80], "status": str(item.get("status", "unknown"))[:40]} for item in items[:20] if isinstance(item, dict)]


def _model_ids(data: Any) -> list[str]:
    items = (data or {}).get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [str(item["id"])[:120] for item in items[:200] if isinstance(item, dict) and item.get("id")]


async def server_status() -> dict[str, Any]:
    base, token = gateway_configuration()
    if not base:
        return {"configured": False}
    gateway, ai, whatsapp, sessions = await asyncio.gather(
        asyncio.to_thread(_get, f"{base}/healthz", None),
        asyncio.to_thread(_get, f"{base}/ai/v1/models", token),
        asyncio.to_thread(_get, f"{base}/wa/api/health", token),
        asyncio.to_thread(_get, f"{base}/wa/api/sessions", token),
    )
    return {
        "configured": True,
        "gateway": _state(gateway[0]),
        "ai": {"state": _state(ai[0]), "models": _model_ids(ai[1])},
        "whatsapp": {"state": _state(whatsapp[0]), "sessions": _session_summary(sessions[1]) if sessions[0] == 200 else []},
    }


def create_server_gateway_router() -> APIRouter:
    router = APIRouter(prefix="/v1/server", tags=["server"])

    @router.get("/status")
    async def status(response: Response, _context: Annotated[RequestContext, Depends(system_administrator_context)]):
        response.headers["Cache-Control"] = "no-store, private"
        return await server_status()

    return router
