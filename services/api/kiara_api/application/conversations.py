from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from ..http.context import RequestContext
from ..http.errors import ApiError
from ..ports.conversations import ConversationCommandRepository

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_ROLE_CAPABILITIES = {
    "owner": frozenset({"draft.create", "outbound.approve", "thread.qualify"}),
    "admin": frozenset({"draft.create", "outbound.approve", "thread.qualify"}),
    "operator": frozenset({"draft.create", "thread.qualify"}),
    "viewer": frozenset(),
}


def content_fingerprint(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def require_idempotency_key(value: str | None) -> str:
    if value is None or not _IDEMPOTENCY_KEY.fullmatch(value):
        raise ApiError(
            400,
            "invalid_idempotency_key",
            "Idempotency-Key deve ter entre 16 e 128 caracteres seguros.",
        )
    return value


def parse_if_match(value: str | None) -> int:
    if value is None:
        raise ApiError(428, "precondition_required", "If-Match é obrigatório.")
    match = re.fullmatch(r'"([1-9][0-9]*)"', value.strip())
    if match is None:
        raise ApiError(412, "precondition_failed", "If-Match não corresponde a uma versão válida.")
    return int(match.group(1))


@dataclass(slots=True)
class ConversationCommands:
    repository: ConversationCommandRepository

    @staticmethod
    def _authorize(context: RequestContext, capability: str) -> None:
        if capability not in _ROLE_CAPABILITIES.get(context.role, frozenset()):
            raise ApiError(
                403,
                "insufficient_capability",
                "Seu papel não permite executar esta operação.",
                {"required_capability": capability},
            )

    async def create_draft(
        self,
        *,
        context: RequestContext,
        thread_id: str,
        text: str,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        self._authorize(context, "draft.create")
        key = require_idempotency_key(idempotency_key)
        normalized_text = text.strip()
        if not normalized_text or len(normalized_text) > 1000:
            raise ApiError(400, "invalid_draft", "O rascunho deve ter entre 1 e 1000 caracteres.")
        return await self.repository.create_draft(
            organization_id=context.organization_id,
            thread_id=thread_id,
            text=normalized_text,
            idempotency_key=key,
            request_fingerprint=content_fingerprint(
                {"operation": "create_draft", "thread_id": thread_id, "text": normalized_text}
            ),
        )

    async def approve_draft(
        self,
        *,
        context: RequestContext,
        draft_id: str,
        if_match: str | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        self._authorize(context, "outbound.approve")
        key = require_idempotency_key(idempotency_key)
        version = parse_if_match(if_match)
        return await self.repository.approve_draft(
            organization_id=context.organization_id,
            draft_id=draft_id,
            expected_version=version,
            actor_user_id=context.user_id,
            actor_membership_id=context.membership_id,
            idempotency_key=key,
            request_fingerprint=content_fingerprint(
                {"operation": "approve_draft", "draft_id": draft_id, "version": version}
            ),
        )

    async def qualify_thread(
        self,
        *,
        context: RequestContext,
        thread_id: str,
        force_refresh: bool,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        self._authorize(context, "thread.qualify")
        key = require_idempotency_key(idempotency_key)
        return await self.repository.qualify_thread(
            organization_id=context.organization_id,
            thread_id=thread_id,
            force_refresh=force_refresh,
            idempotency_key=key,
            request_fingerprint=content_fingerprint(
                {
                    "operation": "qualify_thread",
                    "thread_id": thread_id,
                    "force_refresh": force_refresh,
                }
            ),
        )
