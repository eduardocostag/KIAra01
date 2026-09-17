"""Provision and verify a least-privilege PostgreSQL runtime role."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from apply_migrations import load_env
from psycopg import sql


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    admin_url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    password = os.getenv("KIARA_RUNTIME_DB_PASSWORD")
    if not admin_url or not password:
        raise SystemExit("Credencial administrativa ou KIARA_RUNTIME_DB_PASSWORD ausente")
    role = "kiara_app"
    with psycopg.connect(admin_url, connect_timeout=10, autocommit=True) as connection:
        connection.execute(sql.SQL(
            """DO $role$ BEGIN
                 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname={name}) THEN
                   CREATE ROLE {identifier} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
                 END IF;
               END $role$"""
        ).format(name=sql.Literal(role), identifier=sql.Identifier(role)))
        connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(connection.info.dbname), sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public,kiara TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA kiara TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO {}").format(sql.Identifier(role)))
    parts = urlsplit(admin_url)
    admin_user = parts.username or "postgres"
    suffix = admin_user.split(".", 1)[1] if "." in admin_user else ""
    runtime_user = f"{role}.{suffix}" if suffix else role
    host = parts.hostname or ""
    netloc = f"{quote(runtime_user)}:{quote(password)}@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    runtime_url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    with psycopg.connect(runtime_url, connect_timeout=10) as connection:
        role_row = connection.execute("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        if not role_row or role_row[1] or role_row[2]:
            raise SystemExit("A role de runtime ainda possui privilégio para ignorar RLS")
        first, second = uuid4(), uuid4()
        connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(first),))
        connection.execute("INSERT INTO organizations(id,slug,name) VALUES (%s,%s,'RLS verification')",
                           (first, f"verify-{first.hex[:12]}"))
        connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(second),))
        visible = connection.execute("SELECT id FROM organizations WHERE id=%s", (first,)).fetchall()
        if visible:
            raise SystemExit("RLS não isolou organizações para a nova role")
        connection.rollback()
    args.output.write_text(f"POSTGRES_URL={runtime_url}\n", encoding="utf-8")
    print("runtime_role=ok rls=ok")


if __name__ == "__main__":
    main()
