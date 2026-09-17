from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from services.api.kiara_api.http.errors import ApiError
from services.api.kiara_api.ports.identity import IdentityPrincipal
from services.api.kiara_api.workspace import create_workspace_router


class Verifier:
    def __init__(self, organization_id: str = "org_demo", role: str = "owner") -> None:
        self.organization_id = organization_id
        self.role = role

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        assert bearer_token == "test-token"
        return IdentityPrincipal("user_1", self.organization_id, "membership_1", self.role)


class ResetRepository:
    def __init__(self) -> None:
        self.contexts = []

    async def reset_commercial_data(self, context):
        self.contexts.append(context)
        return {"leads": 12, "pipeline_entries": 10, "searches": 3, "conversations": 2, "activities": 4}


def client(*, organization_id: str = "org_demo", role: str = "owner") -> tuple[TestClient, ResetRepository]:
    app = FastAPI()
    repository = ResetRepository()
    app.state.identity_verifier = Verifier(organization_id, role)

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        request.state.correlation_id = str(uuid4())
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "request_id": request.state.correlation_id}},
        )

    app.include_router(create_workspace_router(repository))
    return TestClient(app), repository


AUTH = {"Authorization": "Bearer test-token"}


def test_owner_can_reset_only_the_authenticated_workspace() -> None:
    api, repository = client(organization_id="org_customer_a")
    with api:
        response = api.request(
            "DELETE",
            "/v1/workspace/commercial-data",
            headers=AUTH,
            json={"confirmation": "ZERAR"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    assert response.json()["deleted"]["leads"] == 12
    assert response.json()["preserved"] == ["sales_profile", "message_templates", "integrations"]
    assert len(repository.contexts) == 1
    assert repository.contexts[0].organization_id == "org_customer_a"


def test_reset_requires_owner_or_admin() -> None:
    api, repository = client(role="operator")
    with api:
        response = api.request(
            "DELETE",
            "/v1/workspace/commercial-data",
            headers=AUTH,
            json={"confirmation": "ZERAR"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"
    assert repository.contexts == []


def test_reset_requires_exact_confirmation_and_rejects_tenant_injection() -> None:
    api, repository = client()
    with api:
        wrong_confirmation = api.request(
            "DELETE",
            "/v1/workspace/commercial-data",
            headers=AUTH,
            json={"confirmation": "zerar"},
        )
        injected_tenant = api.request(
            "DELETE",
            "/v1/workspace/commercial-data",
            headers=AUTH,
            json={"confirmation": "ZERAR", "organization_id": "org_other"},
        )

    assert wrong_confirmation.status_code == 422
    assert injected_tenant.status_code == 422
    assert repository.contexts == []
