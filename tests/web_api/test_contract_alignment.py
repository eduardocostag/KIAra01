from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from services.api.kiara_api.adapters.demo import InMemoryInboxRepository
from services.api.kiara_api.config import ApiSettings
from services.api.kiara_api.main import create_app
from services.api.kiara_api.ports.identity import IdentityPrincipal

TestClient = pytest.importorskip("fastapi.testclient").TestClient
ROOT = Path(__file__).resolve().parents[2]
CONTRACT = yaml.safe_load((ROOT / "packages/contracts/openapi.yaml").read_text(encoding="utf-8"))
AUTH = {"Authorization": "Bearer contract-test-token"}


class TenantVerifier:
    def __init__(self, organization_id: str = "org_contract_a") -> None:
        self.organization_id = organization_id

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        assert bearer_token == "contract-test-token"
        return IdentityPrincipal(
            user_id="user_contract_01",
            organization_id=self.organization_id,
            membership_id="membership_contract_01",
            role="viewer",
        )


def make_client(
    *, organization_id: str = "org_contract_a", repository: InMemoryInboxRepository | None = None
) -> TestClient:
    return TestClient(
        create_app(
            ApiSettings(environment="test", cors_origins=("https://app.kiara.test",)),
            identity_verifier=TenantVerifier(organization_id),
            inbox_repository=repository,
        )
    )


def test_implemented_routes_and_methods_exist_in_canonical_contract() -> None:
    with make_client() as api:
        implemented = {
            (path, method.upper())
            for path, operations in api.app.openapi()["paths"].items()
            for method in operations
            if method.lower() in {"get", "post", "patch", "put", "delete"}
        }
    contracted = {
        (path, method.upper())
        for path, operations in CONTRACT["paths"].items()
        for method in operations
        if method.lower() in {"get", "post", "patch", "put", "delete"}
    }
    assert implemented == contracted


def test_missing_auth_uses_contract_error_envelope() -> None:
    with make_client() as api:
        response = api.get("/v1/me", headers={"X-Correlation-ID": "request-contract-01"})
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "authentication_required",
            "message": "Autenticação obrigatória.",
            "request_id": "request-contract-01",
            "details": {},
        }
    }


def test_demo_auth_requires_explicit_local_setting_and_is_forbidden_in_production() -> None:
    closed = create_app(ApiSettings(environment="development", demo_auth_enabled=False))
    with TestClient(closed) as api:
        unavailable = api.get("/v1/me", headers={"Authorization": "Bearer anything"})
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "identity_unavailable"

    demo = create_app(ApiSettings(environment="test", demo_auth_enabled=True))
    with TestClient(demo) as api:
        denied = api.get("/v1/me", headers={"Authorization": "Bearer wrong"})
        allowed = api.get(
            "/v1/me", headers={"Authorization": "Bearer kiara-local-demo"}
        )
    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["organization"]["id"] == "org_demo"

    with pytest.raises(RuntimeError, match="forbidden"):
        create_app(ApiSettings(environment="production", demo_auth_enabled=True))


def test_cors_preflight_allows_configured_origin_and_denies_unknown_origin() -> None:
    preflight = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Idempotency-Key, If-Match",
    }
    with make_client() as api:
        allowed = api.options(
            "/v1/me", headers={"Origin": "https://app.kiara.test", **preflight}
        )
        denied = api.options(
            "/v1/me", headers={"Origin": "https://attacker.invalid", **preflight}
        )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://app.kiara.test"
    assert "idempotency-key" in allowed.headers["access-control-allow-headers"].lower()
    assert "if-match" in allowed.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-origin" not in denied.headers


def test_invalid_correlation_value_is_replaced_and_never_reflected() -> None:
    malicious = "bad correlation\r\nX-Injected: yes"
    with make_client() as api:
        response = api.get("/health/live", headers={"X-Correlation-ID": malicious})
    generated = response.headers["x-correlation-id"]
    assert response.status_code == 200
    assert generated != malicious
    assert re.fullmatch(r"[0-9a-f-]{36}", generated)
    assert "x-injected" not in response.headers


def test_repository_and_http_responses_are_tenant_isolated() -> None:
    threads = [
        {
            "id": "thread_contract_a",
            "organization_id": "org_contract_a",
            "consumer": {
                "id": "consumer_contract_a",
                "display_name": "Tenant A",
                "instagram_username": "tenant_a",
            },
            "status": "open",
            "unread_count": 1,
            "updated_at": "2026-09-05T12:00:00Z",
            "version": 1,
            "messages": [],
            "drafts": [],
            "qualification": None,
        },
        {
            "id": "thread_contract_b",
            "organization_id": "org_contract_b",
            "consumer": {
                "id": "consumer_contract_b",
                "display_name": "Tenant B",
                "instagram_username": "tenant_b",
            },
            "status": "open",
            "unread_count": 0,
            "updated_at": "2026-09-05T12:00:00Z",
            "version": 1,
            "messages": [],
            "drafts": [],
            "qualification": None,
        },
    ]
    repository = InMemoryInboxRepository(threads)
    with make_client(organization_id="org_contract_a", repository=repository) as api:
        listing = api.get("/v1/inbox/threads", headers=AUTH)
        own = api.get("/v1/inbox/threads/thread_contract_a", headers=AUTH)
        foreign = api.get("/v1/inbox/threads/thread_contract_b", headers=AUTH)

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == ["thread_contract_a"]
    assert all("organization_id" not in item for item in listing.json()["items"])
    assert own.status_code == 200
    assert "organization_id" not in own.json()
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "thread_not_found"
    assert "org_contract_b" not in foreign.text
    assert "Tenant B" not in foreign.text


def test_current_user_and_health_shapes_match_contract_baseline() -> None:
    with make_client() as api:
        me = api.get("/v1/me", headers=AUTH)
        live = api.get("/health/live")
        ready = api.get("/health/ready")
    assert me.status_code == 200
    assert set(me.json()) == {
        "user_id",
        "membership_id",
        "organization",
        "role",
        "capabilities",
    }
    assert me.json()["organization"]["id"] == "org_contract_a"
    assert live.json() == {"status": "ok"}
    assert ready.json() == {"status": "ok"}
