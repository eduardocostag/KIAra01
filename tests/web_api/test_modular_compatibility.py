"""Characterize the existing API and prove source/contract preservation offline."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from scripts.verify_modular_preservation import inspect_preservation
from services.api.kiara_api.adapters.demo import InMemoryInboxRepository
from services.api.kiara_api.config import ApiSettings
from services.api.kiara_api.main import create_app
from services.api.kiara_api.ports.identity import IdentityPrincipal

AUTH = {"Authorization": "Bearer preservation-token"}
THREAD = {
    "id": "preserved_thread", "organization_id": "org_preserved", "channel": "instagram",
    "consumer": {"id": "consumer_preserved", "display_name": "Contato de teste"},
    "status": "waiting_operator", "unread_count": 1, "updated_at": "2026-11-11T12:00:00Z",
    "version": 3, "messages": [], "drafts": [], "qualification": None,
}


class VerifiedIdentity:
    def __init__(self, organization: str = "org_preserved"):
        self.organization = organization

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        assert bearer_token == "preservation-token"
        return IdentityPrincipal("user_preserved", self.organization, "member_preserved", "viewer")


def api_client(organization: str = "org_preserved") -> TestClient:
    return TestClient(create_app(
        ApiSettings(environment="test", cors_origins=("https://preservation.test",)),
        identity_verifier=VerifiedIdentity(organization),
        inbox_repository=InMemoryInboxRepository([THREAD]),
    ))


def test_modular_addition_preserves_captured_sources_and_existing_contract():
    report = inspect_preservation()
    assert report["passed"], report


def test_all_database_configured_legacy_route_methods_are_preserved_without_database_io(monkeypatch):
    async def forbidden_connection(*args, **kwargs):
        pytest.fail("OpenAPI inspection must never connect to a database")

    monkeypatch.setattr("psycopg.AsyncConnection.connect", forbidden_connection)
    app = create_app(ApiSettings(
        environment="test", database_url="postgresql://synthetic:synthetic@127.0.0.1:1/never_connect",
        integration_encryption_key=Fernet.generate_key().decode(),
    ), identity_verifier=VerifiedIdentity())
    baseline = json.loads((Path(__file__).resolve().parents[2] /
        "evidence/kiara-modular/legacy-api-routes.json").read_text(encoding="utf-8"))
    expected = {(row["path"], method) for row in baseline for method in row["methods"]}
    actual = {(path, method.upper()) for path, operations in app.openapi()["paths"].items()
              for method in operations if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}}
    assert expected <= actual
    assert all(path.startswith("/v1/platform/") and method == "GET" for path, method in actual - expected)


def test_existing_health_and_identity_payloads_remain_compatible(monkeypatch):
    monkeypatch.delenv("KIARA_PLATFORM_POLICY_JSON", raising=False)
    with api_client() as api:
        for path in ("/health/live", "/health/ready"):
            response = api.get(path, headers={"X-Correlation-ID": "preservation-trace"})
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            assert response.headers["x-correlation-id"] == "preservation-trace"
        response = api.get("/v1/me", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user_preserved", "membership_id": "member_preserved",
        "organization": {"id": "org_preserved", "name": "Kiara Workspace", "slug": "org_preserved"},
        "role": "viewer", "capabilities": ["inbox.read"],
    }


def test_existing_inbox_payload_detail_and_etag_remain_compatible(monkeypatch):
    monkeypatch.delenv("KIARA_PLATFORM_POLICY_JSON", raising=False)
    with api_client() as api:
        listing = api.get("/v1/inbox/threads", headers=AUTH)
        detail = api.get("/v1/inbox/threads/preserved_thread", headers=AUTH)
    expected = {key: value for key, value in THREAD.items() if key not in {
        "organization_id", "messages", "drafts", "qualification",
    }}
    assert listing.status_code == 200
    assert listing.json() == {"items": [expected], "next_cursor": None, "has_more": False}
    assert detail.status_code == 200
    assert detail.headers["etag"] == '"3"'
    assert detail.json() == {key: value for key, value in THREAD.items() if key != "organization_id"}


@pytest.mark.parametrize("organization", ["org_other", "user_preserved"])
def test_new_platform_does_not_expand_legacy_tenant_scope(organization, monkeypatch):
    monkeypatch.delenv("KIARA_PLATFORM_POLICY_JSON", raising=False)
    with api_client(organization) as api:
        listing = api.get("/v1/inbox/threads", headers=AUTH)
        detail = api.get("/v1/inbox/threads/preserved_thread", headers=AUTH)
    assert listing.json() == {"items": [], "next_cursor": None, "has_more": False}
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "thread_not_found"


def test_legacy_identity_still_requires_authentication(monkeypatch):
    monkeypatch.delenv("KIARA_PLATFORM_POLICY_JSON", raising=False)
    with api_client() as api:
        response = api.get("/v1/me", headers={"X-Correlation-ID": "preservation-auth"})
    assert response.status_code == 401
    assert response.json() == {"error": {
        "code": "authentication_required", "message": "Autenticação obrigatória.",
        "request_id": "preservation-auth", "details": {},
    }}
