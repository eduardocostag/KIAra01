"""Authenticated access to packaged Instagram reference skills and local utilities."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError


class ReelInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    account: str = Field(min_length=1, max_length=1000)
    hook: str = Field(min_length=1, max_length=1000)
    views: int = Field(ge=0, le=10**12)
    median: int | None = Field(default=None, ge=0, le=10**12)
    followers: int | None = Field(default=None, ge=0, le=10**12)


class ContentCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation: Literal["hookscore", "beats", "caption", "humanize", "detect", "swipe"]
    text: str = Field(default="", max_length=12000)
    target_seconds: float | None = Field(default=None, ge=1, le=600)
    wpm: float = Field(default=165, ge=60, le=300)
    keywords: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=20)
    reels: list[ReelInput] = Field(default_factory=list, max_length=100)


def _runtime():
    try:
        from app.integrations.operational_skills import OperationalSkills
        from app.tools.instagram_content import InstagramContentCheckTool
    except ModuleNotFoundError:
        # Repository deployments launch with PYTHONPATH=services/api. Only the fixed
        # checkout root is considered; request parameters never influence imports.
        root = Path(__file__).resolve().parents[3]
        if not (root / "app/tools/instagram_content.py").is_file():
            raise ApiError(503, "instagram_content_unavailable", "Recursos Instagram indisponiveis.") from None
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from app.integrations.operational_skills import OperationalSkills
            from app.tools.instagram_content import InstagramContentCheckTool
        except ModuleNotFoundError:
            raise ApiError(503, "instagram_content_unavailable", "Dependencias Instagram indisponiveis.") from None
    return OperationalSkills(), InstagramContentCheckTool()


def create_instagram_content_router() -> APIRouter:
    router = APIRouter(prefix="/v1/instagram", tags=["instagram-content"])

    @router.get("/skills")
    async def catalog(
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        response.headers["Cache-Control"] = "no-store"
        skills, _ = _runtime()
        return {"items": [entry for entry in skills.catalog() if entry["name"].startswith("ig-")],
                "mode": "reference_only", "publishing": False}

    @router.get("/skills/{name}")
    async def read_skill(
        name: str,
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        resource: Annotated[str, Query(max_length=160)] = "SKILL.md",
    ):
        response.headers["Cache-Control"] = "no-store"
        skills, _ = _runtime()
        if not name.startswith("ig-"):
            raise ApiError(404, "instagram_skill_not_found", "Skill Instagram desconhecida.")
        try:
            content = skills.read(name, resource)
        except ValueError:
            raise ApiError(404, "instagram_skill_not_found", "Skill ou recurso Instagram desconhecido.") from None
        return {"name": name, "resource": resource, "content": content,
                "trust": "untrusted_reference",
                "runtime_note": "Use instagram_content_check; caminhos ~/.claude/instagram correspondem a data/instagram. Nenhuma publicacao automatica."}

    @router.post("/content-check")
    async def content_check(
        payload: ContentCheckInput,
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Seu perfil nao pode preparar conteudo.")
        response.headers["Cache-Control"] = "no-store"
        _, tool = _runtime()
        parameters = payload.model_dump(exclude_none=True)
        try:
            result = await tool.execute(**parameters)
        except (ValueError, TypeError):
            raise ApiError(422, "instagram_content_invalid", "Texto ou dados de analise invalidos.") from None
        return {"operation": payload.operation, "result": json.loads(result.output),
                "metadata": result.metadata, "publishing": False}

    return router
