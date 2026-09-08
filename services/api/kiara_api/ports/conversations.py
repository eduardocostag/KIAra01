from __future__ import annotations

from typing import Any, Protocol


class ConversationCommandRepository(Protocol):
    async def create_draft(
        self,
        *,
        organization_id: str,
        thread_id: str,
        text: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> dict[str, Any]: ...

    async def approve_draft(
        self,
        *,
        organization_id: str,
        draft_id: str,
        expected_version: int,
        actor_user_id: str,
        actor_membership_id: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> dict[str, Any]: ...

    async def qualify_thread(
        self,
        *,
        organization_id: str,
        thread_id: str,
        force_refresh: bool,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> dict[str, Any]: ...
