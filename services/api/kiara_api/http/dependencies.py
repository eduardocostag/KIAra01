from __future__ import annotations

from ..admins import is_system_admin

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
    context = RequestContext.from_principal(principal, request.state.correlation_id)
    # Team members sign in with their own account (a one-person workspace by default) and work inside the
    # workspace that invited them, with the role they were given.
    team = getattr(request.app.state, "team", None)
    if team is not None and context.organization_id == context.user_id:
        seat = await team.seat_for(context.user_id)
        if seat:
            context = RequestContext(context.user_id, seat["organization_id"], f"{seat['organization_id']}:{context.user_id}",
                                     seat["role"], context.correlation_id, context.email)
    return context


async def system_administrator_context(
    context: Annotated[RequestContext, Depends(authenticated_context)],
) -> RequestContext:
    if not is_system_admin(context.email):
        raise ApiError(403, "system_admin_required", "Acesso exclusivo do administrador durante o acesso antecipado.")
    return context
