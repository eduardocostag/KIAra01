from __future__ import annotations

import asyncio
import hashlib
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from ..http.errors import ApiError


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class InMemoryConversationCommandRepository:
    """Process-local demo store. It records approvals but has no outbound transport."""

    def __init__(self, threads: set[tuple[str, str]] | None = None) -> None:
        self._threads = threads or {("org_demo", "thread_demo_01")}
        self._drafts: dict[tuple[str, str], dict[str, Any]] = {}
        self._qualifications: dict[tuple[str, str], dict[str, Any]] = {}
        self._approvals: list[dict[str, Any]] = []
        self._idempotency: dict[tuple[str, str, str], tuple[str, dict[str, Any]]] = {}
        self._sequence = 0
        self._lock = asyncio.Lock()

    @property
    def approvals(self) -> list[dict[str, Any]]:
        return deepcopy(self._approvals)

    def _next_id(self, prefix: str) -> str:
        self._sequence += 1
        return f"{prefix}_{self._sequence:010d}"

    def _replay(
        self, organization_id: str, operation: str, key: str, fingerprint: str
    ) -> dict[str, Any] | None:
        existing = self._idempotency.get((organization_id, operation, key))
        if existing is None:
            return None
        previous_fingerprint, response = existing
        if previous_fingerprint != fingerprint:
            raise ApiError(
                409,
                "idempotency_conflict",
                "A Idempotency-Key já foi usada com outra requisição.",
            )
        return deepcopy(response)

    def _remember(
        self,
        organization_id: str,
        operation: str,
        key: str,
        fingerprint: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        self._idempotency[(organization_id, operation, key)] = (
            fingerprint,
            deepcopy(response),
        )
        return deepcopy(response)

    def _require_thread(self, organization_id: str, thread_id: str) -> None:
        if (organization_id, thread_id) not in self._threads:
            raise ApiError(404, "thread_not_found", "Conversa não encontrada.")

    async def create_draft(
        self,
        *,
        organization_id: str,
        thread_id: str,
        text: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> dict[str, Any]:
        async with self._lock:
            replay = self._replay(
                organization_id, "create_draft", idempotency_key, request_fingerprint
            )
            if replay is not None:
                return replay
            self._require_thread(organization_id, thread_id)
            timestamp = _now()
            draft = {
                "id": self._next_id("draft"),
                "thread_id": thread_id,
                "text": text,
                "status": "draft",
                "version": 1,
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            self._drafts[(organization_id, draft["id"])] = deepcopy(draft)
            return self._remember(
                organization_id, "create_draft", idempotency_key, request_fingerprint, draft
            )

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
    ) -> dict[str, Any]:
        async with self._lock:
            replay = self._replay(
                organization_id, "approve_draft", idempotency_key, request_fingerprint
            )
            if replay is not None:
                return replay
            draft = self._drafts.get((organization_id, draft_id))
            if draft is None:
                raise ApiError(404, "draft_not_found", "Rascunho não encontrado.")
            if draft["version"] != expected_version:
                raise ApiError(
                    412,
                    "precondition_failed",
                    "O rascunho foi alterado; recarregue antes de aprovar.",
                    {"current_version": draft["version"]},
                )
            if draft["status"] != "draft":
                raise ApiError(409, "draft_not_approvable", "O rascunho não pode ser aprovado.")
            approved_at = _now()
            draft["status"] = "approved"
            draft["version"] += 1
            draft["updated_at"] = approved_at
            self._approvals.append(
                {
                    "organization_id": organization_id,
                    "draft_id": draft_id,
                    "actor_user_id": actor_user_id,
                    "actor_membership_id": actor_membership_id,
                    "approved_version": expected_version,
                    "content_hash": draft["content_hash"],
                    "approved_at": approved_at,
                }
            )
            return self._remember(
                organization_id, "approve_draft", idempotency_key, request_fingerprint, draft
            )

    async def qualify_thread(
        self,
        *,
        organization_id: str,
        thread_id: str,
        force_refresh: bool,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> dict[str, Any]:
        async with self._lock:
            replay = self._replay(
                organization_id, "qualify_thread", idempotency_key, request_fingerprint
            )
            if replay is not None:
                return replay
            self._require_thread(organization_id, thread_id)
            resource_key = (organization_id, thread_id)
            qualification = self._qualifications.get(resource_key)
            if qualification is None or force_refresh:
                qualification = {
                    "id": self._next_id("qualification"),
                    "thread_id": thread_id,
                    "score": 68,
                    "temperature": "warm",
                    "recommendation": "Revisar e aprovar um rascunho de resposta",
                    "created_at": _now(),
                }
                self._qualifications[resource_key] = qualification
            return self._remember(
                organization_id,
                "qualify_thread",
                idempotency_key,
                request_fingerprint,
                qualification,
            )
