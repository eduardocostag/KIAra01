from pathlib import Path


def test_competition_archive_is_tenant_scoped_and_separate_from_crm() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0016_competition_archive.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE competition_analyses" in sql
    assert "CREATE TABLE competition_prospects" in sql
    assert "ARRAY['competition_analyses', 'competition_prospects']" in sql
    assert "table_name || '_tenant_policy'" in sql
    assert "kiara.current_organization_id()" in sql
    assert "REFERENCES consumers" not in sql
    assert "REFERENCES pipeline_entries" not in sql
    assert "REFERENCES hunter_results" not in sql


def test_durable_competition_jobs_are_idempotent_and_tenant_scoped() -> None:
    sql = (
        Path(__file__).parents[1] / "migrations" / "0022_competition_durable_jobs.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE competition_analysis_jobs" in sql
    assert "UNIQUE (organization_id, idempotency_key)" in sql
    assert "request_fingerprint" in sql
    assert "lease_expires_at" in sql
    assert "checkpoint jsonb" in sql
    assert "kiara.current_organization_id()" in sql
    assert "ALTER TABLE competition_analysis_jobs FORCE ROW LEVEL SECURITY" in sql
    queue_sql = (
        Path(__file__).parents[1] / "migrations" / "0023_competition_work_queue.sql"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE competition_analysis_work_queue" in queue_sql
    assert "REFERENCES competition_analysis_jobs" in queue_sql
    assert "lease_owner" in queue_sql
    assert "available_at" in queue_sql
    assert "jsonb" not in queue_sql
    fencing_sql = (
        Path(__file__).parents[1] / "migrations" / "0024_competition_worker_fencing.sql"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN lease_owner text" in fencing_sql
    assert "(lease_expires_at IS NULL) = (lease_owner IS NULL)" in fencing_sql
