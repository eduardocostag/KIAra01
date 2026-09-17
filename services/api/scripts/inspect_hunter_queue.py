"""Print non-PII operational Hunter queue state for production diagnosis."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from apply_migrations import load_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--correlation-id")
    args = parser.parse_args()
    load_env(args.env_file)
    url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    if not url:
        raise SystemExit("URL do PostgreSQL não configurada")
    with psycopg.connect(url, connect_timeout=10, row_factory=dict_row) as connection:
        queued = connection.execute(
            """SELECT organization_id,search_id,available_at,lease_expires_at
               FROM hunter_work_queue ORDER BY created_at DESC LIMIT 20"""
        ).fetchall()
        print(f"queue_count={len(queued)}")
        for control in queued:
            with connection.transaction():
                connection.execute("SELECT set_config('app.organization_id', %s, true)",
                                   (str(control["organization_id"]),))
                search = connection.execute(
                    """SELECT status,error_code,updated_at FROM hunter_searches
                       WHERE organization_id=%s AND id=%s""",
                    (control["organization_id"], control["search_id"]),
                ).fetchone()
                job = connection.execute(
                    """SELECT state,attempts,max_attempts,last_error_code,available_at,lease_expires_at
                       FROM jobs WHERE organization_id=%s AND kind='hunter.search'
                         AND payload->>'search_id'=%s""",
                    (control["organization_id"], str(control["search_id"])),
                ).fetchone()
                print({"search_id": str(control["search_id"]), "search": dict(search or {}), "job": dict(job or {})})
                if args.correlation_id:
                    events = connection.execute(
                        """SELECT action,occurred_at FROM audit_events
                           WHERE organization_id=%s AND correlation_id=%s ORDER BY occurred_at""",
                        (control["organization_id"], args.correlation_id),
                    ).fetchall()
                    if events:
                        print("correlation_events=" + str([dict(event) for event in events]))


if __name__ == "__main__":
    main()
