from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from services.api.kiara_api.adapters.conversations_demo import (
    InMemoryConversationCommandRepository,
)
from services.api.kiara_api.application.conversations import ConversationCommands
from services.api.kiara_api.http.errors import ApiError
from services.api.kiara_api.http.routes.conversations import create_conversation_router
from services.api.kiara_api.ports.identity import IdentityPrincipal


class StubVerifier:
    def __init__(self, *, organization_id: str = "org_demo", role: str = "owner") -> None:
        self.organization_id = organization_id
        self.role = role

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        assert bearer_token == "test-token"
        return IdentityPrincipal(
            "user_actor_01", self.organization_id, "membership_actor_01", self.role
        )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.correlation_id = str(uuid4())
        return await call_next(request)


def client(
    *,
    organization_id: str = "org_demo",
    role: str = "owner",
) -> tuple[TestClient, InMemoryConversationCommandRepository]:
    repository = InMemoryConversationCommandRepository()
    app = FastAPI()
    app.state.identity_verifier = StubVerifier(organization_id=organization_id, role=role)
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "request_id": request.state.correlation_id,
                    "details": exc.details,
                }
            },
        )

    app.include_router(create_conversation_router(ConversationCommands(repository)))
    return TestClient(app), repository


AUTH = {"Authorization": "Bearer test-token"}


def _create_draft(api: TestClient, key: str = "draft-key-000001") -> Response:
    return api.post(
        "/v1/inbox/threads/thread_demo_01/drafts",
        headers={**AUTH, "Idempotency-Key": key},
        json={"text": "Olá! Como posso ajudar?"},
    )


def test_create_draft_is_tenant_scoped_and_idempotent() -> None:
    api, _ = client()
    with api:
        first = _create_draft(api)
        replay = _create_draft(api)

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert first.headers["etag"] == '"1"'
    assert first.json()["status"] == "draft"
    assert len(first.json()["content_hash"]) == 64


def test_reusing_idempotency_key_with_another_payload_returns_conflict() -> None:
    api, _ = client()
    with api:
        assert _create_draft(api).status_code == 201
        conflict = api.post(
            "/v1/inbox/threads/thread_demo_01/drafts",
            headers={**AUTH, "Idempotency-Key": "draft-key-000001"},
            json={"text": "Outro conteúdo"},
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"


def test_commands_hide_resources_from_another_tenant() -> None:
    api, _ = client(organization_id="org_other")
    with api:
        response = _create_draft(api)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "thread_not_found"


def test_operator_can_draft_and_qualify_but_cannot_approve() -> None:
    api, _ = client(role="operator")
    with api:
        draft = _create_draft(api)
        qualification = api.post(
            "/v1/threads/thread_demo_01/qualify",
            headers={**AUTH, "Idempotency-Key": "qualify-key-00001"},
            json={},
        )
        approval = api.post(
            f"/v1/drafts/{draft.json()['id']}/approve",
            headers={
                **AUTH,
                "Idempotency-Key": "approve-key-00001",
                "If-Match": '"1"',
            },
        )

    assert draft.status_code == 201
    assert qualification.status_code == 200
    assert approval.status_code == 403
    assert approval.json()["error"]["details"] == {
        "required_capability": "outbound.approve"
    }


def test_approval_requires_etag_and_records_actor_hash_without_sending() -> None:
    api, repository = client()
    with api:
        draft = _create_draft(api).json()
        missing = api.post(
            f"/v1/drafts/{draft['id']}/approve",
            headers={**AUTH, "Idempotency-Key": "approve-key-00001"},
        )
        approved = api.post(
            f"/v1/drafts/{draft['id']}/approve",
            headers={
                **AUTH,
                "Idempotency-Key": "approve-key-00002",
                "If-Match": '"1"',
            },
        )
        replay = api.post(
            f"/v1/drafts/{draft['id']}/approve",
            headers={
                **AUTH,
                "Idempotency-Key": "approve-key-00002",
                "If-Match": '"1"',
            },
        )

    assert missing.status_code == 428
    assert approved.status_code == 200
    assert approved.headers["etag"] == '"2"'
    assert approved.json()["status"] == "approved"
    assert replay.json() == approved.json()
    assert repository.approvals == [
        {
            "organization_id": "org_demo",
            "draft_id": draft["id"],
            "actor_user_id": "user_actor_01",
            "actor_membership_id": "membership_actor_01",
            "approved_version": 1,
            "content_hash": draft["content_hash"],
            "approved_at": repository.approvals[0]["approved_at"],
        }
    ]


def test_stale_approval_is_rejected_without_an_audit_record() -> None:
    api, repository = client()
    with api:
        draft = _create_draft(api).json()
        stale = api.post(
            f"/v1/drafts/{draft['id']}/approve",
            headers={
                **AUTH,
                "Idempotency-Key": "approve-key-00001",
                "If-Match": '"2"',
            },
        )

    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "precondition_failed"
    assert repository.approvals == []


def test_qualification_is_idempotent_and_force_refresh_is_explicit() -> None:
    api, _ = client()
    with api:
        first = api.post(
            "/v1/threads/thread_demo_01/qualify",
            headers={**AUTH, "Idempotency-Key": "qualify-key-00001"},
        )
        replay = api.post(
            "/v1/threads/thread_demo_01/qualify",
            headers={**AUTH, "Idempotency-Key": "qualify-key-00001"},
        )
        refreshed = api.post(
            "/v1/threads/thread_demo_01/qualify",
            headers={**AUTH, "Idempotency-Key": "qualify-key-00002"},
            json={"force_refresh": True},
        )

    assert first.status_code == 200
    assert replay.json() == first.json()
    assert refreshed.status_code == 200
    assert refreshed.json()["id"] != first.json()["id"]
    assert refreshed.json()["score"] == 68


def test_viewer_and_malformed_idempotency_key_fail_with_contract_error() -> None:
    viewer, _ = client(role="viewer")
    owner, _ = client()
    with viewer:
        forbidden = _create_draft(viewer)
    with owner:
        malformed = owner.post(
            "/v1/inbox/threads/thread_demo_01/drafts",
            headers={**AUTH, "Idempotency-Key": "short"},
            json={"text": "Olá"},
        )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "insufficient_capability"
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_idempotency_key"
