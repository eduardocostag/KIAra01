"""Tenant-scoped Chatwoot Application API bridge; no automatic reply/retry loop."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi import Path as PathParameter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
from .integrations import IntegrationRepository

logger = logging.getLogger(__name__)


class ChatwootReplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content: str = Field(min_length=1, max_length=4000)
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True:
            raise ValueError("Confirme explicitamente a mensagem antes do envio.")
        return value

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Mensagem vazia.")
        return value


def _runtime_client(credentials: dict[str, str]):
    try:
        from app.integrations.chatwoot import ChatwootClient
    except ModuleNotFoundError:
        # Only a fixed checkout path may provide the packaged runtime.
        root = Path(__file__).resolve().parents[3]
        if not (root / "app/integrations/chatwoot.py").is_file():
            raise ApiError(503, "chatwoot_runtime_unavailable", "Runtime Chatwoot indisponivel.") from None
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from app.integrations.chatwoot import ChatwootClient
        except ModuleNotFoundError:
            raise ApiError(503, "chatwoot_runtime_unavailable", "Dependencias Chatwoot indisponiveis.") from None
    try:
        return ChatwootClient(credentials["endpoint_url"], credentials["api_access_token"],
                              int(credentials["account_id"]), allow_private_hosts=False)
    except (ValueError, TypeError, KeyError):
        raise ApiError(503, "chatwoot_configuration_invalid", "Revise a integracao Chatwoot do workspace.") from None


def create_chatwoot_router(repository: IntegrationRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/chatwoot", tags=["chatwoot"])

    async def client(context: RequestContext):
        credentials = await repository.credentials_for(context.organization_id, "chatwoot")
        if not credentials:
            raise ApiError(404, "chatwoot_not_configured", "Conecte o Chatwoot neste workspace.")
        return _runtime_client(credentials)

    async def invoke(operation, *, sending: bool = False):
        try:
            return await operation
        except (OSError, RuntimeError, ValueError, TypeError):
            if sending:
                raise ApiError(502, "chatwoot_delivery_unknown",
                               "Nao foi possivel confirmar o envio. Confira a conversa antes de tentar novamente.") from None
            raise ApiError(502, "chatwoot_unavailable", "Chatwoot indisponivel ou acesso negado.") from None

    @router.get("/inboxes")
    async def inboxes(
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        limit: Annotated[int, Query(ge=1, le=50)] = 50,
    ):
        response.headers["Cache-Control"] = "no-store"
        adapter = await client(context)
        return {"items": await invoke(adapter.list_inboxes(limit=limit))}

    @router.get("/conversations")
    async def conversations(
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        status: Literal["open", "resolved", "pending", "snoozed", "all"] = "open",
        page: Annotated[int, Query(ge=1, le=10000)] = 1,
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
    ):
        response.headers["Cache-Control"] = "no-store"
        adapter = await client(context)
        return {"items": await invoke(adapter.list_conversations(status=status, page=page, limit=limit)),
                "page": page}

    @router.get("/conversations/{conversation_id}/messages")
    async def messages(
        conversation_id: Annotated[int, PathParameter(ge=1, le=2**53 - 1)],
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        before: Annotated[int | None, Query(ge=1, le=2**53 - 1)] = None,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
    ):
        response.headers["Cache-Control"] = "no-store"
        adapter = await client(context)
        return {"items": await invoke(adapter.list_messages(conversation_id, before=before, limit=limit))}

    @router.post("/conversations/{conversation_id}/messages")
    async def reply(
        conversation_id: Annotated[int, PathParameter(ge=1, le=2**53 - 1)],
        payload: ChatwootReplyInput,
        response: Response,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        if context.role not in {"owner", "admin"}:
            raise ApiError(403, "insufficient_permission", "Seu perfil nao pode enviar mensagens.")
        response.headers["Cache-Control"] = "no-store"
        adapter = await client(context)
        logger.info("chatwoot.reply.requested", extra={
            "organization_id": context.organization_id, "user_id": context.user_id,
            "conversation_id": conversation_id, "correlation_id": context.correlation_id,
        })
        result = await invoke(adapter.send_message(conversation_id, payload.content), sending=True)
        logger.info("chatwoot.reply.accepted", extra={
            "organization_id": context.organization_id, "conversation_id": conversation_id,
            "correlation_id": context.correlation_id,
        })
        return {"message": result, "automatic_retry": False}

    return router
