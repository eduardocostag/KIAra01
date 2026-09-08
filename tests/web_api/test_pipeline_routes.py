from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from services.api.kiara_api.adapters.pipeline_memory import InMemoryPipelineRepository
from services.api.kiara_api.http.errors import ApiError
from services.api.kiara_api.http.routes.pipeline import create_pipeline_router
from services.api.kiara_api.ports.identity import IdentityPrincipal


class Verifier:
    def __init__(self, organization_id: str = "org_demo", role: str = "operator") -> None:
        self.organization_id = organization_id
        self.role = role

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        assert bearer_token == "test-token"
        return IdentityPrincipal("user_1", self.organization_id, "membership_1", self.role)


def client(*, organization_id: str = "org_demo", role: str = "operator") -> TestClient:
    app = FastAPI()
    app.state.identity_verifier = Verifier(organization_id, role)

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        request.state.correlation_id = str(uuid4())
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "request_id": request.state.correlation_id, "details": exc.details}},
        )

    app.include_router(create_pipeline_router(InMemoryPipelineRepository()))
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-token"}
COMMAND = {**AUTH, "If-Match": '"1"', "Idempotency-Key": "pipeline-command-0001"}


def test_pipeline_is_tenant_scoped_and_requires_operator() -> None:
    with client() as api:
        own = api.get("/v1/pipeline", headers=AUTH)
    with client(organization_id="org_other") as api:
        foreign = api.get("/v1/pipeline", headers=AUTH)
    with client(role="viewer") as api:
        denied = api.get("/v1/pipeline", headers=AUTH)

    assert [item["id"] for item in own.json()["items"]] == ["pipeline_demo_01"]
    assert "organization_id" not in own.text
    assert foreign.json()["items"] == []
    assert denied.status_code == 403


def test_pipeline_update_requires_etag_and_uses_compare_and_swap() -> None:
    with client() as api:
        missing = api.patch("/v1/pipeline/pipeline_demo_01", headers=AUTH, json={"stage": "won"})
        updated = api.patch(
            "/v1/pipeline/pipeline_demo_01",
            headers=COMMAND,
            json={"stage": "won", "next_action": None},
        )
        replay = api.patch(
            "/v1/pipeline/pipeline_demo_01",
            headers=COMMAND,
            json={"stage": "won", "next_action": None},
        )
        stale = api.patch(
            "/v1/pipeline/pipeline_demo_01",
            headers={
                **AUTH,
                "If-Match": '"1"',
                "Idempotency-Key": "pipeline-command-0002",
            },
            json={"stage": "lost"},
        )

    assert missing.status_code == 428
    assert updated.status_code == 200
    assert updated.json()["stage"] == "won"
    assert updated.json()["version"] == 2
    assert updated.headers["etag"] == '"2"'
    assert replay.json() == updated.json()
    assert replay.headers["etag"] == '"2"'
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "version_conflict"


def test_pipeline_update_does_not_accept_tenant_or_reveal_foreign_entry() -> None:
    with client() as api:
        injected = api.patch(
            "/v1/pipeline/pipeline_demo_01",
            headers=COMMAND,
            json={"stage": "won", "organization_id": "org_other"},
        )
    with client(organization_id="org_other") as api:
        foreign = api.patch(
            "/v1/pipeline/pipeline_demo_01",
            headers=COMMAND,
            json={"stage": "won"},
        )

    assert injected.status_code == 422
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "pipeline_entry_not_found"
    assert "org_demo" not in foreign.text


def test_pipeline_update_rejects_missing_or_reused_idempotency_key() -> None:
    with client() as api:
        missing = api.patch(
            "/v1/pipeline/pipeline_demo_01",
            headers={**AUTH, "If-Match": '"1"'},
            json={"stage": "won"},
        )
        first = api.patch(
            "/v1/pipeline/pipeline_demo_01", headers=COMMAND, json={"stage": "won"}
        )
        reused = api.patch(
            "/v1/pipeline/pipeline_demo_01", headers=COMMAND, json={"stage": "lost"}
        )

    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    assert first.status_code == 200
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "idempotency_conflict"
