from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.errors import ApiError


class CompetitionRepository:
    """Tenant-scoped archive kept deliberately separate from the CRM tables."""

    def __init__(self, postgres: PostgresRepository) -> None:
        self._postgres = postgres

    async def begin_kiara_job(
        self,
        organization_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        *,
        mode: str,
        target: str,
        normalized_target: str,
        media_id: str | None,
        name: str,
    ) -> dict[str, Any]:
        organization_uuid = _uuid("organization", organization_id)
        job_id = uuid4()
        provider_analysis_id = f"kiara_{job_id.hex}"
        async with self._postgres._transaction(organization_id) as connection:
            await connection.execute(
                """INSERT INTO competition_analysis_jobs
                   (organization_id,id,idempotency_key,request_fingerprint,provider_analysis_id,
                    mode,target,normalized_target,media_id,name)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (organization_id,idempotency_key) DO NOTHING""",
                (
                    organization_uuid,
                    job_id,
                    idempotency_key,
                    request_fingerprint,
                    provider_analysis_id,
                    mode,
                    target,
                    normalized_target,
                    media_id,
                    name,
                ),
            )
            row = await (
                await connection.execute(
                    """SELECT id,idempotency_key,request_fingerprint,provider_analysis_id,mode,
                              target,normalized_target,media_id,name,state,attempt_count,checkpoint,
                              error_code,error_message,available_at,lease_expires_at,created_at,
                              updated_at,completed_at,lease_owner
                       FROM competition_analysis_jobs
                       WHERE organization_id=%s AND idempotency_key=%s FOR UPDATE""",
                    (organization_uuid, idempotency_key),
                )
            ).fetchone()
            if row is None:
                raise RuntimeError("Competition job insert did not produce a row.")
            if row["request_fingerprint"] != request_fingerprint:
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "A Idempotency-Key já foi usada com outra pesquisa.",
                )
            if row["state"] == "completed":
                return self._job(row)
            if row["state"] == "failed":
                row = await (
                    await connection.execute(
                        """UPDATE competition_analysis_jobs
                           SET state='queued',error_code=NULL,error_message=NULL,available_at=now(),
                               completed_at=NULL,updated_at=now()
                           WHERE organization_id=%s AND id=%s
                           RETURNING id,idempotency_key,request_fingerprint,provider_analysis_id,mode,
                                     target,normalized_target,media_id,name,state,attempt_count,checkpoint,
                                     error_code,error_message,available_at,lease_expires_at,created_at,
                                     updated_at,completed_at""",
                        (organization_uuid, row["id"]),
                    )
                ).fetchone()
            await connection.execute(
                """INSERT INTO competition_analysis_work_queue (organization_id,job_id,available_at)
                   VALUES (%s,%s,%s)
                   ON CONFLICT (organization_id,job_id) DO UPDATE
                     SET available_at=LEAST(competition_analysis_work_queue.available_at,EXCLUDED.available_at),
                         lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                   WHERE competition_analysis_work_queue.lease_expires_at IS NULL
                      OR competition_analysis_work_queue.lease_expires_at < now()""",
                (organization_uuid, row["id"], row["available_at"]),
            )
        return self._job(row)

    async def claim_next_kiara_job(self, worker_id: str) -> dict[str, Any] | None:
        """Claim a queue identifier globally, then access its payload under tenant RLS."""
        async with await self._postgres._connect() as connection, connection.transaction():
            row = await (
                await connection.execute(
                    """WITH candidate AS (
                         SELECT organization_id,job_id
                         FROM competition_analysis_work_queue
                         WHERE available_at<=now()
                           AND (lease_owner IS NULL OR lease_expires_at<now())
                         ORDER BY available_at,created_at
                         FOR UPDATE SKIP LOCKED LIMIT 1
                       )
                       UPDATE competition_analysis_work_queue queue
                       SET lease_owner=%s,lease_expires_at=now()+interval '3 minutes',updated_at=now()
                       FROM candidate
                       WHERE queue.organization_id=candidate.organization_id
                         AND queue.job_id=candidate.job_id
                       RETURNING queue.organization_id,queue.job_id""",
                    (worker_id[:200],),
                )
            ).fetchone()
        if row is None:
            return None
        organization_id = str(row["organization_id"])
        async with self._postgres._transaction(organization_id) as connection:
            job = await (
                await connection.execute(
                    """UPDATE competition_analysis_jobs
                       SET state='running',attempt_count=attempt_count+1,error_code=NULL,
                           error_message=NULL,lease_expires_at=now()+interval '3 minutes',
                           lease_owner=%s,updated_at=now()
                       WHERE organization_id=%s AND id=%s AND
                         ((state IN ('queued','paused') AND available_at<=now()) OR
                          (state='running' AND lease_expires_at<now()))
                       RETURNING id,provider_analysis_id,mode,target,normalized_target,media_id,name,
                                 state,attempt_count,checkpoint,lease_owner""",
                    (worker_id[:200], _uuid("organization", organization_id), str(row["job_id"])),
                )
            ).fetchone()
        if job is None:
            await self._release_kiara_queue_lease(organization_id, str(row["job_id"]), worker_id)
            return None
        return {
            "organization_id": organization_id,
            **dict(job),
            "id": str(job["id"]),
        }

    async def _release_kiara_queue_lease(
        self, organization_id: str, job_id: str, worker_id: str
    ) -> None:
        async with await self._postgres._connect() as connection, connection.transaction():
            await connection.execute(
                """UPDATE competition_analysis_work_queue SET lease_owner=NULL,
                           lease_expires_at=NULL,updated_at=now()
                   WHERE organization_id=%s AND job_id=%s AND lease_owner=%s""",
                (_uuid("organization", organization_id), _uuid("competition_job", job_id), worker_id[:200]),
            )

    async def get_kiara_job(
        self, organization_id: str, job_id: str
    ) -> dict[str, Any] | None:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (
                await connection.execute(
                    """SELECT id,idempotency_key,provider_analysis_id,mode,target,name,state,
                              attempt_count,checkpoint,error_code,error_message,available_at,
                              lease_expires_at,created_at,updated_at,completed_at,lease_owner
                       FROM competition_analysis_jobs
                       WHERE organization_id=%s AND id=%s""",
                    (_uuid("organization", organization_id), _uuid("competition_job", job_id)),
                )
            ).fetchone()
        return self._job(row) if row else None

    async def checkpoint_kiara_job(
        self,
        organization_id: str,
        job_id: str,
        worker_id: str,
        checkpoint: dict[str, Any],
    ) -> None:
        async with self._postgres._transaction(organization_id) as connection:
            cursor = await connection.execute(
                """UPDATE competition_analysis_jobs
                   SET checkpoint=%s::jsonb,lease_expires_at=now()+interval '3 minutes',updated_at=now()
                   WHERE organization_id=%s AND id=%s AND state='running' AND lease_owner=%s""",
                (
                    json.dumps(checkpoint, ensure_ascii=False, default=str),
                    _uuid("organization", organization_id),
                    _uuid("competition_job", str(job_id)),
                    worker_id[:200],
                ),
            )
            if cursor.rowcount != 1:
                raise ApiError(409, "competition_job_not_running", "A pesquisa não está mais em execução.")

    async def _assert_kiara_job_lease(
        self,
        connection: Any,
        organization_id: str,
        job_id: str,
        worker_id: str,
    ) -> None:
        row = await (
            await connection.execute(
                """SELECT id FROM competition_analysis_jobs
                   WHERE organization_id=%s AND id=%s AND state='running'
                     AND lease_owner=%s AND lease_expires_at>now()
                   FOR UPDATE""",
                (
                    _uuid("organization", organization_id),
                    _uuid("competition_job", str(job_id)),
                    worker_id[:200],
                ),
            )
        ).fetchone()
        if row is None:
            raise ApiError(409, "competition_job_not_running", "A pesquisa não está mais em execução.")

    async def finish_kiara_job(
        self,
        organization_id: str,
        job_id: str,
        *,
        worker_id: str,
        state: str,
        checkpoint: dict[str, Any],
        error_code: str | None = None,
        error_message: str | None = None,
        retry_after: int = 0,
    ) -> None:
        if state not in {"queued", "paused", "completed", "failed"}:
            raise ValueError("Invalid competition job transition target.")
        async with self._postgres._transaction(organization_id) as connection:
            cursor = await connection.execute(
                """UPDATE competition_analysis_jobs
                   SET state=%s,checkpoint=%s::jsonb,error_code=%s,error_message=%s,
                       available_at=CASE WHEN %s IN ('paused','queued')
                           THEN now()+(%s * interval '1 second') ELSE now() END,
                       lease_expires_at=NULL,
                       lease_owner=NULL,
                       completed_at=CASE WHEN %s='completed' THEN now() ELSE NULL END,
                       updated_at=now()
                   WHERE organization_id=%s AND id=%s AND state='running' AND lease_owner=%s""",
                (
                    state,
                    json.dumps(checkpoint, ensure_ascii=False, default=str),
                    error_code[:100] if error_code else None,
                    error_message[:500] if error_message else None,
                    state,
                    max(0, retry_after),
                    state,
                    _uuid("organization", organization_id),
                    _uuid("competition_job", str(job_id)),
                    worker_id[:200],
                ),
            )
            if cursor.rowcount != 1:
                raise ApiError(409, "competition_job_not_running", "A pesquisa não está mais em execução.")
            if state in {"paused", "queued"}:
                await connection.execute(
                    """INSERT INTO competition_analysis_work_queue
                       (organization_id,job_id,available_at)
                       VALUES (%s,%s,now()+(%s * interval '1 second'))
                       ON CONFLICT (organization_id,job_id) DO UPDATE
                         SET available_at=EXCLUDED.available_at,lease_owner=NULL,
                             lease_expires_at=NULL,updated_at=now()""",
                    (
                        _uuid("organization", organization_id),
                        _uuid("competition_job", str(job_id)),
                        max(0, retry_after),
                    ),
                )
            else:
                await connection.execute(
                    """DELETE FROM competition_analysis_work_queue
                       WHERE organization_id=%s AND job_id=%s""",
                    (
                        _uuid("organization", organization_id),
                        _uuid("competition_job", str(job_id)),
                    ),
                )

    @staticmethod
    def _job(row: dict[str, Any]) -> dict[str, Any]:
        checkpoint = row["checkpoint"] or {}
        return {
            "id": str(row["id"]),
            "provider_analysis_id": row["provider_analysis_id"],
            "mode": row["mode"],
            "target": row["target"],
            "name": row["name"],
            "state": row["state"],
            "attempt_count": row["attempt_count"],
            "checkpoint": {
                key: checkpoint[key]
                for key in ("phase", "items_collected", "items_saved")
                if key in checkpoint
            },
            "error_code": row["error_code"],
            "error_message": row["error_message"],
            "available_at": _iso(row["available_at"]),
            "lease_expires_at": _iso(row["lease_expires_at"]),
            "lease_owner": row.get("lease_owner"),
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
            "completed_at": _iso(row["completed_at"]),
        }

    async def upsert_analysis(
        self,
        organization_id: str,
        provider_analysis_id: str,
        snapshot: dict[str, Any],
        *,
        mode: str | None = None,
        target: str | None = None,
        name: str | None = None,
        status: str | None = None,
        prospect_count: int | None = None,
        provider: str = "mailerfind",
        job_id: str | None = None,
        worker_id: str | None = None,
    ) -> dict[str, Any]:
        if (job_id is None) != (worker_id is None):
            raise ValueError("job_id and worker_id must be provided together.")
        organization_uuid = _uuid("organization", organization_id)
        safe_snapshot = json.dumps(snapshot, ensure_ascii=False, default=str)
        async with self._postgres._transaction(organization_id) as connection:
            if job_id is not None and worker_id is not None:
                await self._assert_kiara_job_lease(
                    connection, organization_id, job_id, worker_id
                )
            row = await (await connection.execute(
                """INSERT INTO competition_analyses
                   (organization_id,provider,provider_analysis_id,mode,target,name,status,prospect_count,provider_snapshot)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT (organization_id,provider,provider_analysis_id) DO UPDATE SET
                     mode=COALESCE(EXCLUDED.mode,competition_analyses.mode),
                     target=COALESCE(EXCLUDED.target,competition_analyses.target),
                     name=COALESCE(EXCLUDED.name,competition_analyses.name),
                     status=COALESCE(EXCLUDED.status,competition_analyses.status),
                     prospect_count=GREATEST(competition_analyses.prospect_count,EXCLUDED.prospect_count),
                     provider_snapshot=EXCLUDED.provider_snapshot,
                     updated_at=now(),last_synced_at=now()
                   RETURNING id,provider,provider_analysis_id,mode,target,name,status,prospect_count,created_at,updated_at""",
                (organization_uuid, provider, provider_analysis_id, mode, target, name, status or "created",
                 max(0, prospect_count or 0), safe_snapshot),
            )).fetchone()
        return self._analysis(row)

    async def list_analyses(self, organization_id: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self._postgres._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT id,provider,provider_analysis_id,mode,target,name,status,prospect_count,created_at,updated_at
                   FROM competition_analyses WHERE organization_id=%s
                   ORDER BY updated_at DESC,id DESC LIMIT %s""",
                (_uuid("organization", organization_id), limit),
            )).fetchall()
        return [self._analysis(row) for row in rows]

    async def get_analysis(self, organization_id: str, provider_analysis_id: str) -> dict[str, Any] | None:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT id,provider,provider_analysis_id,mode,target,name,status,prospect_count,created_at,updated_at
                   FROM competition_analyses WHERE organization_id=%s AND provider_analysis_id=%s""",
                (_uuid("organization", organization_id), provider_analysis_id),
            )).fetchone()
        return self._analysis(row) if row else None

    async def clear_analyses(self, organization_id: str) -> int:
        """Delete every archived analysis for one tenant; prospects cascade with analyses."""
        async with self._postgres._transaction(organization_id) as connection:
            cursor = await connection.execute(
                "DELETE FROM competition_analyses WHERE organization_id=%s",
                (_uuid("organization", organization_id),),
            )
            return max(0, cursor.rowcount)

    async def upsert_prospects(
        self,
        organization_id: str,
        provider_analysis_id: str,
        prospects: list[dict[str, Any]],
        *,
        job_id: str | None = None,
        worker_id: str | None = None,
    ) -> int:
        if (job_id is None) != (worker_id is None):
            raise ValueError("job_id and worker_id must be provided together.")
        if not prospects:
            return 0
        organization_uuid = _uuid("organization", organization_id)
        async with self._postgres._transaction(organization_id) as connection:
            if job_id is not None and worker_id is not None:
                await self._assert_kiara_job_lease(
                    connection, organization_id, job_id, worker_id
                )
            analysis = await (await connection.execute(
                """SELECT id FROM competition_analyses WHERE organization_id=%s AND provider_analysis_id=%s""",
                (organization_uuid, provider_analysis_id),
            )).fetchone()
            if not analysis:
                return 0
            saved = 0
            for prospect in prospects:
                username = _first_text(prospect, "username", "userName", "handle", "instagram_username")
                display_name = _first_text(prospect, "full_name", "fullName", "name", "display_name")
                email = _first_text(prospect, "email", "publicEmail", "public_email")
                phone = _first_text(prospect, "phone_number", "phone", "phoneNumber", "whatsapp")
                profile_url = _first_text(prospect, "profile_url", "profileUrl")
                whatsapp_url = _first_text(prospect, "whatsapp_url", "whatsappUrl")
                provider_id = _first_text(prospect, "id", "prospectId", "prospect_id", "pk")
                if not provider_id:
                    identity = "|".join((username.lower(), email.lower(), phone, display_name.lower()))
                    provider_id = hashlib.sha256(identity.encode()).hexdigest()
                await connection.execute(
                    """INSERT INTO competition_prospects
                       (organization_id,analysis_id,provider_prospect_id,instagram_username,display_name,
                        public_email,phone,profile_url,whatsapp_url,provider_snapshot)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                       ON CONFLICT (organization_id,analysis_id,provider_prospect_id) DO UPDATE SET
                         instagram_username=COALESCE(EXCLUDED.instagram_username,competition_prospects.instagram_username),
                         display_name=COALESCE(EXCLUDED.display_name,competition_prospects.display_name),
                         public_email=COALESCE(EXCLUDED.public_email,competition_prospects.public_email),
                         phone=COALESCE(EXCLUDED.phone,competition_prospects.phone),
                         profile_url=COALESCE(EXCLUDED.profile_url,competition_prospects.profile_url),
                         whatsapp_url=COALESCE(EXCLUDED.whatsapp_url,competition_prospects.whatsapp_url),
                         provider_snapshot=EXCLUDED.provider_snapshot,updated_at=now()""",
                    (organization_uuid, analysis["id"], provider_id, username or None, display_name or None,
                     email or None, phone or None, profile_url or None, whatsapp_url or None,
                     json.dumps(prospect, ensure_ascii=False, default=str)),
                )
                saved += 1
            await connection.execute(
                """UPDATE competition_analyses SET prospect_count=GREATEST(prospect_count,%s),updated_at=now()
                   WHERE organization_id=%s AND id=%s""",
                (saved, organization_uuid, analysis["id"]),
            )
        return saved

    async def list_prospects(self, organization_id: str, provider_analysis_id: str, limit: int) -> list[dict[str, Any]]:
        async with self._postgres._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT p.id,p.provider_prospect_id,p.instagram_username,p.display_name,p.public_email,p.phone,
                          p.profile_url,p.whatsapp_url,p.provider_snapshot,
                          p.created_at,p.updated_at
                   FROM competition_prospects p JOIN competition_analyses a
                     ON a.organization_id=p.organization_id AND a.id=p.analysis_id
                   WHERE p.organization_id=%s AND a.provider_analysis_id=%s
                   ORDER BY p.created_at,p.id LIMIT %s""",
                (_uuid("organization", organization_id), provider_analysis_id, limit),
            )).fetchall()
        return [{
            "id": str(row["id"]), "prospectId": row["provider_prospect_id"],
            "username": row["instagram_username"], "full_name": row["display_name"],
            "email": row["public_email"], "phone_number": row["phone"],
            "profile_url": row["profile_url"], "whatsapp_url": row["whatsapp_url"],
            "relationship_type": (row["provider_snapshot"] or {}).get("relationship_type"),
            "source_media_url": (row["provider_snapshot"] or {}).get("source_media_url"),
            "comment_text": (row["provider_snapshot"] or {}).get("comment_text"),
            "intent": (row["provider_snapshot"] or {}).get("intent"),
            "lead_score": (row["provider_snapshot"] or {}).get("lead_score"),
            "qualification_reason": (row["provider_snapshot"] or {}).get("qualification_reason"),
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat(),
        } for row in rows]

    @staticmethod
    def _analysis(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["provider_analysis_id"], "analysisId": row["provider_analysis_id"],
            "archiveId": str(row["id"]), "provider": row["provider"], "mode": row["mode"], "target": row["target"],
            "name": row["name"], "status": row["status"], "prospectCount": row["prospect_count"],
            "createdAt": row["created_at"].isoformat(), "updatedAt": row["updated_at"].isoformat(),
            "archived": True,
        }


def _first_text(value: dict[str, Any], *keys: str) -> str:
    for key in keys:
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()[:1000]
        if isinstance(item, (int, float)):
            return str(item)
    return ""
