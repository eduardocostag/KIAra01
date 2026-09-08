from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, Response, status
from pydantic import BaseModel

from ...application.conversations import ConversationCommands
from ..context import RequestContext
from ..dependencies import authenticated_context
from ..errors import ApiError


class DraftCreate(BaseModel):
    text: str


class QualificationRequest(BaseModel):
    force_refresh: bool = False


def create_conversation_router(commands: ConversationCommands) -> APIRouter:
    router = APIRouter(tags=["conversations"])

    @router.post(
        "/v1/inbox/threads/{thread_id}/drafts",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_draft(
        thread_id: str,
        payload: DraftCreate,
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> dict[str, object]:
        draft = await commands.create_draft(
            context=context,
            thread_id=thread_id,
            text=payload.text,
            idempotency_key=idempotency_key,
        )
        response.headers["ETag"] = f'"{draft["version"]}"'
        return draft

    @router.post("/v1/drafts/{draft_id}/approve")
    async def approve_draft(
        draft_id: str,
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> dict[str, object]:
        draft = await commands.approve_draft(
            context=context,
            draft_id=draft_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
        )
        response.headers["ETag"] = f'"{draft["version"]}"'
        return draft

    @router.post("/v1/threads/{thread_id}/qualify")
    async def qualify_thread(
        thread_id: str,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
        payload: Annotated[QualificationRequest | None, Body()] = None,
    ) -> dict[str, object]:
        return await commands.qualify_thread(
            context=context,
            thread_id=thread_id,
            force_refresh=payload.force_refresh if payload else False,
            idempotency_key=idempotency_key,
        )

    return router


def require_commands(value: ConversationCommands | None) -> ConversationCommands:
    """Small integration guard for factories that configure adapters conditionally."""
    if value is None:
        raise ApiError(503, "conversation_commands_unavailable", "Comandos indisponíveis.")
    return value
