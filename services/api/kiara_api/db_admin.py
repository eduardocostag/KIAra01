"""Worker-only database maintenance against the API's own production database.

The production connection string never leaves Vercel: the worker (KIARA_WORKER_TOKEN) asks the API itself to
report which database it uses and to apply a numbered migration shipped in this release. Only files from the
release's `migrations/` folder, one at a time, tracked with a checksum like scripts/apply_migrations.py.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from .adapters.postgres import PostgresRepository
from .http.errors import ApiError

_NAME = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")


def _migration_dir() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "migrations", here.parents[2] / "migrations"):
        if candidate.is_dir():
            return candidate
    raise ApiError(503, "migrations_missing", "Migrações não incluídas nesta versão.")


def _authorize(request: Request) -> None:
    expected = os.getenv("KIARA_WORKER_TOKEN") or os.getenv("CRON_SECRET")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise ApiError(401, "worker_unauthorized", "Worker não autorizado.")


def create_db_admin_router(postgres: PostgresRepository | None) -> APIRouter:
    router = APIRouter(tags=["internal"])

    def store() -> PostgresRepository:
        if postgres is None:
            raise ApiError(503, "database_not_configured", "Banco de dados não configurado.")
        return postgres

    @router.get("/v1/internal/db/status")
    async def status(request: Request) -> dict[str, Any]:
        _authorize(request)
        async with await store()._connect() as connection:
            info = await (await connection.execute(
                """SELECT current_database() AS database, (SELECT count(*) FROM conversation_threads) AS threads,
                          (SELECT count(*) FROM consumers) AS consumers""")).fetchone()
            applied = [row["filename"] for row in await (await connection.execute(
                "SELECT filename FROM kiara_schema_migrations ORDER BY filename")).fetchall()]
            # Real schema evidence, independent of the tracker table (which a restricted role may not see).
            evidence = await (await connection.execute(
                """SELECT current_user AS role, (SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user) AS bypass_rls,
                          to_regclass('public.action_requests') IS NOT NULL AS has_0030_action_requests,
                          to_regclass('public.conversation_threads') IS NOT NULL AS has_0028_threads,
                          (SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass('public.kiara_schema_migrations')) AS tracker_rls,
                          (SELECT pg_get_constraintdef(oid) FROM pg_constraint
                            WHERE conname='integration_credentials_provider_check' LIMIT 1) AS provider_check""")).fetchone()
        shipped = sorted(path.name for path in _migration_dir().glob("*.sql"))
        # A fingerprint (not the address) is enough to tell two databases apart without revealing anything.
        fingerprint = hashlib.sha256((os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or "").split("@")[-1].encode()).hexdigest()[:12]
        return {"database": info["database"], "fingerprint": fingerprint, "threads": info["threads"], "consumers": info["consumers"],
                "pending": [name for name in shipped if name not in applied],
                "schema": {**evidence, "accepts_whatsapp_cloud": "whatsapp_cloud" in str(evidence.get("provider_check") or "")}}

    @router.post("/v1/internal/db/migrate/{filename}")
    async def migrate(filename: str, request: Request) -> dict[str, Any]:
        _authorize(request)
        if not _NAME.fullmatch(filename):
            raise ApiError(422, "invalid_migration", "Nome de migração inválido.")
        path = _migration_dir() / filename
        if not path.is_file():
            raise ApiError(404, "migration_not_found", "Migração não encontrada nesta versão.")
        contents = path.read_bytes()
        checksum = hashlib.sha256(contents).hexdigest()
        async with await store()._connect() as connection:
            await connection.set_autocommit(True)  # each migration file carries its own BEGIN/COMMIT
            await connection.execute("""CREATE TABLE IF NOT EXISTS kiara_schema_migrations (
              filename text PRIMARY KEY, checksum text, applied_at timestamptz NOT NULL DEFAULT now())""")
            row = await (await connection.execute("SELECT checksum FROM kiara_schema_migrations WHERE filename=%s", (filename,))).fetchone()
            if row:
                if row["checksum"] and row["checksum"] != checksum:
                    raise ApiError(409, "migration_changed", "Migração já aplicada foi alterada; crie uma nova.")
                return {"filename": filename, "status": "already_applied"}
            await connection.execute(contents.decode("utf-8"))
            await connection.execute("INSERT INTO kiara_schema_migrations(filename,checksum) VALUES (%s,%s)", (filename, checksum))
        return {"filename": filename, "status": "applied"}

    return router
