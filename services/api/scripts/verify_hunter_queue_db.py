"""Exercise Hunter queue SQL against production and roll everything back."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from apply_migrations import load_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    url = os.getenv("POSTGRES_URL_NON_POOLING") or os.getenv("POSTGRES_URL")
    if not url:
        raise SystemExit("URL do PostgreSQL não configurada")
    tenants = [(uuid4(), uuid4(), uuid4()), (uuid4(), uuid4(), uuid4())]
    with psycopg.connect(url, connect_timeout=10) as connection:
        for organization, user, search in tenants:
            connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(organization),))
            connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))
            connection.execute("INSERT INTO organizations(id,slug,name) VALUES (%s,%s,'Queue verification')",
                               (organization, f"verify-{organization.hex[:12]}"))
            connection.execute("SELECT kiara.ensure_current_user('test', %s)", (f"verify-{user}",))
            connection.execute(
                """INSERT INTO hunter_searches
                   (organization_id,id,requested_by,market,query,sources,result_limit,status,confirmed_by,confirmed_at)
                   VALUES (%s,%s,%s,'b2b','queue verification',ARRAY['web'],10,'running',%s,now())""",
                (organization, search, user, user),
            )
            payload = {"search_id": str(search), "requested_by": str(user),
                       "membership_id": str(uuid4()), "role": "owner", "correlation_id": str(uuid4())}
            connection.execute(
                """INSERT INTO jobs(organization_id,kind,state,payload,idempotency_key,max_attempts)
                   VALUES (%s,'hunter.search','queued',%s,%s,12)""",
                (organization, json.dumps(payload), f"hunter.search:{search}"),
            )
            connection.execute("INSERT INTO hunter_work_queue(organization_id,search_id) VALUES (%s,%s)",
                               (organization, search))
        organization, _, search = tenants[0]
        connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(organization),))
        visible = connection.execute("SELECT id FROM hunter_searches").fetchall()
        if [row[0] for row in visible] != [search]:
            raise SystemExit("Falha de isolamento RLS entre organizações")
        leased = connection.execute(
            """UPDATE jobs SET state='running',attempts=attempts+1,lease_owner='verification',
                 lease_expires_at=now()+interval '4 minutes' WHERE organization_id=%s
                 AND payload->>'search_id'=%s RETURNING attempts""", (organization, str(search)),
        ).fetchone()
        if not leased or leased[0] != 1:
            raise SystemExit("Falha ao adquirir lease de teste")
        connection.rollback()
    print("queue_transaction=ok_rolled_back tenant_isolation=ok")


if __name__ == "__main__":
    main()
