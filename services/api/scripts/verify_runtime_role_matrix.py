"""Exercise every runtime write family in one transaction and roll it back."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from apply_migrations import load_env


def _psycopg_url(value: str) -> str:
    parts = urlsplit(value)
    query = urlencode([(key, item) for key, item in parse_qsl(parts.query) if key != "supa"])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    load_env(args.env_file)
    database_url = os.getenv("POSTGRES_URL")
    if not database_url:
        raise SystemExit("POSTGRES_URL ausente")

    organization, other_organization = uuid4(), uuid4()
    user, membership, consumer, thread = uuid4(), uuid4(), uuid4(), uuid4()
    draft, pipeline_entry, search, maximum_search = uuid4(), uuid4(), uuid4(), uuid4()
    body = "Mensagem de verificação transacional"
    content_hash = hashlib.sha256(body.encode()).hexdigest()

    with psycopg.connect(_psycopg_url(database_url), connect_timeout=10) as connection:
        role_flags = connection.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone()
        bypasses_rls = bool(role_flags and (role_flags[0] or role_flags[1]))
        connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(organization),))
        connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))
        connection.execute(
            "INSERT INTO organizations(id,slug,name) VALUES (%s,%s,'Runtime matrix')",
            (organization, f"matrix-{organization.hex[:12]}"),
        )
        ensured = connection.execute(
            "SELECT kiara.ensure_current_user('verification', %s)",
            (f"matrix-{user}",),
        ).fetchone()
        if not ensured or ensured[0] != user:
            raise SystemExit("Falha em users/ensure_current_user")
        connection.execute(
            "INSERT INTO memberships(organization_id,id,user_id,role,status) VALUES (%s,%s,%s,'owner','active')",
            (organization, membership, user),
        )
        connection.execute(
            "INSERT INTO consumers(organization_id,id,display_name,instagram_username) VALUES (%s,%s,'Runtime Lead',%s)",
            (organization, consumer, f"runtime_{consumer.hex[:12]}"),
        )
        connection.execute(
            "INSERT INTO conversation_threads(organization_id,id,consumer_id,channel,provider_thread_id) VALUES (%s,%s,%s,'instagram',%s)",
            (organization, thread, consumer, f"runtime-{thread}"),
        )
        connection.execute(
            "INSERT INTO messages(organization_id,thread_id,direction,body,sent_at) VALUES (%s,%s,'inbound',%s,%s)",
            (organization, thread, body, datetime.now(UTC)),
        )
        connection.execute(
            "INSERT INTO message_drafts(organization_id,id,thread_id,body,content_hash,created_by) VALUES (%s,%s,%s,%s,%s,%s)",
            (organization, draft, thread, body, content_hash, user),
        )
        connection.execute(
            "INSERT INTO approvals(organization_id,draft_id,draft_version,content_hash,decision,decided_by) VALUES (%s,%s,1,%s,'approved',%s)",
            (organization, draft, content_hash, user),
        )
        connection.execute(
            "INSERT INTO qualifications(organization_id,thread_id,score,temperature,recommendation) VALUES (%s,%s,80,'hot','Verificar contato')",
            (organization, thread),
        )
        connection.execute(
            "INSERT INTO pipeline_entries(organization_id,id,consumer_id,owner_membership_id,next_action) VALUES (%s,%s,%s,%s,'Revisar lead')",
            (organization, pipeline_entry, consumer, membership),
        )
        connection.execute(
            "INSERT INTO pipeline_stage_events(organization_id,pipeline_entry_id,to_stage,actor_user_id) VALUES (%s,%s,'new',%s)",
            (organization, pipeline_entry, user),
        )
        connection.execute(
            "INSERT INTO sales_profiles(organization_id,business_name,sender_name,offer,templates) VALUES (%s,'Runtime','Kiara','Teste',%s)",
            (organization, json.dumps({"first_contact": body})),
        )
        connection.execute(
            "INSERT INTO outreach_activities(organization_id,pipeline_entry_id,actor_user_id,channel,status,body) VALUES (%s,%s,%s,'instagram','opened',%s)",
            (organization, pipeline_entry, user, body),
        )
        connection.execute(
            "INSERT INTO hunter_searches(organization_id,id,requested_by,market,query,sources,result_limit) VALUES (%s,%s,%s,'b2b','runtime matrix',ARRAY['web'],5)",
            (organization, search, user),
        )
        connection.execute(
            "INSERT INTO hunter_searches(organization_id,id,requested_by,market,query,sources,result_limit) VALUES (%s,%s,%s,'b2b','runtime maximum',ARRAY['web'],100)",
            (organization, maximum_search, user),
        )
        connection.execute(
            "INSERT INTO hunter_results(organization_id,search_id,source,title,url,public_data) VALUES (%s,%s,'web','Runtime result','https://example.com/runtime',%s)",
            (organization, search, json.dumps({"verification": True})),
        )
        connection.execute(
            "INSERT INTO jobs(organization_id,kind,payload,idempotency_key,max_attempts) VALUES (%s,'hunter.search',%s,%s,12)",
            (organization, json.dumps({"search_id": str(search)}), f"matrix:{search}"),
        )
        connection.execute(
            "INSERT INTO hunter_work_queue(organization_id,search_id) VALUES (%s,%s)",
            (organization, search),
        )
        connection.execute(
            "INSERT INTO outbox_events(organization_id,aggregate_type,aggregate_id,event_type,payload) VALUES (%s,'lead',%s,'runtime.verified',%s)",
            (organization, consumer, json.dumps({"verified": True})),
        )
        connection.execute(
            "INSERT INTO audit_events(organization_id,actor_user_id,action,resource_type,resource_id,correlation_id) VALUES (%s,%s,'runtime.verified','lead',%s,%s)",
            (organization, user, consumer, f"matrix-{uuid4()}"),
        )
        connection.execute(
            """INSERT INTO integration_credentials(
                 organization_id,provider,encrypted_credentials,configured_fields,
                 hermes_instance_id,hermes_endpoint_fingerprint
               ) VALUES (%s,'hermes','verification',ARRAY['api_key','endpoint_url','instance_id'],%s,%s)""",
            (organization, f"matrix-{organization}", organization.hex),
        )
        connection.execute(
            "UPDATE pipeline_entries SET stage='qualified',version=version+1 WHERE organization_id=%s AND id=%s",
            (organization, pipeline_entry),
        )

        connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(other_organization),))
        visible = connection.execute(
            "SELECT id FROM consumers WHERE organization_id=%s",
            (organization,),
        ).fetchall()
        if visible and not bypasses_rls:
            raise SystemExit("RLS expôs dados entre organizações")
        connection.rollback()

    isolation = "skipped_admin" if bypasses_rls else "ok"
    print(f"runtime_write_families=ok tenant_isolation={isolation} transaction=rolled_back")


if __name__ == "__main__":
    main()
