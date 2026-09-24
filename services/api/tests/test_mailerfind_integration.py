from pathlib import Path

import pytest

from kiara_api.http.errors import ApiError
from kiara_api.integrations import _validate_credentials


def test_mailerfind_accepts_official_mcp_oauth_credentials() -> None:
    _validate_credentials("mailerfind", {
        "endpoint_url": "https://mcp.mailerfind.com/mcp",
        "access_token": "test-access-token",
        "client_id": "test-client",
        "token_type": "Bearer",
    })


@pytest.mark.parametrize("endpoint", [
    "http://mcp.mailerfind.com/mcp",
    "https://example.com/mcp",
    "https://mcp.mailerfind.com/other",
])
def test_mailerfind_rejects_non_official_endpoint(endpoint: str) -> None:
    with pytest.raises(ApiError) as error:
        _validate_credentials("mailerfind", {
            "endpoint_url": endpoint,
            "access_token": "test-access-token",
            "client_id": "test-client",
        })
    assert error.value.code == "invalid_mailerfind_endpoint"


def test_mailerfind_migration_extends_provider_constraint() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0014_mailerfind_integration.sql").read_text(encoding="utf-8")
    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "'mailerfind'" in sql
    assert "VALIDATE CONSTRAINT integration_credentials_provider_check" in sql


def test_global_mailerfind_migration_is_singleton_and_readable_by_workspaces() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0015_global_mailerfind.sql").read_text(encoding="utf-8")
    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "is_global boolean NOT NULL DEFAULT false" in sql
    assert "WHERE is_global" in sql
    assert "integration_credentials_global_read_policy" in sql
    assert "provider = 'mailerfind'" in sql
