from __future__ import annotations

import asyncio
import base64
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from .browser_worker import BrowserWorkerClient, BrowserWorkerError
from .competition_store import CompetitionRepository
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError


KiaraCompetitionMode = Literal["followers", "commenters", "likers", "post_audience"]


class KiaraCompetitionInput(BaseModel):
    mode: KiaraCompetitionMode
    target: str = Field(min_length=1, max_length=500)
    media_id: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("target", "media_id", "name")
    @classmethod
    def trim_kiara_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class BrowserInputCommand(BaseModel):
    action: Literal["click", "type", "key", "scroll", "reload"]
    x: float | None = None
    y: float | None = None
    text: str | None = Field(default=None, max_length=500)
    key: str | None = Field(default=None, max_length=40)
    delta_y: float | None = Field(default=None, ge=-3000, le=3000)


def _browser_error(error: BrowserWorkerError) -> ApiError:
    return ApiError(error.status_code, error.code, error.message)


class InstagramProfilePreviewInput(BaseModel):
    username: str = Field(min_length=1, max_length=31)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        return value.strip()


_INSTAGRAM_RESERVED_PATHS = {
    "about", "accounts", "api", "challenge", "developer", "directory", "direct",
    "emails", "explore", "legal", "p", "privacy", "reel", "reels", "stories", "web",
}


def _kiara_public_target(payload: KiaraCompetitionInput) -> tuple[str, str | None]:
    if payload.mode in {"commenters", "likers", "post_audience"}:
        parsed = urlsplit(payload.target)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme != "https" or host != "instagram.com" or not re.fullmatch(r"/(?:p|reel)/[A-Za-z0-9_-]+/?", parsed.path):
            raise ApiError(422, "instagram_post_url_invalid", "Cole o link HTTPS de uma publicação ou Reel público do Instagram.")
        return payload.target, None
    username = payload.target.removeprefix("@").strip()
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username) or username.lower() in _INSTAGRAM_RESERVED_PATHS:
        raise ApiError(422, "instagram_username_invalid", "Informe somente o @usuário público do concorrente.")
    return f"https://www.instagram.com/{username}/", username.lower()


def create_competition_router(archive: CompetitionRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/competition", tags=["competition"])

    @router.get("/instagram/connection")
    async def instagram_connection(context: Annotated[RequestContext, Depends(authenticated_context)]):
        client = BrowserWorkerClient()
        try:
            return await asyncio.to_thread(client.profile_status, context.organization_id)
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.post("/instagram/connection", status_code=201)
    async def start_instagram_connection(context: Annotated[RequestContext, Depends(authenticated_context)]):
        client = BrowserWorkerClient()
        try:
            return await asyncio.to_thread(client.create_session, context.organization_id)
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.get("/instagram/connection/{session_id}")
    async def instagram_connection_status(
        session_id: str,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        client = BrowserWorkerClient()
        try:
            return await asyncio.to_thread(client.session_status, context.organization_id, session_id)
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.get("/instagram/connection/{session_id}/screenshot")
    async def instagram_connection_screenshot(
        session_id: str,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        client = BrowserWorkerClient()
        try:
            image = await asyncio.to_thread(client.screenshot, context.organization_id, session_id)
            return {"image": "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")}
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.post("/instagram/connection/{session_id}/input")
    async def instagram_connection_input(
        session_id: str,
        payload: BrowserInputCommand,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        client = BrowserWorkerClient()
        try:
            return await asyncio.to_thread(
                client.input,
                context.organization_id,
                session_id,
                payload.model_dump(exclude_none=True),
            )
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.post("/instagram/connection/{session_id}/complete")
    async def complete_instagram_connection(
        session_id: str,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        client = BrowserWorkerClient()
        try:
            return await asyncio.to_thread(client.complete, context.organization_id, session_id)
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.delete("/instagram/connection", status_code=204)
    async def disconnect_instagram_connection(
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        client = BrowserWorkerClient()
        try:
            await asyncio.to_thread(client.disconnect, context.organization_id)
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.get("/overview")
    async def overview(context: Annotated[RequestContext, Depends(authenticated_context)]):
        local = await archive.list_analyses(context.organization_id)
        return {
            "account": {},
            "analyses": {"items": local},
            "provider": {"available": True, "name": "kiara_instagram"},
        }

    @router.post("/kiara/analyses", status_code=201)
    async def create_kiara_analysis(
        payload: KiaraCompetitionInput,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        normalized_target, normalized_username = _kiara_public_target(payload)
        client = BrowserWorkerClient()
        try:
            result = await asyncio.to_thread(
                client.analyse,
                context.organization_id,
                {
                    "mode": payload.mode,
                    "username": normalized_username or normalized_target,
                    "media_id": payload.media_id,
                    "limit": 100,
                },
            )
            prospects = result.get("items", []) if isinstance(result.get("items"), list) else []
            snapshot = result.get("snapshot", {}) if isinstance(result.get("snapshot"), dict) else {}
        except BrowserWorkerError as error:
            raise _browser_error(error) from None
        analysis_id = f"kiara_{uuid4().hex}"
        name = payload.name or f"Kiara · {payload.mode} · {payload.target}"
        analysis = await archive.upsert_analysis(
            context.organization_id,
            analysis_id,
            {**snapshot, "collected": len(prospects)},
            mode=payload.mode,
            target=payload.target,
            name=name,
            status="completed",
            prospect_count=len(prospects),
            provider="kiara_instagram",
        )
        saved = await archive.upsert_prospects(context.organization_id, analysis_id, prospects)
        message = None if prospects else "Nenhum comentário ou curtida acessível foi encontrado nas publicações consultadas."
        return {"analysis": analysis, "saved": saved, "items": prospects, "message": message}

    @router.post("/kiara/profile-preview")
    async def preview_instagram_profile(
        payload: InstagramProfilePreviewInput,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        username = payload.username.removeprefix("@").strip()
        if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username) or username.lower() in _INSTAGRAM_RESERVED_PATHS:
            raise ApiError(422, "instagram_username_invalid", "Informe um @usuário válido do Instagram.")
        client = BrowserWorkerClient()
        try:
            return await asyncio.to_thread(client.profile, context.organization_id, username)
        except BrowserWorkerError as error:
            raise _browser_error(error) from None

    @router.get("/analyses/{analysis_id}")
    async def get_analysis(
        analysis_id: str,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        local = await archive.get_analysis(context.organization_id, analysis_id)
        if not local:
            raise ApiError(404, "analysis_not_found", "A análise selecionada não foi encontrada.")
        return local

    @router.get("/prospects")
    async def list_prospects(
        context: Annotated[RequestContext, Depends(authenticated_context)],
        analysis_id: str,
        contactable_only: bool = False,
        limit: int = 50,
    ):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        if not 1 <= limit <= 100:
            raise ApiError(422, "prospect_limit_invalid", "O limite deve ficar entre 1 e 100.")
        analysis = await archive.get_analysis(context.organization_id, analysis_id)
        if not analysis:
            raise ApiError(404, "analysis_not_found", "A análise selecionada não foi encontrada.")
        local = await archive.list_prospects(context.organization_id, analysis_id, limit)
        if contactable_only:
            local = [item for item in local if item.get("email") or item.get("phone_number")]
        return {"items": local, "archived": True}

    return router
