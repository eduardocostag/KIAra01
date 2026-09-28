from pathlib import Path

import pytest

from kiara_api.http.errors import ApiError
from kiara_api.integrations import _validate_credentials


def test_postiz_accepts_cloud_and_local_endpoints() -> None:
    _validate_credentials("postiz", {
        "endpoint_url": "https://api.postiz.com",
        "api_key": "postiz-test-api-key-123456",
    })
    _validate_credentials("postiz", {
        "endpoint_url": "http://localhost:4007",
        "api_key": "postiz-local-api-key-1234",
    })


@pytest.mark.parametrize("endpoint", [
    "http://postiz.example.com",
    "https://user:secret@postiz.example.com",
    "https://postiz.example.com/public/v1",
    "https://postiz.example.com?key=value",
])
def test_postiz_rejects_unsafe_or_non_base_endpoint(endpoint: str) -> None:
    with pytest.raises(ApiError) as error:
        _validate_credentials("postiz", {
            "endpoint_url": endpoint,
            "api_key": "postiz-test-api-key-123456",
        })
    assert error.value.code == "invalid_postiz_endpoint"


def test_postiz_migration_extends_provider_constraint() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0019_postiz_integration.sql").read_text(encoding="utf-8")
    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "'postiz'" in sql
    assert "VALIDATE CONSTRAINT integration_credentials_provider_check" in sql
