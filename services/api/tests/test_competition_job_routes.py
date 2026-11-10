from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from kiara_api.competition import create_competition_router
from kiara_api.http.context import RequestContext
from kiara_api.http.dependencies import authenticated_context
from kiara_api.http.errors import ApiError


class _Archive:
    def __init__(self) -> None:
        self.created: dict[str, Any] | None = None

    async def begin_kiara_job(
        self,
        organization_id: str,
        idempotency_key: str,
        fingerprint: str,
        **parameters: Any,
    ) -> dict[str, Any]:
        self.created = {
            "organization_id": organization_id,
            "idempotency_key": idempotency_key,
            "fingerprint": fingerprint,
            **parameters,
        }
        return {
            "id": "7f02e6b0-1f6d-49e8-94d4-a4818e49d3c3",
            "provider_analysis_id": "kiara_test",
            "state": "queued",
            "attempt_count": 0,
        }


def _app(archive: _Archive) -> FastAPI:
    app = FastAPI()
    app.include_router(create_competition_router(archive))  # type: ignore[arg-type]

    @app.exception_handler(ApiError)
    async def handle_api_error(_request, error: ApiError):
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )

    app.dependency_overrides[authenticated_context] = lambda: RequestContext(
        "user", "org-test", "membership", "owner", "test"
    )
    return app


def test_analysis_route_enqueues_and_returns_without_running_worker() -> None:
    archive = _Archive()

    response = TestClient(_app(archive)).post(
        "/v1/competition/kiara/analyses",
        headers={"Idempotency-Key": "request-key-000001"},
        json={"mode": "followers", "target": "@example"},
    )

    assert response.status_code == 202
    assert response.json()["job"]["state"] == "queued"
    assert archive.created is not None
    assert archive.created["organization_id"] == "org-test"
    assert archive.created["normalized_target"] == "https://www.instagram.com/example/"


def test_analysis_route_requires_idempotency_key_before_enqueueing() -> None:
    archive = _Archive()

    response = TestClient(_app(archive)).post(
        "/v1/competition/kiara/analyses",
        json={"mode": "followers", "target": "@example"},
    )

    assert response.status_code == 400
    assert archive.created is None
