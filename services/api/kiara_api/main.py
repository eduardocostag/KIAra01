from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import uuid4

import psycopg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
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
from .competition import create_competition_router
from .competition_store import CompetitionRepository
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
from .workspace import PostgresWorkspaceResetRepository, create_workspace_router

logger = logging.getLogger(__name__)


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
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "X-Kiara-Version",
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

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
        errors = exc.errors()
        first = errors[0] if errors else {}
        location = [str(part) for part in first.get("loc", ()) if part not in {"body", "query", "path", "header"}]
        field = (location[0] if location else "requisição").replace("-", "_")
        error_type = str(first.get("type") or "validation_error")
        guidance = {
            "query": (
                "hunter_query_invalid",
                "A descrição da pesquisa deve ter entre 2 e 300 caracteres.",
                "Ajuste o texto em ‘Descreva o cliente’ e tente novamente.",
            ),
            "location": (
                "hunter_location_invalid",
                "A cidade ou região deve ter no máximo 160 caracteres.",
                "Resuma a localização, por exemplo: Porto Alegre - RS.",
            ),
            "sources": (
                "hunter_sources_invalid",
                "Selecione de 1 a 4 fontes válidas: Web, Google Maps, Instagram e Facebook.",
                "Revise as fontes marcadas. Se todas já estiverem selecionadas, atualize a página; se persistir, contate o administrador com a referência abaixo.",
            ),
            "result_limit": (
                "hunter_result_limit_invalid",
                "O limite deve ser um número entre 1 e 100.",
                "Informe um limite entre 1 e 100 e tente novamente.",
            ),
            "market": (
                "hunter_market_invalid",
                "O tipo de público enviado pela interface não é válido.",
                "Atualize a página. Se persistir, contate o administrador com a referência abaixo.",
            ),
            "idempotency_key": (
                "idempotency_key_invalid",
                "A confirmação da pesquisa chegou sem um identificador válido.",
                "Tente confirmar novamente. Se persistir, contate o administrador com a referência abaixo.",
            ),
        }
        code, message, action = guidance.get(
            field,
            (
                "request_validation_failed",
                f"O campo ‘{field}’ não foi aceito pela API.",
                "Revise o valor informado e tente novamente. Se persistir, contate o administrador com a referência abaixo.",
            ),
        )
        logger.warning(
            "api.request_validation_failed request_id=%s method=%s path=%s field=%s validation_type=%s",
            correlation_id, request.method, request.url.path, field, error_type,
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": correlation_id,
                    "details": {"field": field, "reason": error_type, "action": action, "retryable": False},
                }
            },
            headers={"X-Correlation-ID": correlation_id},
        )

    @app.exception_handler(psycopg.Error)
    async def database_error_handler(request: Request, exc: psycopg.Error) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
        database_code = getattr(exc, "sqlstate", None)
        constraint_name = getattr(getattr(exc, "diag", None), "constraint_name", None)
        known_constraints = {
            "hunter_searches_result_limit_check": (
                "hunter_result_limit_invalid",
                "Informe um limite entre 1 e 100 resultados.",
            ),
            "hunter_searches_query_check": (
                "hunter_query_invalid",
                "A pesquisa deve conter entre 2 e 300 caracteres.",
            ),
            "hunter_searches_sources_check": (
                "hunter_sources_invalid",
                "Selecione entre 1 e 4 fontes de pesquisa.",
            ),
            "hunter_results_source_check": (
                "hunter_result_source_invalid",
                "Uma fonte retornou um identificador incompatível. Os demais resultados foram preservados; contate o administrador com a referência.",
            ),
            "integration_credentials_provider_check": (
                "integration_provider_invalid",
                "A integração informada não é suportada.",
            ),
        }
        if isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)):
            status_code, code = 503, "database_unavailable"
            message = "O banco de dados está temporariamente indisponível. A operação pode ser repetida."
            retryable = True
        elif isinstance(
            exc,
            (
                psycopg.errors.SerializationFailure,
                psycopg.errors.DeadlockDetected,
                psycopg.errors.LockNotAvailable,
                psycopg.errors.QueryCanceled,
            ),
        ):
            status_code, code = 503, "database_busy"
            message = "O banco de dados estava ocupado e não concluiu a operação. Tente novamente."
            retryable = True
        elif isinstance(exc, psycopg.errors.UniqueViolation):
            status_code, code = 409, "resource_conflict"
            message = "Os dados já foram registrados ou foram alterados por outra operação."
            retryable = False
        elif isinstance(exc, psycopg.errors.ForeignKeyViolation):
            status_code, code = 409, "related_resource_missing"
            message = "Um registro necessário para concluir a operação não está mais disponível."
            retryable = False
        elif isinstance(exc, psycopg.errors.CheckViolation):
            status_code = 422
            code, message = known_constraints.get(
                constraint_name,
                (
                    "invalid_database_value",
                    "Os dados enviados não atendem às regras necessárias para esta operação.",
                ),
            )
            retryable = False
        elif isinstance(exc, (psycopg.errors.NotNullViolation, psycopg.DataError)):
            status_code, code = 422, "invalid_database_value"
            message = "Um campo obrigatório está ausente ou possui formato inválido."
            retryable = False
        elif isinstance(exc, psycopg.errors.InsufficientPrivilege):
            status_code, code = 503, "database_policy_rejected"
            message = "Uma política de segurança do banco rejeitou a operação. A ocorrência foi registrada."
            retryable = False
        else:
            status_code, code = 503, "database_operation_failed"
            message = "O banco de dados não conseguiu concluir a operação. A ocorrência foi registrada."
            retryable = True
        logger.exception(
            "api.database_error request_id=%s method=%s path=%s error_class=%s database_code=%s response_code=%s",
            correlation_id,
            request.method,
            request.url.path,
            type(exc).__name__,
            database_code,
            code,
        )
        headers = {"X-Correlation-ID": correlation_id}
        if retryable:
            headers["Retry-After"] = "2"
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": correlation_id,
                    "details": {
                        "retryable": retryable,
                        **({"database_code": database_code} if database_code else {}),
                        **({"constraint": constraint_name} if constraint_name in known_constraints else {}),
                    },
                }
            },
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
        database_code = getattr(exc, "sqlstate", None)
        logger.exception(
            "api.unexpected_error request_id=%s method=%s path=%s error_class=%s database_code=%s",
            correlation_id, request.method, request.url.path, type(exc).__name__, database_code,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": (
                        "A API encontrou um erro interno ao concluir a operação. "
                        f"Tipo: {type(exc).__name__}. A ocorrência foi registrada para diagnóstico."
                    ),
                    "request_id": correlation_id,
                    "details": {"error_type": type(exc).__name__,
                                **({"database_code": database_code} if database_code else {})},
                }
            },
            headers={"X-Correlation-ID": correlation_id},
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
            integration_repository = IntegrationRepository(PostgresRepository(config.database_url), config.integration_encryption_key)
            app.include_router(create_integration_router(integration_repository))
            app.include_router(create_competition_router(
                integration_repository,
                CompetitionRepository(PostgresRepository(config.database_url)),
            ))
        app.include_router(create_sales_router(SalesRepository(PostgresRepository(config.database_url))))
        app.include_router(create_workspace_router(PostgresWorkspaceResetRepository(PostgresRepository(config.database_url))))

    return app
