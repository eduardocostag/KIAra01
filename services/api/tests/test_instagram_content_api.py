import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api.adapters.demo import DemoIdentityVerifier
from kiara_api.http.errors import ApiError
from kiara_api.instagram_content import create_instagram_content_router
from kiara_api.ports.identity import IdentityPrincipal


def client(role="owner"):
    app = FastAPI()

    class Verifier(DemoIdentityVerifier):
        async def verify(self, token):
            principal = await super().verify(token)
            return IdentityPrincipal(principal.user_id, principal.organization_id,
                                     principal.membership_id, role)

    app.state.identity_verifier = Verifier()

    @app.middleware("http")
    async def correlation(request, call_next):
        request.state.correlation_id = "test-instagram"
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def api_error(request, error):
        return JSONResponse({"code": error.code}, status_code=error.status_code)

    app.include_router(create_instagram_content_router())
    return TestClient(app)


HEADERS = {"Authorization": "Bearer kiara-local-demo"}


@pytest.mark.parametrize("path", ["/v1/instagram/skills", "/v1/instagram/skills/ig-reel"])
def test_skill_reads_require_verified_identity(path):
    assert client().get(path).status_code == 401
    assert client().get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_catalog_has_thirteen_skills_and_reads_references():
    session = client()
    result = session.get("/v1/instagram/skills", headers=HEADERS)
    assert result.status_code == 200
    assert len(result.json()["items"]) == 13
    assert result.headers["cache-control"] == "no-store"
    reference = session.get("/v1/instagram/skills/ig-reel", headers=HEADERS,
                            params={"resource": "hooks.json"})
    assert reference.status_code == 200
    assert reference.json()["trust"] == "untrusted_reference"
    assert "hooks" in reference.json()["content"]


@pytest.mark.parametrize("resource", ["../../../../config.py", "hookscore.py", "../ig-human/slop.json"])
def test_skill_resources_cannot_escape_or_expose_executables(resource):
    result = client().get("/v1/instagram/skills/ig-reel", headers=HEADERS,
                          params={"resource": resource})
    assert result.status_code == 404


def test_check_enforces_identity_and_drafting_role():
    body = {"operation": "caption", "text": "Private draft"}
    assert client().post("/v1/instagram/content-check", json=body).status_code == 401
    assert client("viewer").post("/v1/instagram/content-check", headers=HEADERS,
                                 json=body).status_code == 403


@pytest.mark.parametrize("operation", ["caption", "hookscore", "humanize", "detect", "beats"])
def test_checks_use_real_local_utilities(operation):
    result = client("operator").post("/v1/instagram/content-check", headers=HEADERS,
                                     json={"operation": operation, "text": "I lost $18000 on one contract."})
    assert result.status_code == 200, result.text
    assert result.json()["result"]
    assert result.json()["metadata"]["local_only"]
    assert result.json()["publishing"] is False
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("body", [
    {"operation": "caption", "text": "draft", "organization_id": "other"},
    {"operation": "caption", "text": "x" * 12001},
    {"operation": "publish", "text": "draft"},
    {"operation": "beats", "text": "draft", "wpm": 0},
    {"operation": "caption", "text": ""},
])
def test_checks_reject_invalid_or_tenant_injected_data(body):
    result = client().post("/v1/instagram/content-check", headers=HEADERS, json=body)
    assert result.status_code == 422
