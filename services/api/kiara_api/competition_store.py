from __future__ import annotations

import hashlib
import json
from typing import Any

from .adapters.postgres import PostgresRepository, _uuid


class CompetitionRepository:
    """Tenant-scoped archive kept deliberately separate from the CRM tables."""

    def __init__(self, postgres: PostgresRepository) -> None:
        self._postgres = postgres

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
    ) -> dict[str, Any]:
        organization_uuid = _uuid("organization", organization_id)
        safe_snapshot = json.dumps(snapshot, ensure_ascii=False, default=str)
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """INSERT INTO competition_analyses
                   (organization_id,provider_analysis_id,mode,target,name,status,prospect_count,provider_snapshot)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   ON CONFLICT (organization_id,provider,provider_analysis_id) DO UPDATE SET
                     mode=COALESCE(EXCLUDED.mode,competition_analyses.mode),
                     target=COALESCE(EXCLUDED.target,competition_analyses.target),
                     name=COALESCE(EXCLUDED.name,competition_analyses.name),
                     status=COALESCE(EXCLUDED.status,competition_analyses.status),
                     prospect_count=GREATEST(competition_analyses.prospect_count,EXCLUDED.prospect_count),
                     provider_snapshot=EXCLUDED.provider_snapshot,
                     updated_at=now(),last_synced_at=now()
                   RETURNING id,provider_analysis_id,mode,target,name,status,prospect_count,created_at,updated_at""",
                (organization_uuid, provider_analysis_id, mode, target, name, status or "created",
                 max(0, prospect_count or 0), safe_snapshot),
            )).fetchone()
        return self._analysis(row)

    async def list_analyses(self, organization_id: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self._postgres._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT id,provider_analysis_id,mode,target,name,status,prospect_count,created_at,updated_at
                   FROM competition_analyses WHERE organization_id=%s
                   ORDER BY updated_at DESC,id DESC LIMIT %s""",
                (_uuid("organization", organization_id), limit),
            )).fetchall()
        return [self._analysis(row) for row in rows]

    async def get_analysis(self, organization_id: str, provider_analysis_id: str) -> dict[str, Any] | None:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT id,provider_analysis_id,mode,target,name,status,prospect_count,created_at,updated_at
                   FROM competition_analyses WHERE organization_id=%s AND provider='mailerfind'
                     AND provider_analysis_id=%s""",
                (_uuid("organization", organization_id), provider_analysis_id),
            )).fetchone()
        return self._analysis(row) if row else None

    async def upsert_prospects(
        self, organization_id: str, provider_analysis_id: str, prospects: list[dict[str, Any]]
    ) -> int:
        if not prospects:
            return 0
        organization_uuid = _uuid("organization", organization_id)
        async with self._postgres._transaction(organization_id) as connection:
            analysis = await (await connection.execute(
                """SELECT id FROM competition_analyses WHERE organization_id=%s AND provider='mailerfind'
                   AND provider_analysis_id=%s""",
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
                provider_id = _first_text(prospect, "id", "prospectId", "prospect_id", "pk")
                if not provider_id:
                    identity = "|".join((username.lower(), email.lower(), phone, display_name.lower()))
                    provider_id = hashlib.sha256(identity.encode()).hexdigest()
                await connection.execute(
                    """INSERT INTO competition_prospects
                       (organization_id,analysis_id,provider_prospect_id,instagram_username,display_name,
                        public_email,phone,provider_snapshot)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                       ON CONFLICT (organization_id,analysis_id,provider_prospect_id) DO UPDATE SET
                         instagram_username=COALESCE(EXCLUDED.instagram_username,competition_prospects.instagram_username),
                         display_name=COALESCE(EXCLUDED.display_name,competition_prospects.display_name),
                         public_email=COALESCE(EXCLUDED.public_email,competition_prospects.public_email),
                         phone=COALESCE(EXCLUDED.phone,competition_prospects.phone),
                         provider_snapshot=EXCLUDED.provider_snapshot,updated_at=now()""",
                    (organization_uuid, analysis["id"], provider_id, username or None, display_name or None,
                     email or None, phone or None, json.dumps(prospect, ensure_ascii=False, default=str)),
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
                          p.created_at,p.updated_at
                   FROM competition_prospects p JOIN competition_analyses a
                     ON a.organization_id=p.organization_id AND a.id=p.analysis_id
                   WHERE p.organization_id=%s AND a.provider='mailerfind' AND a.provider_analysis_id=%s
                   ORDER BY p.created_at,p.id LIMIT %s""",
                (_uuid("organization", organization_id), provider_analysis_id, limit),
            )).fetchall()
        return [{
            "id": str(row["id"]), "prospectId": row["provider_prospect_id"],
            "username": row["instagram_username"], "full_name": row["display_name"],
            "email": row["public_email"], "phone_number": row["phone"],
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat(),
        } for row in rows]

    @staticmethod
    def _analysis(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["provider_analysis_id"], "analysisId": row["provider_analysis_id"],
            "archiveId": str(row["id"]), "mode": row["mode"], "target": row["target"],
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
