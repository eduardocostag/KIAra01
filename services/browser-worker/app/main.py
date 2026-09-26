from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from playwright.async_api import BrowserContext, Page, async_playwright
from .instagram import InstagramSessionFailure


INSTAGRAM_LOGIN = "https://www.instagram.com/accounts/login/"
USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


class SessionCreate(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=200)


class BrowserInput(BaseModel):
    action: Literal["click", "type", "key", "scroll", "reload"]
    x: float | None = None
    y: float | None = None
    text: str | None = Field(default=None, max_length=500)
    key: str | None = Field(default=None, max_length=40)
    delta_y: float | None = Field(default=None, ge=-3000, le=3000)


class ProfileRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=1, max_length=31)


class AnalysisRequest(BaseModel):
    workspace_id: str = Field(min_length=1, max_length=200)
    mode: Literal["commenters", "likers", "post_audience"]
    username: str = Field(min_length=1, max_length=500)
    media_id: str = Field(min_length=1, max_length=160)
    limit: int = Field(default=100, ge=1, le=100)


@dataclass
class LiveSession:
    id: str
    workspace_id: str
    context: BrowserContext
    page: Page
    lock: asyncio.Lock
    last_activity: float


class BrowserSessions:
    def __init__(self) -> None:
        self.data_dir = Path(os.getenv("KIARA_BROWSER_DATA_DIR", "/data"))
        self.profile_root = self.data_dir / "profiles"
        self.profile_root.mkdir(parents=True, exist_ok=True)
        self.executable = os.getenv("KIARA_CHROMIUM_PATH") or None
        self._playwright = None
        self._sessions: dict[str, LiveSession] = {}
        self._workspace_sessions: dict[str, str] = {}
        self._guard = asyncio.Lock()

    def profile_path(self, workspace_id: str) -> Path:
        salt = os.getenv("KIARA_PROFILE_SALT") or os.getenv("KIARA_WORKER_TOKEN", "")
        digest = hmac.new(salt.encode(), workspace_id.encode(), hashlib.sha256).hexdigest()
        return self.profile_root / digest

    async def start(self, workspace_id: str) -> LiveSession:
        async with self._guard:
            current_id = self._workspace_sessions.get(workspace_id)
            if current_id and current_id in self._sessions:
                session = self._sessions[current_id]
                session.last_activity = time.monotonic()
                return session
            # Expira sessões abandonadas após 10 minutos para não bloquear outros usuários.
            stale = [
                session_id
                for session_id, session in self._sessions.items()
                if time.monotonic() - session.last_activity > 600
            ]
            for session_id in stale:
                session = self._sessions.pop(session_id)
                self._workspace_sessions.pop(session.workspace_id, None)
                await session.context.close()
            if self._sessions:
                raise HTTPException(429, "O navegador está atendendo outra conexão. Tente novamente em instantes.")
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            profile = self.profile_path(workspace_id)
            profile.mkdir(parents=True, exist_ok=True)
            launch_args = {
                "headless": True,
                "viewport": {"width": 1280, "height": 800},
                "locale": "pt-BR",
                "timezone_id": "America/Sao_Paulo",
                "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            }
            if self.executable:
                launch_args["executable_path"] = self.executable
            context = await self._playwright.chromium.launch_persistent_context(
                str(profile),
                **launch_args,
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(INSTAGRAM_LOGIN, wait_until="domcontentloaded", timeout=45_000)
            session = LiveSession(
                uuid4().hex,
                workspace_id,
                context,
                page,
                asyncio.Lock(),
                time.monotonic(),
            )
            self._sessions[session.id] = session
            self._workspace_sessions[workspace_id] = session.id
            return session

    def get(self, session_id: str, workspace_id: str) -> LiveSession:
        session = self._sessions.get(session_id)
        if not session or not hmac.compare_digest(session.workspace_id, workspace_id):
            raise HTTPException(404, "A tela de conexão expirou. Abra uma nova conexão.")
        session.last_activity = time.monotonic()
        return session

    async def close(self, session_id: str) -> None:
        async with self._guard:
            session = self._sessions.pop(session_id, None)
            if not session:
                return
            self._workspace_sessions.pop(session.workspace_id, None)
            await session.context.close()

    async def cookies(self, workspace_id: str) -> list[dict]:
        current_id = self._workspace_sessions.get(workspace_id)
        if current_id and current_id in self._sessions:
            return await self._sessions[current_id].context.cookies("https://www.instagram.com")
        session = await self.start(workspace_id)
        try:
            return await session.context.cookies("https://www.instagram.com")
        finally:
            await self.close(session.id)

    async def disconnect(self, workspace_id: str) -> None:
        current_id = self._workspace_sessions.get(workspace_id)
        if current_id:
            await self.close(current_id)
        profile = self.profile_path(workspace_id)
        if profile.exists():
            import shutil
            await asyncio.to_thread(shutil.rmtree, profile)


sessions = BrowserSessions()
app = FastAPI(title="Kiara Browser Worker", version="1.0.0")


@app.exception_handler(InstagramSessionFailure)
async def instagram_failure_handler(_request: Request, error: InstagramSessionFailure):
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.message, "code": error.code},
    )


