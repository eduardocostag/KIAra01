from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from services.api.kiara_api.config import ApiSettings
from services.api.kiara_api.main import create_app
from services.api.kiara_api.ports.identity import IdentityPrincipal


class StubVerifier:
    def __init__(self, organization_id: str = "org_demo") -> None:
        self.organization_id = organization_id

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        assert bearer_token == "test-token"
        return IdentityPrincipal("user_1", self.organization_id, "membership_1", "viewer")


def client(*, organization_id: str = "org_demo") -> TestClient:
    app = create_app(
        ApiSettings(environment="test", cors_origins=("https://kiara.test",)),
        identity_verifier=StubVerifier(organization_id),
    )
    return TestClient(app)


def test_health_and_correlation_header() -> None:
    with client() as api:
        response = api.get("/health/live", headers={"X-Correlation-ID": "trace-123"})
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["x-correlation-id"] == "trace-123"
        assert api.get("/health/ready").json() == {"status": "ok"}


def test_authentication_error_uses_standard_envelope() -> None:
    with client() as api:
        response = api.get("/v1/me")
    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "authentication_required"
    assert body["request_id"]
    assert body["details"] == {}


def test_me_and_inbox_are_derived_from_verified_tenant() -> None:
    headers = {"Authorization": "Bearer test-token"}
    with client() as api:
        me = api.get("/v1/me", headers=headers)
        inbox = api.get("/v1/inbox/threads", headers=headers)
    assert me.status_code == 200
    assert me.json()["organization"]["id"] == "org_demo"
    assert inbox.status_code == 200
    assert len(inbox.json()["items"]) == 1


def test_inbox_does_not_leak_between_tenants() -> None:
    headers = {"Authorization": "Bearer test-token"}
    with client(organization_id="org_other") as api:
        listing = api.get("/v1/inbox/threads", headers=headers)
        detail = api.get("/v1/inbox/threads/thread_demo_01", headers=headers)
    assert listing.json()["items"] == []
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "thread_not_found"


def test_cors_allows_only_configured_origin() -> None:
    with client() as api:
        allowed = api.options(
            "/v1/me",
            headers={
                "Origin": "https://kiara.test",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = api.options(
            "/v1/me",
            headers={
                "Origin": "https://evil.test",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert allowed.headers["access-control-allow-origin"] == "https://kiara.test"
    assert "access-control-allow-origin" not in denied.headers


def test_demo_auth_is_explicit_and_forbidden_in_production() -> None:
    closed_app = create_app(ApiSettings(environment="development", demo_auth_enabled=False))
    with TestClient(closed_app) as api:
        closed = api.get("/v1/me", headers={"Authorization": "Bearer any-token"})
    assert closed.status_code == 503
    assert closed.json()["error"]["code"] == "identity_unavailable"

    with pytest.raises(RuntimeError, match="forbidden"):
        create_app(ApiSettings(environment="production", demo_auth_enabled=True))

    demo_app = create_app(ApiSettings(environment="test", demo_auth_enabled=True))
    with TestClient(demo_app) as api:
        response = api.get(
            "/v1/me", headers={"Authorization": "Bearer kiara-local-demo"}
        )
    assert response.status_code == 200
    assert response.json()["organization"]["id"] == "org_demo"
