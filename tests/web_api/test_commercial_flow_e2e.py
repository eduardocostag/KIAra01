from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from services.api.kiara_api.adapters.conversations_demo import (
    InMemoryConversationCommandRepository,
)
from services.api.kiara_api.adapters.demo import InMemoryInboxRepository
from services.api.kiara_api.adapters.pipeline_memory import InMemoryPipelineRepository
from services.api.kiara_api.config import ApiSettings
from services.api.kiara_api.main import create_app
from services.api.kiara_api.ports.identity import IdentityPrincipal

THREAD_ID = "thread_commercial_01"
FOREIGN_THREAD_ID = "thread_foreign_01"
PIPELINE_ID = "pipeline_commercial_01"
FOREIGN_PIPELINE_ID = "pipeline_foreign_01"
ORG_A = "org_commercial_a"
ORG_B = "org_commercial_b"
AUTH_A = {"Authorization": "Bearer tenant-a-token"}
AUTH_B = {"Authorization": "Bearer tenant-b-token"}


class TokenTenantVerifier:
    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        organizations = {
            "tenant-a-token": ORG_A,
            "tenant-b-token": ORG_B,
        }
        organization_id = organizations[bearer_token]
        return IdentityPrincipal(
            user_id=f"user_{organization_id}",
            organization_id=organization_id,
            membership_id=f"membership_{organization_id}",
            role="owner",
        )


@dataclass
class CommercialHarness:
    client: TestClient
    conversations: InMemoryConversationCommandRepository


