from pathlib import Path


def test_kiara_provider_migration_extends_archive_without_touching_crm() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0017_kiara_competition_provider.sql").read_text(encoding="utf-8")
    assert "'kiara_public'" in sql
    assert "ALTER TABLE competition_prospects" in sql
    assert "consumers" not in sql
    assert "pipeline_entries" not in sql
