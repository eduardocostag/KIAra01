from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .adapters.conversations_demo import InMemoryConversationCommandRepository
from .adapters.demo import (
    DemoIdentityVerifier,
    InMemoryInboxRepository,
    UnconfiguredIdentityVerifier,
)
from .adapters.pipeline_memory import InMemoryPipelineRepository
from .application.conversations import ConversationCommands
from .config import ApiSettings
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
from .http.routes.conversations import create_conversation_router
from .http.routes.pipeline import create_pipeline_router
from .hunter import HunterRepository, create_hunter_router
from .integrations import IntegrationRepository, create_integration_router
from .ports.conversations import ConversationCommandRepository
from .ports.identity import IdentityVerifier
from .ports.inbox import InboxRepository
from .ports.pipeline import PipelineRepository
from .sales import SalesRepository, create_sales_router


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-correlation-id", "").strip()
        correlation_id = (
            incoming
            if incoming and len(incoming) <= 128 and all(char.isalnum() or char in "-_." for char in incoming)
            else str(uuid4())
        )
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class IdentityResponse(BaseModel):
    user_id: str
    membership_id: str
    organization: dict[str, str]
    role: str
    capabilities: list[str]


_CAPABILITIES = {
    "owner": ["inbox.read", "draft.create", "thread.qualify", "outbound.approve", "pipeline.write", "integrations.manage"],
    "admin": ["inbox.read", "draft.create", "thread.qualify", "outbound.approve", "pipeline.write", "integrations.manage"],
    "operator": ["inbox.read", "draft.create", "thread.qualify", "pipeline.write"],
    "viewer": ["inbox.read"],
}


def create_app(
    settings: ApiSettings | None = None,
    identity_verifier: IdentityVerifier | None = None,
    inbox_repository: InboxRepository | None = None,
    conversation_repository: ConversationCommandRepository | None = None,
    pipeline_repository: PipelineRepository | None = None,
) -> FastAPI:
    config = settings or ApiSettings.from_env()
    config.validate()
    if identity_verifier is None:
        if config.demo_auth_enabled:
            identity_verifier = DemoIdentityVerifier()
        elif config.oidc_configured:
            from .adapters.identity_oidc import OidcIdentityVerifier

            identity_verifier = OidcIdentityVerifier(
                issuer=config.oidc_issuer or "",
                audience=config.oidc_audience or "",
                jwks_url=config.oidc_jwks_url or "",
                cache_ttl_seconds=config.oidc_jwks_cache_ttl_seconds,
            )
        else:
            identity_verifier = UnconfiguredIdentityVerifier()
    if config.database_url and not any(
        (inbox_repository, conversation_repository, pipeline_repository)
    ):
        from .adapters.postgres import PostgresRepository

        postgres = PostgresRepository(config.database_url)
        repository = postgres
        conversation_commands_repository = postgres
        pipeline_entries_repository = postgres
    else:
        repository = inbox_repository or InMemoryInboxRepository()
        conversation_commands_repository = (
            conversation_repository or InMemoryConversationCommandRepository()
        )
        pipeline_entries_repository = pipeline_repository or InMemoryPipelineRepository()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.identity_verifier = identity_verifier
        app.state.inbox_repository = repository
        app.state.conversation_repository = conversation_commands_repository
        app.state.pipeline_repository = pipeline_entries_repository
        app.state.settings = config
        yield

    app = FastAPI(title="Kiara Lead Intelligence API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "X-Correlation-ID",
        ],
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request.state.correlation_id,
                    "details": exc.details,
                }
            },
        )

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready(request: Request) -> dict[str, str]:
        if not await request.app.state.inbox_repository.ready():
            raise ApiError(503, "dependency_unavailable", "API não está pronta.")
        return {"status": "ok"}

    @app.get("/v1/me", response_model=IdentityResponse)
    async def me(
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ) -> IdentityResponse:
        return IdentityResponse(
            user_id=context.user_id,
            membership_id=context.membership_id,
            organization={
                "id": context.organization_id,
                "name": "Kiara Workspace",
                "slug": context.organization_id,
            },
            role=context.role,
            capabilities=_CAPABILITIES.get(context.role, ["inbox.read"]),
        )

    @app.get("/v1/inbox/threads")
    async def list_threads(
        request: Request,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ) -> dict[str, Any]:
        items = await request.app.state.inbox_repository.list_threads(context.organization_id)
        return {"items": items, "next_cursor": None, "has_more": False}

    @app.get("/v1/inbox/threads/{thread_id}")
    async def get_thread(
        thread_id: str,
        request: Request,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ) -> dict[str, Any]:
        item = await request.app.state.inbox_repository.get_thread(
            context.organization_id, thread_id
        )
        if item is None:
            raise ApiError(404, "thread_not_found", "Conversa não encontrada.")
        response = JSONResponse(content=item)
        response.headers["ETag"] = f'"{item["version"]}"'
        return response

    app.include_router(
        create_conversation_router(ConversationCommands(conversation_commands_repository))
    )
    app.include_router(create_pipeline_router(pipeline_entries_repository))
    if config.database_url:
        app.include_router(create_hunter_router(HunterRepository(PostgresRepository(config.database_url))))
        if config.integration_encryption_key:
            app.include_router(create_integration_router(IntegrationRepository(PostgresRepository(config.database_url), config.integration_encryption_key)))
        app.include_router(create_sales_router(SalesRepository(PostgresRepository(config.database_url))))

    return app
