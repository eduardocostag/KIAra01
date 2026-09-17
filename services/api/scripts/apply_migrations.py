"""Apply pending numbered SQL migrations without logging database credentials."""
from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument(
        "--baseline-through",
        help="Explicitly mark legacy migrations through this filename as already applied.",
    )
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
          filename text PRIMARY KEY, checksum text, applied_at timestamptz NOT NULL DEFAULT now()
        )""")
        connection.execute("ALTER TABLE kiara_schema_migrations ADD COLUMN IF NOT EXISTS checksum text")
        if not tracker_exists and existing_schema:
            if not args.baseline_through:
                raise SystemExit(
                    "Esquema legado detectado sem histórico de migrações. "
                    "Informe --baseline-through explicitamente após auditar o banco."
                )
            for previous in sorted(migration_dir.glob("*.sql")):
                if previous.name > args.baseline_through:
                    break
                connection.execute(
                    "INSERT INTO kiara_schema_migrations(filename) VALUES (%s) ON CONFLICT DO NOTHING",
                    (previous.name,),
                )
                print(f"baseline={previous.name}")
        applied = {
            row[0]: row[1]
            for row in connection.execute("SELECT filename,checksum FROM kiara_schema_migrations")
        }
        for path in files:
            if not path.is_file():
                raise SystemExit(f"Migração não encontrada: {path.name}")
            contents = path.read_bytes()
            checksum = hashlib.sha256(contents).hexdigest()
            if path.name in applied:
                stored_checksum = applied[path.name]
                if stored_checksum and stored_checksum != checksum:
                    raise SystemExit(
                        f"Migração já aplicada foi alterada: {path.name}. "
                        "Crie uma nova migração corretiva."
                    )
                if not stored_checksum:
                    connection.execute(
                        "UPDATE kiara_schema_migrations SET checksum=%s WHERE filename=%s",
                        (checksum, path.name),
                    )
                    print(f"checksum={path.name}")
                print(f"skip={path.name}")
                continue
            connection.execute(contents.decode("utf-8"))
            connection.execute(
                "INSERT INTO kiara_schema_migrations(filename,checksum) VALUES (%s,%s)",
                (path.name, checksum),
            )
            print(f"applied={path.name}")


if __name__ == "__main__":
    main()
