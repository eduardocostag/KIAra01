from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..http.errors import ApiError
from ..ports.identity import IdentityPrincipal


class UnconfiguredIdentityVerifier:
    """Fail-closed adapter that keeps health endpoints available during provisioning."""

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        raise ApiError(503, "identity_unavailable", "Provedor de identidade não configurado.")


class DemoIdentityVerifier:
    """Explicit local-only identity adapter; never suitable for deployed environments."""

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        if bearer_token != "kiara-local-demo":
            raise ApiError(401, "invalid_token", "Token de demonstração inválido.")
        return IdentityPrincipal(
            user_id="user_demo",
            organization_id="org_demo",
            membership_id="membership_demo",
            role="owner",
        )


class InMemoryInboxRepository:
    """Tenant-scoped read model containing sanitized demonstration data only."""

    def __init__(self, threads: list[dict[str, Any]] | None = None) -> None:
        self._threads = threads if threads is not None else _DEMO_THREADS

    async def ready(self) -> bool:
        return True

    async def list_threads(self, organization_id: str) -> list[dict[str, Any]]:
        return [
            self._public_thread(item, detail=False)
            for item in self._threads
            if item["organization_id"] == organization_id
        ]

    async def get_thread(self, organization_id: str, thread_id: str) -> dict[str, Any] | None:
        item = next(
            (
                item
                for item in self._threads
                if item["organization_id"] == organization_id and item["id"] == thread_id
            ),
            None,
        )
        return self._public_thread(item, detail=True) if item else None

    @staticmethod
    def _public_thread(item: dict[str, Any], *, detail: bool) -> dict[str, Any]:
        public = deepcopy(item)
        public.pop("organization_id", None)
        if not detail:
            public.pop("messages", None)
            public.pop("drafts", None)
            public.pop("qualification", None)
        return public


_DEMO_THREADS: list[dict[str, Any]] = [
    {
        "id": "thread_demo_01",
        "organization_id": "org_demo",
        "channel": "instagram",
        "consumer": {
            "id": "consumer_demo_01",
            "display_name": "Lead demonstrativo",
            "instagram_username": "lead_demo",
        },
        "status": "waiting_operator",
        "unread_count": 1,
        "updated_at": "2026-09-05T12:00:00Z",
        "version": 1,
        "messages": [
            {
                "id": "message_demo_01",
                "direction": "inbound",
                "text": "Olá! Gostaria de saber mais.",
                "created_at": "2026-09-05T12:00:00Z",
            }
        ],
        "drafts": [],
        "qualification": {
            "id": "qualification_demo_01",
            "thread_id": "thread_demo_01",
            "temperature": "warm",
            "score": 68,
            "recommendation": "Revisar e aprovar um rascunho de resposta",
            "created_at": "2026-09-05T12:00:00Z",
        },
    }
]
