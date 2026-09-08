from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from ...application.pipeline import PipelineService
from ...ports.pipeline import PipelineRepository
from ..context import RequestContext
from ..dependencies import authenticated_context
from ..errors import ApiError

_ETAG = re.compile(r'^"([1-9][0-9]*)"$')
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")


class PipelineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Literal["new", "qualified", "contacted", "opportunity", "won", "lost"] | None = None
    next_action: str | None = None


def create_pipeline_router(repository: PipelineRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/pipeline", tags=["pipeline"])
    service = PipelineService(repository)

    @router.get("")
    async def list_pipeline(
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ) -> dict[str, Any]:
        items = await service.list_entries(context)
        return {"items": items, "next_cursor": None, "has_more": False}

    @router.patch("/{entry_id}")
    async def update_pipeline(
        entry_id: str,
        update: PipelineUpdate,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> JSONResponse:
        if if_match is None:
            raise ApiError(428, "precondition_required", "Cabeçalho If-Match obrigatório.")
        match = _ETAG.fullmatch(if_match)
        if match is None:
            raise ApiError(400, "invalid_if_match", "Cabeçalho If-Match inválido.")
        if idempotency_key is None:
            raise ApiError(400, "idempotency_key_required", "Idempotency-Key obrigatório.")
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ApiError(400, "invalid_idempotency_key", "Idempotency-Key inválido.")
        changes = update.model_dump(exclude_unset=True)
        if not changes:
            raise ApiError(422, "empty_update", "Informe ao menos uma alteração.")
        entry = await service.update_entry(
            context, entry_id, idempotency_key, int(match.group(1)), changes
        )
        response = JSONResponse(content=entry)
        response.headers["ETag"] = f'"{entry["version"]}"'
        return response

    return router
