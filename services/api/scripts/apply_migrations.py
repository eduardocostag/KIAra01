"""Apply pending numbered SQL migrations without logging database credentials."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env.local"))
    parser.add_argument("--only", help="Apply only this migration filename")
    args = parser.parse_args()
    load_env(args.env_file)
    database_url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("POSTGRES_URL_NON_POOLING, POSTGRES_URL ou DATABASE_URL não configurada")
    migration_dir = Path(__file__).parents[1] / "migrations"
    files = [migration_dir / args.only] if args.only else sorted(migration_dir.glob("*.sql"))
    with psycopg.connect(database_url, connect_timeout=10, autocommit=True) as connection:
        tracker_exists = connection.execute(
            "SELECT to_regclass('public.kiara_schema_migrations') IS NOT NULL"
        ).fetchone()[0]
        existing_schema = connection.execute(
            "SELECT to_regclass('public.hunter_searches') IS NOT NULL"
        ).fetchone()[0]
        connection.execute("""CREATE TABLE IF NOT EXISTS kiara_schema_migrations (
          filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
        )""")
        if not tracker_exists and existing_schema:
            target = args.only or "9999"
            for previous in sorted(migration_dir.glob("*.sql")):
                if previous.name >= target:
                    break
                connection.execute(
                    "INSERT INTO kiara_schema_migrations(filename) VALUES (%s) ON CONFLICT DO NOTHING",
                    (previous.name,),
                )
                print(f"baseline={previous.name}")
        applied = {row[0] for row in connection.execute("SELECT filename FROM kiara_schema_migrations")}
        for path in files:
            if not path.is_file():
                raise SystemExit(f"Migração não encontrada: {path.name}")
            if path.name in applied:
                print(f"skip={path.name}")
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO kiara_schema_migrations(filename) VALUES (%s)", (path.name,))
            print(f"applied={path.name}")


if __name__ == "__main__":
    main()
