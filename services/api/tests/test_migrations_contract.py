import re
from pathlib import Path

MIGRATION = Path(__file__).parents[1] / "migrations" / "0001_initial_postgres.sql"
SQL = MIGRATION.read_text(encoding="utf-8")

TENANT_TABLES = {
    "memberships",
    "consumers",
    "conversation_threads",
    "messages",
    "message_drafts",
    "approvals",
    "pipeline_entries",
    "pipeline_stage_events",
    "jobs",
    "outbox_events",
    "audit_events",
}


def table_definition(name: str) -> str:
    match = re.search(
        rf"CREATE TABLE {re.escape(name)} \((.*?)\n\);",
        SQL,
        flags=re.DOTALL,
    )
    assert match, f"missing CREATE TABLE for {name}"
    return match.group(1)


def test_migration_is_atomic_and_has_no_seed_data() -> None:
    assert SQL.lstrip().startswith("BEGIN;")
    assert SQL.rstrip().endswith("COMMIT;")
    assert not re.search(r"\bINSERT\s+INTO\b", SQL, flags=re.IGNORECASE)


def test_all_tenant_tables_require_organization_id() -> None:
    for table in TENANT_TABLES:
        definition = table_definition(table)
        assert re.search(r"organization_id uuid NOT NULL", definition)
        assert re.search(r"PRIMARY KEY \(organization_id, id\)", definition)


def test_rls_is_enabled_forced_and_fail_closed() -> None:
    assert "current_setting('app.organization_id', true)" in SQL
    assert "NULLIF(current_setting('app.organization_id', true), '')::uuid" in SQL
    for table in TENANT_TABLES:
        assert f"'{table}'" in SQL
    assert "ENABLE ROW LEVEL SECURITY" in SQL
    assert "FORCE ROW LEVEL SECURITY" in SQL
    assert "WITH CHECK (organization_id = kiara.current_organization_id())" in SQL


def test_cross_tenant_foreign_keys_include_organization_id() -> None:
    tenant_child_tables = {
        "conversation_threads",
        "messages",
        "message_drafts",
        "approvals",
        "pipeline_entries",
        "pipeline_stage_events",
    }
    for table in tenant_child_tables:
        definition = table_definition(table)
        assert "FOREIGN KEY (organization_id," in definition
        assert "REFERENCES" in definition
        assert "(organization_id, id)" in definition


def test_operational_queues_have_tenant_scoped_guards() -> None:
    jobs = table_definition("jobs")
    assert "UNIQUE (organization_id, idempotency_key)" in jobs
    assert "lease_expires_at" in jobs
    assert "max_attempts" in jobs
    assert "WHERE state IN ('queued', 'running')" in SQL
    assert "WHERE published_at IS NULL" in SQL


def test_provider_message_deduplication_allows_missing_external_ids() -> None:
    messages = table_definition("messages")
    assert "UNIQUE NULLS NOT DISTINCT" not in messages
    assert "ON messages (organization_id, provider_message_id)" in SQL
    assert "WHERE provider_message_id IS NOT NULL" in SQL
