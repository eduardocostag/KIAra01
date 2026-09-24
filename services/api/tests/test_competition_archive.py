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
