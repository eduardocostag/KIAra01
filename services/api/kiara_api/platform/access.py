"""Resolve tenant access without provisioning organizations or changing memberships."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from ..adapters.postgres import PostgresRepository, _uuid
from ..http.context import RequestContext
from ..http.errors import ApiError

_ROLES = {"owner", "admin", "operator", "viewer"}


@dataclass(frozen=True)
class PlatformAccess:
    organization_id: str
    organization_name: str
    membership_id: str
    role: str
    source: str


class PlatformAccessRepository:
    def __init__(self, postgres: PostgresRepository | None = None):
        self.postgres = postgres

    async def resolve(self, context: RequestContext) -> PlatformAccess:
        personal = context.organization_id == context.user_id
        organization = membership = None
        if self.postgres is not None:
            try:
                async with await self.postgres._connect() as connection, connection.transaction():
                    await connection.execute("SET TRANSACTION READ ONLY")
                    await connection.execute(
                        "SELECT set_config('app.organization_id', %s, true)",
                        (str(_uuid("organization", context.organization_id)),),
                    )
                    await connection.execute(
                        "SELECT set_config('app.user_id', %s, true)",
                        (str(_uuid("user", context.user_id)),),
                    )
                    organization = await (
                        await connection.execute(
                            "SELECT name,status FROM organizations WHERE id=%s",
                            (_uuid("organization", context.organization_id),),
                        )
                    ).fetchone()
                    membership = await (
                        await connection.execute(
                            "SELECT id,role,status FROM memberships WHERE organization_id=%s AND user_id=%s",
                            (
                                _uuid("organization", context.organization_id),
                                _uuid("user", context.user_id),
                            ),
                        )
                    ).fetchone()
            except psycopg.Error:
                raise ApiError(
                    503,
                    "platform_access_unavailable",
                    "Não foi possível verificar o acesso à plataforma.",
                ) from None
        if organization is not None and organization["status"] != "active":
            raise ApiError(403, "platform_organization_inactive", "Esta empresa está indisponível.")
        if membership is not None:
            if membership["status"] != "active" or membership["role"] not in _ROLES:
                raise ApiError(
                    403,
                    "platform_membership_inactive",
                    "Sua participação nesta empresa não está ativa.",
                )
            if organization is None:
                raise ApiError(403, "platform_organization_missing", "Empresa não encontrada.")
            return PlatformAccess(
                context.organization_id,
                organization["name"],
                str(membership["id"]),
                membership["role"],
                "persisted_membership",
            )
        if not personal or context.role not in _ROLES:
            raise ApiError(
                403,
                "platform_membership_required",
                "Uma participação ativa nesta empresa é obrigatória.",
            )
        # Existing Supabase personal accounts predate explicit membership rows.
        return PlatformAccess(
            context.organization_id,
            organization["name"] if organization else "Kiara Workspace",
            context.membership_id,
            context.role,
            "legacy_personal_workspace",
        )
