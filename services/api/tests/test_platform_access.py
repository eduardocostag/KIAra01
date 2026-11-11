"""Read-only platform endpoints, tenant guards and trusted policy regression tests."""

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.adapters.postgres import _uuid
from kiara_api.config import ApiSettings
from kiara_api.http.errors import ApiError
from kiara_api.main import create_app
from kiara_api.platform.access import PlatformAccessRepository
from kiara_api.platform.router import create_platform_router
from kiara_api.ports.identity import IdentityPrincipal


class Cursor:
    def __init__(self, row):
        self.row = row

    async def fetchone(self):
        return self.row


class Connection:
    def __init__(self, organizations, memberships):
        self.organizations, self.memberships = organizations, memberships
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def transaction(self):
        return self

    async def execute(self, query, params=()):
        self.calls.append((query, params))
        if "FROM organizations" in query:
            return Cursor(self.organizations.get(params[0]))
        if "FROM memberships" in query:
            return Cursor(self.memberships.get(tuple(params)))
        assert query == "SET TRANSACTION READ ONLY" or query.startswith("SELECT set_config(")
        return Cursor(None)


class Database:
    def __init__(self, organizations, memberships):
        self.connection = Connection(organizations, memberships)

    async def _connect(self):
        return self.connection


def principal(user="alice", organization=None, role="owner", email=None):
    identity_email = (
        "admin@kiara.local" if user == "alice" else f"{user}@example.test"
    ) if email is None else email
    return IdentityPrincipal(
        user, organization or user, f"{organization or user}:{user}", role, identity_email
    )


def database(
    organization="company-a", user="alice", role="operator", status="active", org_status="active"
):
    return Database(
        {_uuid("organization", organization): {"name": organization, "status": org_status}},
        {
            (_uuid("organization", organization), _uuid("user", user)): {
                "id": "persisted-member",
                "role": role,
                "status": status,
            }
        },
    )


def client(identity=None, db=None):
    app = FastAPI()
    identity = identity or principal()

    class Verifier:
        async def verify(self, token):
            if token != "valid-token":
                raise ApiError(401, "invalid_token", "Invalid token")
            return identity

    app.state.identity_verifier = Verifier()

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = "platform-test"
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def error_handler(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=error.status_code)

    app.include_router(create_platform_router(PlatformAccessRepository(db)))
    return TestClient(app)


AUTH = {"Authorization": "Bearer valid-token"}


@pytest.fixture(autouse=True)
def clean_policy(monkeypatch):
    monkeypatch.delenv("KIARA_PLATFORM_POLICY_JSON", raising=False)


@pytest.mark.parametrize("path", ["context", "modules/leads", "skills", "portfolio"])
def test_platform_requires_authentication(path):
    assert client().get("/v1/platform/" + path).status_code == 401
    assert (
        client()
        .get("/v1/platform/" + path, headers={"Authorization": "Bearer invalid"})
        .status_code
        == 401
    )


def test_personal_legacy_context_preserves_leads_and_marks_new_modules_as_preparation():
    result = client().get("/v1/platform/context", headers=AUTH)
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    payload = result.json()
    assert payload["brand"] == "KIARA"
    assert payload["organization"]["id"] == "alice"
    assert payload["platform_role"] == "platform_admin"
    assert payload["phase"] == "structure_only"
    assert payload["external_execution_enabled"] is False
    assert payload["access_source"] == "legacy_personal_workspace"
    modules = {module["key"]: module for module in payload["modules"]}
    assert modules["leads"]["href"] == "/app"
    assert modules["leads"]["status"] == "operational"
    assert all(module["enabled"] is True for module in modules.values())
    assert all(modules[key]["status"] == "preparation" for key in ("ti", "whatsapp", "atendimento"))


def test_company_requires_persisted_active_membership_and_ignores_tenant_injection():
    db = database()
    session = client(principal(organization="company-a"), db)
    result = session.get(
        "/v1/platform/context?organization_id=company-b",
        headers={**AUTH, "X-Organization-ID": "company-b"},
    )
    assert result.status_code == 200
    assert result.json()["organization"]["id"] == "company-a"
    assert result.json()["membership"] == {"id": "persisted-member", "role": "operator"}
    assert db.connection.calls[0][0] == "SET TRANSACTION READ ONLY"
    queries = " ".join(query for query, _ in db.connection.calls)
    assert all(word not in queries for word in ("INSERT", "UPDATE", "DELETE"))
    assert len([query for query, _ in db.connection.calls if "FROM" in query]) == 2
    assert (
        client(principal(organization="company-b"), db)
        .get("/v1/platform/context", headers=AUTH)
        .status_code
        == 403
    )
    assert (
        client(principal(organization="company-a"))
        .get("/v1/platform/context", headers=AUTH)
        .status_code
        == 403
    )


