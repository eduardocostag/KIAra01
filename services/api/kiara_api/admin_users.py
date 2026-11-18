"""User sessions, for the system administrators (Administração → Usuários).

Supabase's admin API changes passwords, bans and deletes users, but cannot end someone else's sessions. The API's
own database connection can: deleting the user's rows in auth.sessions revokes every refresh token, and the site
rejects the session on the next request (it checks the session with Supabase on every page).
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from .adapters.postgres import PostgresRepository
from .http.context import RequestContext
from .http.dependencies import system_administrator_context
from .http.errors import ApiError


def create_admin_users_router(postgres: PostgresRepository | None) -> APIRouter:
    router = APIRouter(prefix="/v1/admin/users", tags=["admin"])

    @router.post("/{user_id}/sign-out")
    async def sign_out(user_id: str, context: Annotated[RequestContext, Depends(system_administrator_context)]) -> dict[str, Any]:
        del context
        try:
            target = str(uuid.UUID(user_id))
        except ValueError:
            raise ApiError(422, "user_invalid", "Usuário inválido.") from None
        if postgres is None:
            raise ApiError(503, "database_not_configured", "Banco de dados não configurado.")
        async with await postgres._connect() as connection, connection.transaction():
            await connection.execute("DELETE FROM auth.refresh_tokens WHERE user_id = %s", (target,))
            result = await connection.execute("DELETE FROM auth.sessions WHERE user_id = %s::uuid", (target,))
            ended = result.rowcount or 0
        return {"ended_sessions": ended}

    return router
