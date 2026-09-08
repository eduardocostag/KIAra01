"""Read-only diagnosis of one Hunter request; never prints credentials or lead data."""
import argparse
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from kiara_api.adapters.postgres import _psycopg_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("search_id", type=UUID)
    args = parser.parse_args()
    values = {}
    for line in (Path(__file__).resolve().parents[1] / ".env.local").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key == "POSTGRES_URL":
            values[key] = json.loads(value) if value.startswith('"') else value
    try:
        with psycopg.connect(_psycopg_url(values["POSTGRES_URL"]), row_factory=dict_row, connect_timeout=10) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            row = connection.execute(
                """SELECT s.id,s.status,s.sources,s.created_at,s.updated_at,s.error_code,
                          (SELECT count(*) FROM hunter_results r WHERE r.organization_id=s.organization_id AND r.search_id=s.id) result_count
                   FROM hunter_searches s WHERE s.id=%s""", (args.search_id,),
            ).fetchone()
            print(json.dumps(row, default=str))
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