@pytest.mark.parametrize("status", ["revoked", "invited"])
@pytest.mark.parametrize("personal", [True, False])
def test_inactive_membership_cannot_use_legacy_fallback(status, personal):
    organization = "alice" if personal else "company-a"
    result = client(
        principal(organization=organization), database(organization=organization, status=status)
    ).get("/v1/platform/context", headers=AUTH)
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "platform_membership_inactive"


@pytest.mark.parametrize("status", ["suspended", "closed"])
def test_inactive_company_is_denied(status):
    result = client(principal(organization="company-a"), database(org_status=status)).get(
        "/v1/platform/context", headers=AUTH
    )
    assert result.status_code == 403


def test_persisted_role_downgrade_applies_module_restrictions(monkeypatch):
    monkeypatch.setenv(
        "KIARA_PLATFORM_POLICY_JSON",
        json.dumps(
            {
                "organizations": {
                    "company-a": {
                        "disabled_modules": ["whatsapp"],
                        "module_roles": {"ti": ["owner"]},
                    }
                }
            }
        ),
    )
    session = client(principal(organization="company-a", role="owner"), database(role="viewer"))
    result = session.get("/v1/platform/context", headers=AUTH)
    assert result.status_code == 200
    assert result.json()["membership"]["role"] == "viewer"
    assert {item["key"] for item in result.json()["modules"]} == {"leads", "atendimento"}
    for key in ("ti", "whatsapp"):
        assert session.get(f"/v1/platform/modules/{key}", headers=AUTH).status_code == 403
    assert session.get("/v1/platform/modules/leads", headers=AUTH).status_code == 200


def test_unknown_module_and_mutations_are_not_supported():
    session = client()
    assert session.get("/v1/platform/modules/unknown", headers=AUTH).status_code == 404
    for path in ("context", "modules/ti", "skills", "portfolio"):
        assert session.post("/v1/platform/" + path, headers=AUTH, json={}).status_code == 405


def test_only_configured_admin_email_can_access_the_platform(monkeypatch):
    monkeypatch.setenv(
        "KIARA_PLATFORM_POLICY_JSON", json.dumps({"platform_admin_user_ids": ["alice"]})
    )
    identity = IdentityPrincipal("alice", "alice", "alice:alice", "admin", "other@example.test")
    session = client(identity)
    result = session.get("/v1/platform/context", headers=AUTH)
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "platform_admin_only"
    assert session.get("/v1/platform/portfolio", headers=AUTH).status_code == 403


def test_admin_email_is_confirmed_from_verified_identity_claim():
    identity = IdentityPrincipal("alice", "alice", "alice:alice", "owner", "ADMIN@KIARA.LOCAL")
    result = client(identity).get("/v1/platform/context", headers=AUTH)
    assert result.status_code == 200
    assert result.json()["platform_role"] == "platform_admin"


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "[]",
        '{"unrecognized_admin":true}',
        '{"organizations":{"alice":{"disabled_modules":["unknown"]}}}',
        '{"organizations":{"alice":{"disabled_modules":["leads"]}}}',
        '{"organizations":{"alice":{"module_roles":{"leads":["owner"]}}}}',
        '{"platform_admin_user_ids":["   "]}',
        '{"reseller_assignments":{"alice":["  "]}}',
    ],
)
def test_invalid_policy_only_disables_platform(monkeypatch, raw):
    monkeypatch.setenv("KIARA_PLATFORM_POLICY_JSON", raw)
    failed = client().get("/v1/platform/context", headers=AUTH)
    assert failed.status_code == 503
    assert failed.headers["cache-control"] == "no-store"

    class Verifier:
        async def verify(self, token):
            return principal()

    with TestClient(
        create_app(ApiSettings(environment="test"), identity_verifier=Verifier())
    ) as api:
        assert api.get("/v1/me", headers=AUTH).status_code == 200
        assert api.get("/v1/platform/context", headers=AUTH).status_code == 503


