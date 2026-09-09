from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import psycopg
from psycopg.rows import dict_row

from ..http.errors import ApiError


def _uuid(kind: str, external_id: str) -> UUID:
    try:
        return UUID(external_id)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"kiara:{kind}:{external_id}")


def _iso(value: Any) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _psycopg_url(value: str) -> str:
    parts = urlsplit(value)
    query = urlencode([(key, item) for key, item in parse_qsl(parts.query) if key != "supa"])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


class PostgresRepository:
    """Persistent, tenant-scoped repository backed by Supabase PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        self._database_url = _psycopg_url(database_url)

    @asynccontextmanager
    async def _transaction(self, organization_id: str) -> AsyncIterator[psycopg.AsyncConnection]:
        organization_uuid = _uuid("organization", organization_id)
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=dict_row, connect_timeout=5
        ) as connection, connection.transaction():
            await connection.execute(
                "SELECT set_config('app.organization_id', %s, true)",
                (str(organization_uuid),),
            )
            await connection.execute(
                """INSERT INTO organizations (id, slug, name)
                   VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                (organization_uuid, f"clerk-{str(organization_uuid)[:18]}", "Kiara Workspace"),
            )
            yield connection

    async def ready(self) -> bool:
        try:
            async with await psycopg.AsyncConnection.connect(
                self._database_url, connect_timeout=5
            ) as connection:
                row = await (await connection.execute("SELECT to_regclass('public.organizations')")).fetchone()
                return bool(row and row[0])
        except psycopg.Error:
            return False

    async def list_threads(self, organization_id: str) -> list[dict[str, Any]]:
        async with self._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT t.id, t.channel, t.status, t.updated_at, c.id consumer_id,
                          c.display_name, c.instagram_username,
                          (SELECT count(*) FROM messages m WHERE m.organization_id=t.organization_id
                           AND m.thread_id=t.id AND m.direction='inbound') unread_count
                   FROM conversation_threads t JOIN consumers c
                     ON c.organization_id=t.organization_id AND c.id=t.consumer_id
                   WHERE t.organization_id=%s ORDER BY t.updated_at DESC LIMIT 100""",
                (_uuid("organization", organization_id),),
            )).fetchall()
        return [self._thread_summary(row) for row in rows]

    async def get_thread(self, organization_id: str, thread_id: str) -> dict[str, Any] | None:
        organization_uuid, thread_uuid = _uuid("organization", organization_id), _uuid("thread", thread_id)
        async with self._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT t.id, t.channel, t.status, t.updated_at, c.id consumer_id,
                          c.display_name, c.instagram_username,
                          (SELECT count(*) FROM messages m WHERE m.organization_id=t.organization_id
                           AND m.thread_id=t.id AND m.direction='inbound') unread_count
                   FROM conversation_threads t JOIN consumers c
                     ON c.organization_id=t.organization_id AND c.id=t.consumer_id
                   WHERE t.organization_id=%s AND t.id=%s""",
                (organization_uuid, thread_uuid),
            )).fetchone()
            if row is None:
                return None
            messages = await (await connection.execute(
                "SELECT id, direction, body text, sent_at created_at FROM messages WHERE organization_id=%s AND thread_id=%s ORDER BY sent_at, id",
                (organization_uuid, thread_uuid),
            )).fetchall()
            drafts = await (await connection.execute(
                "SELECT id, thread_id, body text, status, version, content_hash, created_at, updated_at FROM message_drafts WHERE organization_id=%s AND thread_id=%s ORDER BY created_at, id",
                (organization_uuid, thread_uuid),
            )).fetchall()
            qualification = await (await connection.execute(
                "SELECT id, thread_id, score, temperature, recommendation, created_at FROM qualifications WHERE organization_id=%s AND thread_id=%s ORDER BY created_at DESC LIMIT 1",
                (organization_uuid, thread_uuid),
            )).fetchone()
        result = self._thread_summary(row)
        result["messages"] = [self._serialize(item) for item in messages]
        result["drafts"] = [self._serialize(item) for item in drafts]
        result["qualification"] = self._serialize(qualification) if qualification else None
        return result

    async def create_draft(self, *, organization_id: str, thread_id: str, text: str,
                           idempotency_key: str, request_fingerprint: str) -> dict[str, Any]:
        organization_uuid, thread_uuid = _uuid("organization", organization_id), _uuid("thread", thread_id)
        async with self._transaction(organization_id) as connection:
            replay = await self._replay(connection, organization_uuid, "create_draft", idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            exists = await (await connection.execute(
                "SELECT 1 FROM conversation_threads WHERE organization_id=%s AND id=%s",
                (organization_uuid, thread_uuid),
            )).fetchone()
            if not exists:
                raise ApiError(404, "thread_not_found", "Conversa não encontrada.")
            system_user = _uuid("user", f"system-draft:{organization_id}")
            await connection.execute(
                "INSERT INTO users (id, identity_provider, external_subject) VALUES (%s,'kiara',%s) ON CONFLICT (id) DO NOTHING",
                (system_user, f"system-draft:{organization_id}"),
            )
            row = await (await connection.execute(
                """INSERT INTO message_drafts
                   (organization_id, thread_id, body, content_hash, created_by)
                   VALUES (%s,%s,%s,%s,%s) RETURNING id, thread_id, body text, status,
                   version, content_hash, created_at, updated_at""",
                (organization_uuid, thread_uuid, text, hashlib.sha256(text.encode()).hexdigest(),
                 system_user),
            )).fetchone()
            result = self._serialize(row)
            await self._remember(connection, organization_uuid, "create_draft", idempotency_key, request_fingerprint, result)
            return result

    async def approve_draft(self, *, organization_id: str, draft_id: str, expected_version: int,
                            actor_user_id: str, actor_membership_id: str, idempotency_key: str,
                            request_fingerprint: str) -> dict[str, Any]:
        organization_uuid, draft_uuid = _uuid("organization", organization_id), _uuid("draft", draft_id)
        user_uuid = _uuid("user", actor_user_id)
        async with self._transaction(organization_id) as connection:
            replay = await self._replay(connection, organization_uuid, "approve_draft", idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            await connection.execute(
                "INSERT INTO users (id, identity_provider, external_subject) VALUES (%s,'clerk',%s) ON CONFLICT (id) DO NOTHING",
                (user_uuid, actor_user_id),
            )
            await connection.execute(
                """INSERT INTO memberships (organization_id,id,user_id,role,status)
                   VALUES (%s,%s,%s,'operator','active') ON CONFLICT (organization_id,user_id) DO NOTHING""",
                (organization_uuid, _uuid("membership", actor_membership_id), user_uuid),
            )
            current = await (await connection.execute(
                "SELECT * FROM message_drafts WHERE organization_id=%s AND id=%s FOR UPDATE",
                (organization_uuid, draft_uuid),
            )).fetchone()
            if current is None:
                raise ApiError(404, "draft_not_found", "Rascunho não encontrado.")
            if current["version"] != expected_version:
                raise ApiError(412, "precondition_failed", "O rascunho foi alterado; recarregue antes de aprovar.")
            if current["status"] != "draft":
                raise ApiError(409, "draft_not_approvable", "O rascunho não pode ser aprovado.")
            await connection.execute(
                "INSERT INTO approvals (organization_id,draft_id,draft_version,content_hash,decision,decided_by) VALUES (%s,%s,%s,%s,'approved',%s)",
                (organization_uuid, draft_uuid, expected_version, current["content_hash"], user_uuid),
            )
            row = await (await connection.execute(
                """UPDATE message_drafts SET status='approved', version=version+1, updated_at=now()
                   WHERE organization_id=%s AND id=%s RETURNING id,thread_id,body text,status,version,content_hash,created_at,updated_at""",
                (organization_uuid, draft_uuid),
            )).fetchone()
            result = self._serialize(row)
            await self._remember(connection, organization_uuid, "approve_draft", idempotency_key, request_fingerprint, result)
            return result

    async def qualify_thread(self, *, organization_id: str, thread_id: str, force_refresh: bool,
                             idempotency_key: str, request_fingerprint: str) -> dict[str, Any]:
        organization_uuid, thread_uuid = _uuid("organization", organization_id), _uuid("thread", thread_id)
        async with self._transaction(organization_id) as connection:
            replay = await self._replay(connection, organization_uuid, "qualify_thread", idempotency_key, request_fingerprint)
            if replay is not None:
                return replay
            row = None if force_refresh else await (await connection.execute(
                "SELECT id,thread_id,score,temperature,recommendation,created_at FROM qualifications WHERE organization_id=%s AND thread_id=%s ORDER BY created_at DESC LIMIT 1",
                (organization_uuid, thread_uuid),
            )).fetchone()
            if row is None:
                try:
                    row = await (await connection.execute(
                        """INSERT INTO qualifications (organization_id,thread_id,score,temperature,recommendation)
                           VALUES (%s,%s,50,'warm','Revisar a conversa e preparar uma resposta')
                           RETURNING id,thread_id,score,temperature,recommendation,created_at""",
                        (organization_uuid, thread_uuid),
                    )).fetchone()
                except psycopg.errors.ForeignKeyViolation as exc:
                    raise ApiError(404, "thread_not_found", "Conversa não encontrada.") from exc
            result = self._serialize(row)
            await self._remember(connection, organization_uuid, "qualify_thread", idempotency_key, request_fingerprint, result)
            return result

    async def list_entries(self, organization_id: str) -> list[dict[str, Any]]:
        organization_uuid = _uuid("organization", organization_id)
        async with self._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT p.id,p.stage,p.next_action,p.next_action_at,p.version,p.updated_at,c.id consumer_id,
                          c.display_name,c.instagram_username,c.attributes,
                          COALESCE((SELECT jsonb_agg(item ORDER BY item->>'created_at' DESC) FROM
                            (SELECT jsonb_build_object('id',a.id,'channel',a.channel,'status',a.status,'body',a.body,
                              'next_follow_up_at',a.next_follow_up_at,'created_at',a.created_at) item
                             FROM outreach_activities a WHERE a.organization_id=p.organization_id
                               AND a.pipeline_entry_id=p.id ORDER BY a.created_at DESC LIMIT 20) recent), '[]'::jsonb) activities
                   FROM pipeline_entries p JOIN consumers c
                   ON c.organization_id=p.organization_id AND c.id=p.consumer_id
                   WHERE p.organization_id=%s AND c.lifecycle_status='active'
                     AND c.consent_status NOT IN ('revoked','opted_out')
                   ORDER BY p.updated_at DESC""", (organization_uuid,)
            )).fetchall()
        return [self._pipeline(row) for row in rows]

    async def update_entry(self, organization_id: str, entry_id: str, idempotency_key: str,
                           expected_version: int, changes: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
        organization_uuid, entry_uuid = _uuid("organization", organization_id), _uuid("pipeline", entry_id)
        fingerprint = hashlib.sha256(json.dumps(changes, sort_keys=True).encode()).hexdigest()
        async with self._transaction(organization_id) as connection:
            replay = await self._replay(connection, organization_uuid, "pipeline_update", idempotency_key, fingerprint, conflict_as_none=True)
            if replay is not None:
                return "updated", replay
            current = await (await connection.execute(
                "SELECT version FROM pipeline_entries WHERE organization_id=%s AND id=%s FOR UPDATE", (organization_uuid, entry_uuid)
            )).fetchone()
            if current is None:
                return "missing", None
            if current["version"] != expected_version:
                return "conflict", None
            assignments, values = [], []
            for column in ("stage", "next_action"):
                if column in changes:
                    assignments.append(f"{column}=%s")
                    values.append(changes[column])
            values.extend([organization_uuid, entry_uuid])
            row = await (await connection.execute(
                f"UPDATE pipeline_entries SET {', '.join(assignments)}, version=version+1, updated_at=now() WHERE organization_id=%s AND id=%s RETURNING id,stage,next_action,version,updated_at,consumer_id",
                values,
            )).fetchone()
            consumer = await (await connection.execute(
                "SELECT display_name,instagram_username,attributes FROM consumers WHERE organization_id=%s AND id=%s",
                (organization_uuid, row["consumer_id"]),
            )).fetchone()
            row.update(consumer)
            result = self._pipeline(row)
            await self._remember(connection, organization_uuid, "pipeline_update", idempotency_key, fingerprint, result)
            return "updated", result

    async def _replay(self, connection: psycopg.AsyncConnection, organization_uuid: UUID,
                      operation: str, key: str, fingerprint: str, conflict_as_none: bool = False) -> dict[str, Any] | None:
        row = await (await connection.execute(
            "SELECT payload FROM jobs WHERE organization_id=%s AND idempotency_key=%s", (organization_uuid, f"{operation}:{key}")
        )).fetchone()
        if row is None:
            return None
        if row["payload"].get("fingerprint") != fingerprint:
            if conflict_as_none:
                raise ApiError(409, "idempotency_conflict", "Chave de idempotência já utilizada.")
            raise ApiError(409, "idempotency_conflict", "A Idempotency-Key já foi usada com outra requisição.")
        return row["payload"]["response"]

    async def _remember(self, connection: psycopg.AsyncConnection, organization_uuid: UUID,
                        operation: str, key: str, fingerprint: str, response: dict[str, Any]) -> None:
        await connection.execute(
            "INSERT INTO jobs (organization_id,kind,state,payload,idempotency_key) VALUES (%s,%s,'succeeded',%s,%s)",
            (organization_uuid, operation, json.dumps({"fingerprint": fingerprint, "response": response}), f"{operation}:{key}"),
        )

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {key: (_iso(value) if hasattr(value, "isoformat") else str(value) if isinstance(value, UUID) else value) for key, value in row.items()}

    def _thread_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(row["id"]), "channel": row["channel"], "consumer": {
            "id": str(row["consumer_id"]), "display_name": row["display_name"] or "Lead do Instagram",
            "instagram_username": row["instagram_username"] or "instagram"
        }, "status": row["status"], "unread_count": row["unread_count"],
            "updated_at": _iso(row["updated_at"]), "version": 1}

    def _pipeline(self, row: dict[str, Any]) -> dict[str, Any]:
        hunter = (row.get("attributes") or {}).get("hunter") or {}
        consumer = {"id": str(row["consumer_id"]),
                    "display_name": row["display_name"] or "Contato sem nome",
                    "instagram_username": row["instagram_username"] or None}
        for key in ("phone", "whatsapp_url", "source_url", "source", "website_status",
                    "website_url", "research_query", "search_id", "location", "address",
                    "website_evidence", "criterion_status"):
            if isinstance(hunter.get(key), str):
                consumer[key] = hunter[key]
        return {"id": str(row["id"]), "consumer": consumer,
            "stage": row["stage"], "next_action": row["next_action"],
            "next_action_at": _iso(row.get("next_action_at")), "activities": row.get("activities") or [],
            "version": row["version"], "updated_at": _iso(row["updated_at"])}
