from __future__ import annotations

import json
from typing import Annotated, Any, Literal, Protocol

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError


class WorkspaceResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: Literal["ZERAR"]


class WorkspaceResetRepository(Protocol):
    async def reset_commercial_data(self, context: RequestContext) -> dict[str, int]: ...


class PostgresWorkspaceResetRepository:
    """Deletes commercial data from one tenant while preserving its configuration."""

    def __init__(self, postgres: PostgresRepository) -> None:
        self._postgres = postgres

    async def reset_commercial_data(self, context: RequestContext) -> dict[str, int]:
        organization_uuid = _uuid("organization", context.organization_id)
        user_uuid = _uuid("user", context.user_id)
        async with self._postgres._transaction(context.organization_id) as connection:
            await connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user_uuid),))
            await connection.execute("SELECT kiara.ensure_current_user('supabase', %s)", (context.user_id,))

            counts: dict[str, int] = {}
            for key, table in (
                ("leads", "consumers"),
                ("pipeline_entries", "pipeline_entries"),
                ("searches", "hunter_searches"),
                ("conversations", "conversation_threads"),
                ("activities", "outreach_activities"),
            ):
                row = await (await connection.execute(
                    f"SELECT count(*) AS count FROM {table} WHERE organization_id=%s",
                    (organization_uuid,),
                )).fetchone()
                counts[key] = int(row["count"])

            # Delete in dependency order. Every statement is tenant-scoped and the
            # transaction is atomic: either the whole reset succeeds or nothing is lost.
            for table in (
                "approvals",
                "message_drafts",
                "messages",
                "qualifications",
                "conversation_threads",
                "outreach_activities",
                "pipeline_stage_events",
                "pipeline_entries",
                "hunter_searches",
                "consumers",
                "jobs",
                "outbox_events",
            ):
                await connection.execute(
                    f"DELETE FROM {table} WHERE organization_id=%s",
                    (organization_uuid,),
                )

            await connection.execute(
                """INSERT INTO audit_events
                   (organization_id,actor_user_id,action,resource_type,correlation_id,metadata)
                   VALUES (%s,%s,'workspace.commercial_data.reset','workspace',%s,%s)""",
                (organization_uuid, user_uuid, context.correlation_id, json.dumps(counts)),
            )
        return counts


def create_workspace_router(repository: WorkspaceResetRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/workspace", tags=["workspace"])

    @router.delete("/commercial-data")
    async def reset_commercial_data(
        payload: WorkspaceResetRequest,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ) -> dict[str, Any]:
        if context.role not in {"owner", "admin"}:
            raise ApiError(
                403,
                "insufficient_role",
                "Somente proprietários e administradores podem zerar os dados do workspace.",
            )
        deleted = await repository.reset_commercial_data(context)
        return {
            "status": "reset",
            "deleted": deleted,
            "preserved": ["sales_profile", "message_templates", "integrations"],
        }

    return router
