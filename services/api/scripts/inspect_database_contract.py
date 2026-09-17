"""Print safe schema contract definitions used by API validation."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from apply_migrations import load_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    database_url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    if not database_url:
        raise SystemExit("URL do PostgreSQL ausente")
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        rows = connection.execute(
            """SELECT rel.relname, constraint_row.conname,
                      pg_get_constraintdef(constraint_row.oid)
               FROM pg_constraint constraint_row
               JOIN pg_class rel ON rel.oid=constraint_row.conrelid
               JOIN pg_namespace namespace_row ON namespace_row.oid=rel.relnamespace
               WHERE namespace_row.nspname='public'
                 AND constraint_row.contype='c'
                 AND rel.relname IN (
                   'hunter_searches','hunter_results','jobs','users','memberships',
                   'consumers','conversation_threads','messages','message_drafts',
                   'approvals','pipeline_entries','qualifications',
                   'integration_credentials','sales_profiles','outreach_activities'
                 )
               ORDER BY rel.relname,constraint_row.conname"""
        ).fetchall()
        integration_columns = connection.execute(
            """SELECT column_name,data_type
               FROM information_schema.columns
               WHERE table_schema='public' AND table_name='integration_credentials'
               ORDER BY ordinal_position"""
        ).fetchall()
        integration_indexes = connection.execute(
            """SELECT indexname,indexdef
               FROM pg_indexes
               WHERE schemaname='public' AND tablename='integration_credentials'
               ORDER BY indexname"""
        ).fetchall()
    for table, name, definition in rows:
        print(f"{table}.{name}={definition}")
    for name, data_type in integration_columns:
        print(f"integration_credentials.column.{name}={data_type}")
    for name, definition in integration_indexes:
        print(f"integration_credentials.index.{name}={definition}")


if __name__ == "__main__":
    main()
