"""Teams: the owner invites people by link; each one signs in with their own account and works inside
the owner's workspace with a role (admin, operator, viewer). Includes a simple sales ranking.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

Context = Annotated[RequestContext, Depends(authenticated_context)]
from .usage import PLANS, SYSTEM_ADMIN_EMAIL, subscription

Role = Literal["admin", "operator", "viewer"]
ROLE_LABELS = {"owner": "Dono", "admin": "Administrador", "operator": "Vendedor", "viewer": "Somente leitura"}
SEAT_CACHE_SECONDS = 60


class InviteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    role: Role = "operator"


class InviteAccept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=200)
    display_name: str = Field(default="", max_length=160)


class RoleChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TeamService:
    def __init__(self, postgres: PostgresRepository | None) -> None:
        self._postgres = postgres
        self._seats: dict[str, tuple[float, dict[str, Any] | None]] = {}

    async def _server(self):
        """A connection outside any tenant: seats and invites are looked up before the workspace is known."""
        return await self._postgres._connect()

    async def seat_for(self, subject: str) -> dict[str, Any] | None:
        """The workspace a signed-in person belongs to as a team member (cached for a minute)."""
        if self._postgres is None:
            return None
        cached = self._seats.get(subject)
        if cached and time.monotonic() - cached[0] < SEAT_CACHE_SECONDS:
            return cached[1]
        try:
            async with await self._server() as connection:
                row = await (await connection.execute(
                    "SELECT organization_id,role FROM team_seats WHERE subject=%s", (subject,))).fetchone()
        except Exception:  # noqa: BLE001 - before the migration, everyone stays in their own workspace
            row = None
        seat = {"organization_id": str(row["organization_id"]), "role": row["role"]} if row else None
        self._seats[subject] = (time.monotonic(), seat)
        return seat

    def forget(self, subject: str) -> None:
        self._seats.pop(subject, None)

    @staticmethod
    def _manager(context: RequestContext) -> None:
        if context.role not in {"owner", "admin"}:
            raise ApiError(403, "insufficient_role", "Só quem administra a conta gerencia a equipe.")

    async def overview(self, context: RequestContext, days: int = 30) -> dict[str, Any]:
        org = _uuid("organization", context.organization_id)
        since = datetime.now(UTC) - timedelta(days=days)
        async with self._postgres._transaction(context.organization_id) as connection:
            plan = await subscription(connection, org)
        async with await self._server() as connection:
            seats = await (await connection.execute(
                "SELECT subject,role,email,display_name,created_at FROM team_seats WHERE organization_id=%s ORDER BY created_at", (org,))).fetchall()
            invites = await (await connection.execute(
                """SELECT id,email,role,created_at,expires_at FROM team_invites WHERE organization_id=%s
                   AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at>now() ORDER BY created_at DESC""", (org,))).fetchall()
        people = [{"subject": str(org), "role": "owner", "email": None, "display_name": "Dono da conta"},
                  *[{"subject": row["subject"], "role": row["role"], "email": row["email"], "display_name": row["display_name"]} for row in seats]]
        async with self._postgres._transaction(context.organization_id) as connection:
            for person in people:
                stats = await (await connection.execute(
                    """SELECT
                         (SELECT count(DISTINCT o.pipeline_entry_id) FROM outreach_activities o JOIN users u ON u.id=o.actor_user_id
                           WHERE o.organization_id=%(org)s AND u.external_subject=%(subject)s AND o.status='sent' AND o.created_at>=%(since)s) AS approached,
                         (SELECT count(DISTINCT e.pipeline_entry_id) FROM pipeline_stage_events e JOIN users u ON u.id=e.actor_user_id
                           WHERE e.organization_id=%(org)s AND u.external_subject=%(subject)s AND e.to_stage='won' AND e.created_at>=%(since)s) AS won""",
                    {"org": org, "subject": person["subject"], "since": since})).fetchone()
                person.update(approached=int(stats["approached"]), won=int(stats["won"]), role_label=ROLE_LABELS[person["role"]],
                              you=person["subject"] == context.user_id or (person["role"] == "owner" and context.role == "owner"))
        return {
            "members": people,
            "ranking": sorted(people, key=lambda item: (-item["won"], -item["approached"])),
            "invites": [{"id": str(row["id"]), "email": row["email"], "role": row["role"], "role_label": ROLE_LABELS[row["role"]],
                         "expires_at": row["expires_at"].isoformat()} for row in invites],
            "seats": {"used": len(people) + len(invites), "limit": PLANS[plan["plan"]]["limits"]["seats"]},
            "can_manage": context.role in {"owner", "admin"},
        }

    async def invite(self, context: RequestContext, body: InviteCreate) -> dict[str, Any]:
        self._manager(context)
        overview = await self.overview(context)
        unlimited = (context.email or "").strip().lower() == SYSTEM_ADMIN_EMAIL
        if overview["seats"]["used"] >= overview["seats"]["limit"] and not unlimited:
            raise ApiError(402, "plan_limit_reached", f"Seu plano permite {overview['seats']['limit']} pessoa(s) na equipe. Mude de plano para convidar mais.")
        token = secrets.token_urlsafe(32)
        async with await self._server() as connection, connection.transaction():
            await connection.execute(
                "INSERT INTO team_invites(organization_id,email,role,token_hash,invited_by) VALUES(%s,%s,%s,%s,%s)",
                (_uuid("organization", context.organization_id), body.email.strip().lower(), body.role, token_hash(token), context.user_id))
        return {"token": token, "email": body.email.strip().lower(), "role": body.role}

    async def accept(self, context: RequestContext, body: InviteAccept) -> dict[str, Any]:
        async with await self._server() as connection, connection.transaction():
            invite = await (await connection.execute(
                """SELECT id,organization_id,email,role FROM team_invites WHERE token_hash=%s AND accepted_at IS NULL
                   AND revoked_at IS NULL AND expires_at>now() FOR UPDATE""", (token_hash(body.token),))).fetchone()
            if invite is None:
                raise ApiError(404, "invite_invalid", "Este convite não existe, já foi usado ou expirou. Peça um novo link.")
            if str(invite["organization_id"]) == context.user_id:
                raise ApiError(409, "invite_own_workspace", "Você já é o dono desta conta.")
            email = (context.email or "").strip().lower()
            if email and email != invite["email"]:
                raise ApiError(403, "invite_other_email", f"Este convite é para {invite['email']}. Entre com esse e-mail para aceitar.")
            await connection.execute(
                """INSERT INTO team_seats(subject,organization_id,role,email,display_name) VALUES(%s,%s,%s,%s,%s)
                   ON CONFLICT (subject) DO UPDATE SET organization_id=excluded.organization_id,role=excluded.role,
                   email=excluded.email,display_name=excluded.display_name""",
                (context.user_id, invite["organization_id"], invite["role"], invite["email"], body.display_name.strip() or None))
            await connection.execute("UPDATE team_invites SET accepted_at=now() WHERE id=%s", (invite["id"],))
        self.forget(context.user_id)
        return {"joined": True, "role": invite["role"]}

    async def change_role(self, context: RequestContext, subject: str, body: RoleChange) -> None:
        self._manager(context)
        async with await self._server() as connection, connection.transaction():
            await connection.execute("UPDATE team_seats SET role=%s WHERE subject=%s AND organization_id=%s",
                                     (body.role, subject, _uuid("organization", context.organization_id)))
        self.forget(subject)

    async def remove(self, context: RequestContext, subject: str) -> None:
        if subject != context.user_id:
            self._manager(context)   # anyone may leave; only managers remove others
        async with await self._server() as connection, connection.transaction():
            await connection.execute("DELETE FROM team_seats WHERE subject=%s AND organization_id=%s",
                                     (subject, _uuid("organization", context.organization_id)))
        self.forget(subject)

    async def revoke(self, context: RequestContext, invite_id: str) -> None:
        self._manager(context)
        async with await self._server() as connection, connection.transaction():
            await connection.execute("UPDATE team_invites SET revoked_at=now() WHERE id=%s AND organization_id=%s",
                                     (_uuid("invite", invite_id), _uuid("organization", context.organization_id)))


def create_team_router(service: TeamService) -> APIRouter:
    router = APIRouter(prefix="/v1/team", tags=["team"])

    @router.get("")
    async def overview(context: Context) -> dict[str, Any]:
        return await service.overview(context)

    @router.post("/invites", status_code=201)
    async def invite(body: InviteCreate, context: Context) -> dict[str, Any]:
        return await service.invite(context, body)

    @router.delete("/invites/{invite_id}", status_code=204)
    async def revoke(invite_id: str, context: Context) -> None:
        await service.revoke(context, invite_id)

    @router.post("/accept")
    async def accept(body: InviteAccept, context: Context) -> dict[str, Any]:
        return await service.accept(context, body)

    @router.patch("/members/{subject}", status_code=204)
    async def change_role(subject: str, body: RoleChange, context: Context) -> None:
        await service.change_role(context, subject, body)

    @router.delete("/members/{subject}", status_code=204)
    async def remove(subject: str, context: Context) -> None:
        await service.remove(context, subject)

    return router
