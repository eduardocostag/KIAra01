from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.hunter import SearchCreate


def test_hunter_requires_supported_sources_and_bounded_limit() -> None:
    with pytest.raises(ValidationError):
        SearchCreate(market="b2c", query="academia", sources=["private_instagram"], result_limit=10)
    with pytest.raises(ValidationError):
        SearchCreate(market="b2b", query="clinicas", sources=["web"], result_limit=100)


def test_hunter_schema_requires_confirmation_and_tenant_rls() -> None:
    migration = (Path(__file__).parents[1] / "migrations" / "0002_hunter.sql").read_text(encoding="utf-8")
    assert "pending_confirmation" in migration
    assert "confirmed_by" in migration
    assert "confirmed_at" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "kiara.current_organization_id()" in migration


def test_confirmation_is_a_separate_endpoint() -> None:
    source = (Path(__file__).parents[1] / "kiara_api" / "hunter.py").read_text(encoding="utf-8")
    assert '@router.post("/searches", status_code=201)' in source
    assert '@router.post("/searches/{search_id}/confirm")' in source
    assert "claim_confirmation" in source