def authorize(x_kiara_worker_token: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("KIARA_WORKER_TOKEN", "")
    if not expected:
        raise HTTPException(503, "Worker sem chave configurada.")
    if not x_kiara_worker_token or not hmac.compare_digest(x_kiara_worker_token, expected):
        raise HTTPException(401, "Acesso não autorizado.")


async def instagram_cookie(workspace_id: str) -> str:
    cookies = await sessions.cookies(workspace_id)
    session_id = next(
        (str(cookie["value"]) for cookie in cookies if cookie.get("name") == "sessionid"),
        "",
    )
    if not session_id:
        return ""
    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if cookie.get("name") and cookie.get("value")
    )


@app.get("/health/live")
async def live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready", dependencies=[Depends(authorize)])
async def ready() -> dict:
    return {"status": "ready", "active_sessions": len(sessions._sessions)}


@app.post("/v1/sessions", dependencies=[Depends(authorize)])
async def create_session(payload: SessionCreate) -> dict:
    session = await sessions.start(payload.workspace_id)
    return {"session_id": session.id, "status": "awaiting_login"}


@app.get("/v1/sessions/{session_id}", dependencies=[Depends(authorize)])
async def session_status(session_id: str, workspace_id: str) -> dict:
    session = sessions.get(session_id, workspace_id)
    cookies = await session.context.cookies("https://www.instagram.com")
    connected = any(cookie.get("name") == "sessionid" and cookie.get("value") for cookie in cookies)
    return {"session_id": session.id, "connected": connected, "url": session.page.url}


@app.get("/v1/sessions/{session_id}/screenshot", dependencies=[Depends(authorize)])
async def screenshot(session_id: str, workspace_id: str) -> Response:
    session = sessions.get(session_id, workspace_id)
    async with session.lock:
        image = await session.page.screenshot(type="jpeg", quality=76)
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/v1/sessions/{session_id}/input", dependencies=[Depends(authorize)])
async def browser_input(session_id: str, payload: BrowserInput, workspace_id: str) -> dict:
    session = sessions.get(session_id, workspace_id)
    async with session.lock:
        if payload.action == "click" and payload.x is not None and payload.y is not None:
            await session.page.mouse.click(payload.x, payload.y)
        elif payload.action == "type" and payload.text is not None:
            await session.page.keyboard.type(payload.text, delay=35)
        elif payload.action == "key" and payload.key:
            await session.page.keyboard.press(payload.key)
        elif payload.action == "scroll":
            await session.page.mouse.wheel(0, payload.delta_y or 500)
        elif payload.action == "reload":
            await session.page.reload(wait_until="domcontentloaded")
        else:
            raise HTTPException(422, "Comando de navegador incompleto.")
    return {"ok": True}


@app.post("/v1/sessions/{session_id}/complete", dependencies=[Depends(authorize)])
async def complete_login(session_id: str, workspace_id: str) -> dict:
    session = sessions.get(session_id, workspace_id)
    cookies = await session.context.cookies("https://www.instagram.com")
    session_id_value = next((str(c["value"]) for c in cookies if c.get("name") == "sessionid"), "")
    if not session_id_value:
        raise HTTPException(409, "Conclua o login no Instagram antes de continuar.")
    await sessions.close(session_id)
    return {"connected": True}


@app.get("/v1/profiles/{workspace_id}/status", dependencies=[Depends(authorize)])
async def profile_status(workspace_id: str) -> dict:
    value = await instagram_cookie(workspace_id)
    return {"connected": bool(value)}


@app.delete("/v1/profiles/{workspace_id}", status_code=204, dependencies=[Depends(authorize)])
async def disconnect_profile(workspace_id: str) -> Response:
    await sessions.disconnect(workspace_id)
    return Response(status_code=204)


@app.post("/v1/instagram/profile", dependencies=[Depends(authorize)])
async def instagram_profile(payload: ProfileRequest) -> dict:
    from .instagram import load_instagram_profile
    username = payload.username.removeprefix("@").strip()
    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(422, "Informe um @ válido do Instagram.")
    cookie = await instagram_cookie(payload.workspace_id)
    if not cookie:
        raise HTTPException(409, "Conecte o Instagram antes de carregar o perfil.")
    return await asyncio.to_thread(load_instagram_profile, cookie, username)


@app.post("/v1/instagram/analyse", dependencies=[Depends(authorize)])
async def instagram_analyse(payload: AnalysisRequest) -> dict:
    from .instagram import collect_instagram_relationships
    cookie = await instagram_cookie(payload.workspace_id)
    if not cookie:
        raise HTTPException(409, "A conexão com o Instagram expirou. Entre novamente.")
    items, snapshot = await asyncio.to_thread(
        collect_instagram_relationships,
        cookie,
        payload.mode,
        payload.username,
        media_id=payload.media_id,
        limit=payload.limit,
    )
    return {"items": items, "snapshot": snapshot}
