from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError
from kiara_api.integrations import create_integration_router


@pytest.mark.parametrize("email", [None, "member@example.com", "admin@evil.test"])
@pytest.mark.parametrize(("method", "path", "body"), [
    ("GET", "", None),
    ("PUT", "/instagram_session", {"credentials": {"session_id": "test"}}),
    ("DELETE", "/instagram_session", None),
    ("GET", "/instagram-session/status", None),
    ("GET", "/hermes/capabilities", None),
    ("GET", "/postiz/credentials", None),
])
def test_non_system_admin_cannot_access_any_integration_route(email, method, path, body):
    repository = AsyncMock()
    app = FastAPI()
    app.include_router(create_integration_router(repository))
    context = RequestContext("user", "org", "membership", "owner", "request", email=email)
    app.dependency_overrides[authenticated_context] = lambda: context

    @app.exception_handler(ApiError)
    async def denied(_request, error):
        return JSONResponse({"code": error.code}, status_code=error.status_code)

    response = TestClient(app).request(method, "/v1/integrations" + path, json=body)
    assert response.status_code == 403
    assert response.json()["code"] == "system_admin_required"
    assert repository.mock_calls == []


def test_system_admin_can_list_integrations():
    repository = AsyncMock()
    repository.list.return_value = []
    app = FastAPI()
    app.include_router(create_integration_router(repository))
    context = RequestContext("user", "org", "membership", "owner", "request", email="admin@kiara.local")
    app.dependency_overrides[authenticated_context] = lambda: replace(context)
    response = TestClient(app).get("/v1/integrations")
    assert response.status_code == 200
    repository.list.assert_awaited_once_with("org")
