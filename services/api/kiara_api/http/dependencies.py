from __future__ import annotations

from fastapi import Request

from .context import RequestContext
from .errors import ApiError


async def authenticated_context(request: Request) -> RequestContext:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "authentication_required", "Autenticação obrigatória.")
    principal = await request.app.state.identity_verifier.verify(token)
    return RequestContext.from_principal(principal, request.state.correlation_id)
