from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .context import RequestContext
from .errors import ApiError


async def authenticated_context(request: Request) -> RequestContext:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "authentication_required", "Autenticação obrigatória.")
    principal = await request.app.state.identity_verifier.verify(token)
    return RequestContext.from_principal(principal, request.state.correlation_id)


async def system_administrator_context(
    context: Annotated[RequestContext, Depends(authenticated_context)],
) -> RequestContext:
    if (context.email or "").strip().lower() != "admin@kiara.local":
        raise ApiError(403, "system_admin_required", "Acesso exclusivo do administrador durante o acesso antecipado.")
    return context