def test_admin_portfolio_only_returns_explicit_ids_without_customer_access(monkeypatch):
    monkeypatch.setenv(
        "KIARA_PLATFORM_POLICY_JSON",
        json.dumps(
            {
                "reseller_assignments": {
                    "reseller": ["customer-a", "customer-a"],
                    "bob": ["customer-b"],
                },
            }
        ),
    )
    from kiara_api.platform import service as platform_service

    monkeypatch.setattr(
        platform_service,
        "PLATFORM_ADMIN_EMAILS",
        frozenset({"admin@kiara.local", "reseller@example.test"}),
    )
    session = client(principal(user="reseller", email="reseller@example.test"))
    result = session.get("/v1/platform/portfolio?organization_id=customer-b", headers=AUTH)
    assert result.status_code == 200
    assert result.json()["platform_role"] == "platform_admin"
    assert result.json()["items"] == [{"organization_id": "customer-a"}]
    assert result.json()["scope"] == "assigned_metadata_only"
    assert (
        client(principal(organization="customer-a"))
        .get("/v1/platform/context", headers=AUTH)
        .status_code
        == 403
    )
    assert (
        client(principal(user="charlie", email="charlie@example.test"))
        .get("/v1/platform/portfolio", headers=AUTH)
        .status_code
        == 403
    )


def test_explicit_platform_admin_has_no_implicit_customer_portfolio_or_operational_access(
    monkeypatch,
):
    monkeypatch.setenv(
        "KIARA_PLATFORM_POLICY_JSON", json.dumps({"platform_admin_user_ids": ["alice"]})
    )
    result = client().get("/v1/platform/portfolio", headers=AUTH)
    assert result.status_code == 200
    assert result.json()["platform_role"] == "platform_admin"
    assert result.json()["items"] == []
    assert (
        client(principal(organization="customer-a"))
        .get("/v1/platform/context", headers=AUTH)
        .status_code
        == 403
    )


def test_skills_reuse_existing_catalog_without_enabling_executors(monkeypatch):
    monkeypatch.setenv(
        "KIARA_PLATFORM_POLICY_JSON",
        json.dumps({"organizations": {"alice": {"disabled_modules": ["atendimento"]}}}),
    )
    result = client().get("/v1/platform/skills", headers=AUTH)
    assert result.status_code == 200
    items = result.json()["items"]
    assert any(item["name"] == "google-maps-scraper" for item in items)
    assert not any(item["name"] == "kiara-chatwoot" for item in items)
    assert all(
        item["trust"] == "untrusted_reference" and item["executor_status"] == "inactive"
        for item in items
    )
    assert all("content" not in item for item in items)


def test_packaged_skill_metadata_matches_existing_skill_catalog(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3]))
    from kiara_api.platform.skills_catalog import SKILLS_CATALOG

    from app.integrations.operational_skills import OperationalSkills

    assert list(SKILLS_CATALOG) == OperationalSkills().catalog()


def test_oversized_reseller_assignment_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "KIARA_PLATFORM_POLICY_JSON",
        json.dumps(
            {
                "reseller_assignments": {"alice": [f"customer-{index}" for index in range(1001)]},
            }
        ),
    )
    result = client().get("/v1/platform/portfolio", headers=AUTH)
    assert result.status_code == 503
    assert result.headers["cache-control"] == "no-store"


def test_personal_database_workspace_without_membership_preserves_legacy_access():
    db = Database(
        {_uuid("organization", "alice"): {"name": "Existing workspace", "status": "active"}}, {}
    )
    result = client(db=db).get("/v1/platform/context", headers=AUTH)
    assert result.status_code == 200
    assert result.json()["organization"]["name"] == "Existing workspace"
    assert result.json()["access_source"] == "legacy_personal_workspace"


def test_database_failure_is_fail_closed_for_platform(monkeypatch):
    from unittest.mock import AsyncMock

    import psycopg

    db = database()
    monkeypatch.setattr(
        db, "_connect", AsyncMock(side_effect=psycopg.OperationalError("unavailable"))
    )
    result = client(principal(organization="company-a"), db).get(
        "/v1/platform/context", headers=AUTH
    )
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "platform_access_unavailable"
    assert result.headers["cache-control"] == "no-store"


def test_new_platform_routes_match_canonical_contract():
    import yaml

    contract = yaml.safe_load(
        (Path(__file__).resolve().parents[3] / "packages/contracts/openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    implemented = client().app.openapi()["paths"]
    expected = {
        "/v1/platform/context",
        "/v1/platform/modules/{module_key}",
        "/v1/platform/skills",
        "/v1/platform/portfolio",
    }
    assert set(implemented) == expected
    for path in expected:
        assert set(implemented[path]) == {"get"}
        assert "get" in contract["paths"][path]