@pytest.fixture
def commercial_api() -> CommercialHarness:
    threads: list[dict[str, Any]] = [
        {
            "id": THREAD_ID,
            "organization_id": ORG_A,
            "channel": "instagram",
            "consumer": {
                "id": "consumer_commercial_01",
                "display_name": "Lead de teste",
                "instagram_username": "lead_teste",
            },
            "status": "waiting_operator",
            "unread_count": 1,
            "updated_at": "2026-09-05T12:00:00Z",
            "version": 1,
            "messages": [
                {
                    "id": "message_inbound_01",
                    "direction": "inbound",
                    "text": "Quero conhecer o serviço.",
                    "created_at": "2026-09-05T12:00:00Z",
                }
            ],
            "drafts": [],
            "qualification": None,
        },
        {
            "id": FOREIGN_THREAD_ID,
            "organization_id": ORG_B,
            "channel": "instagram",
            "consumer": {
                "id": "consumer_foreign_01",
                "display_name": "Lead do outro tenant",
                "instagram_username": "lead_foreign",
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
    pipeline_entries = [
        {
            "id": PIPELINE_ID,
            "organization_id": ORG_A,
            "consumer": threads[0]["consumer"],
            "stage": "new",
            "next_action": None,
            "version": 1,
            "updated_at": "2026-09-05T12:00:00Z",
        },
        {
            "id": FOREIGN_PIPELINE_ID,
            "organization_id": ORG_B,
            "consumer": threads[1]["consumer"],
            "stage": "new",
            "next_action": None,
            "version": 1,
            "updated_at": "2026-09-05T12:00:00Z",
        },
    ]
    conversations = InMemoryConversationCommandRepository(
        {(ORG_A, THREAD_ID), (ORG_B, FOREIGN_THREAD_ID)}
    )
    app = create_app(
        ApiSettings(environment="test", cors_origins=("https://app.kiara.test",)),
        identity_verifier=TokenTenantVerifier(),
        inbox_repository=InMemoryInboxRepository(threads),
        conversation_repository=conversations,
        pipeline_repository=InMemoryPipelineRepository(pipeline_entries),
    )
    with TestClient(app) as client:
        yield CommercialHarness(client, conversations)


def test_commercial_journey_is_tenant_scoped_idempotent_and_never_sends(
    commercial_api: CommercialHarness,
) -> None:
    api = commercial_api.client

    me = api.get("/v1/me", headers=AUTH_A)
    inbox = api.get("/v1/inbox/threads", headers=AUTH_A)
    detail = api.get(f"/v1/inbox/threads/{THREAD_ID}", headers=AUTH_A)

    assert me.status_code == 200
    assert me.json()["organization"]["id"] == ORG_A
    assert [item["id"] for item in inbox.json()["items"]] == [THREAD_ID]
    assert detail.status_code == 200
    assert detail.headers["etag"] == '"1"'
    assert [message["direction"] for message in detail.json()["messages"]] == ["inbound"]

    draft_headers = {**AUTH_A, "Idempotency-Key": "draft-commercial-0001"}
    created = api.post(
        f"/v1/inbox/threads/{THREAD_ID}/drafts",
        headers=draft_headers,
        json={"text": "Olá! Posso explicar como funciona."},
    )
    replayed_draft = api.post(
        f"/v1/inbox/threads/{THREAD_ID}/drafts",
        headers=draft_headers,
        json={"text": "Olá! Posso explicar como funciona."},
    )
    assert created.status_code == replayed_draft.status_code == 201
    assert created.json() == replayed_draft.json()
    assert created.headers["etag"] == replayed_draft.headers["etag"] == '"1"'

    draft = created.json()
    missing_precondition = api.post(
        f"/v1/drafts/{draft['id']}/approve",
        headers={**AUTH_A, "Idempotency-Key": "approve-invalid-0001"},
    )
    stale_precondition = api.post(
        f"/v1/drafts/{draft['id']}/approve",
        headers={
            **AUTH_A,
            "Idempotency-Key": "approve-invalid-0002",
            "If-Match": '"2"',
        },
    )
    assert missing_precondition.status_code == 428
    assert missing_precondition.json()["error"]["code"] == "precondition_required"
    assert stale_precondition.status_code == 412
    assert stale_precondition.json()["error"]["code"] == "precondition_failed"
    assert commercial_api.conversations.approvals == []

    approve_headers = {
        **AUTH_A,
        "Idempotency-Key": "approve-commercial-0001",
        "If-Match": created.headers["etag"],
    }
    approved = api.post(f"/v1/drafts/{draft['id']}/approve", headers=approve_headers)
    replayed_approval = api.post(
        f"/v1/drafts/{draft['id']}/approve", headers=approve_headers
    )
    assert approved.status_code == replayed_approval.status_code == 200
    assert approved.json() == replayed_approval.json()
    assert approved.headers["etag"] == replayed_approval.headers["etag"] == '"2"'
    assert approved.json()["status"] == "approved"
    assert len(commercial_api.conversations.approvals) == 1

    qualify_headers = {**AUTH_A, "Idempotency-Key": "qualify-commercial-0001"}
    qualified = api.post(
        f"/v1/threads/{THREAD_ID}/qualify",
        headers=qualify_headers,
        json={"force_refresh": False},
    )
    replayed_qualification = api.post(
        f"/v1/threads/{THREAD_ID}/qualify",
        headers=qualify_headers,
        json={"force_refresh": False},
    )
    assert qualified.status_code == replayed_qualification.status_code == 200
    assert qualified.json() == replayed_qualification.json()
    assert qualified.json()["thread_id"] == THREAD_ID

    pipeline = api.get("/v1/pipeline", headers=AUTH_A)
    assert pipeline.status_code == 200
    assert [item["id"] for item in pipeline.json()["items"]] == [PIPELINE_ID]
    entry = pipeline.json()["items"][0]
    pipeline_headers = {
        **AUTH_A,
        "Idempotency-Key": "pipeline-commercial-0001",
        "If-Match": f'"{entry["version"]}"',
        "Content-Type": "application/merge-patch+json",
    }
    updated = api.patch(
        f"/v1/pipeline/{PIPELINE_ID}",
        headers=pipeline_headers,
        json={"stage": "qualified", "next_action": "Continuar atendimento assistido"},
    )
    replayed_update = api.patch(
        f"/v1/pipeline/{PIPELINE_ID}",
        headers=pipeline_headers,
        json={"stage": "qualified", "next_action": "Continuar atendimento assistido"},
    )
    assert updated.status_code == replayed_update.status_code == 200
    assert updated.json() == replayed_update.json()
    assert updated.headers["etag"] == replayed_update.headers["etag"] == '"2"'

    final_detail = api.get(f"/v1/inbox/threads/{THREAD_ID}", headers=AUTH_A)
    assert [message["direction"] for message in final_detail.json()["messages"]] == [
        "inbound"
    ]
    assert not hasattr(api.app.state, "instagram_transport")
    assert not hasattr(api.app.state, "outbound_transport")


def test_cross_tenant_resources_are_opaque_for_reads_and_mutations(
    commercial_api: CommercialHarness,
) -> None:
    api = commercial_api.client
    cases = [
        api.get(f"/v1/inbox/threads/{THREAD_ID}", headers=AUTH_B),
        api.post(
            f"/v1/inbox/threads/{THREAD_ID}/drafts",
            headers={**AUTH_B, "Idempotency-Key": "cross-draft-denied-01"},
            json={"text": "tentativa"},
        ),
        api.post(
            f"/v1/threads/{THREAD_ID}/qualify",
            headers={**AUTH_B, "Idempotency-Key": "cross-qualify-denied-01"},
            json={"force_refresh": False},
        ),
        api.patch(
            f"/v1/pipeline/{PIPELINE_ID}",
            headers={
                **AUTH_B,
                "Idempotency-Key": "cross-pipeline-denied-01",
                "If-Match": '"1"',
                "Content-Type": "application/merge-patch+json",
            },
            json={"stage": "won"},
        ),
    ]

    assert [response.status_code for response in cases] == [404, 404, 404, 404]
    assert all(ORG_A not in response.text for response in cases)
    assert all("Lead de teste" not in response.text for response in cases)

