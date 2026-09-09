from pathlib import Path

SQL = (Path(__file__).parents[1] / "migrations" / "0004_sales_workspace.sql").read_text(encoding="utf-8")


def test_sales_migration_is_atomic_and_tenant_scoped() -> None:
    assert SQL.lstrip().startswith("BEGIN;")
    assert SQL.rstrip().endswith("COMMIT;")
    for table in ("sales_profiles", "outreach_activities"):
        assert f"CREATE TABLE {table}" in SQL
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in SQL
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in SQL
        assert f"CREATE POLICY {table}_tenant_policy" in SQL


def test_outreach_requires_human_status_and_pipeline_reference() -> None:
    assert "status IN ('opened', 'sent', 'replied', 'no_response')" in SQL
    assert "REFERENCES pipeline_entries (organization_id, id)" in SQL
    assert "WHERE next_follow_up_at IS NOT NULL AND status = 'sent'" in SQL
