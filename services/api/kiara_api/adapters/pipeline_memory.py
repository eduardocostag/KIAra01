from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any


class InMemoryPipelineRepository:
    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._entries = entries if entries is not None else deepcopy(_DEMO_ENTRIES)
        self._lock = asyncio.Lock()
        self._operations: dict[tuple[str, str, str], tuple[int, dict[str, Any], dict[str, Any]]] = {}

    async def list_entries(self, organization_id: str) -> list[dict[str, Any]]:
        return [self._public(item) for item in self._entries if item["organization_id"] == organization_id]

    async def update_entry(
        self,
        organization_id: str,
        entry_id: str,
        idempotency_key: str,
        expected_version: int,
        changes: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]:
        async with self._lock:
            operation_key = (organization_id, entry_id, idempotency_key)
            previous = self._operations.get(operation_key)
            if previous is not None:
                previous_version, previous_changes, previous_entry = previous
                if previous_version == expected_version and previous_changes == changes:
                    return "updated", deepcopy(previous_entry)
                return "idempotency_conflict", None
            item = next(
                (
                    candidate
                    for candidate in self._entries
                    if candidate["organization_id"] == organization_id
                    and candidate["id"] == entry_id
                ),
                None,
            )
            if item is None:
                return "missing", None
            if item["version"] != expected_version:
                return "conflict", None
            item.update(changes)
            item["version"] += 1
            item["updated_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            public = self._public(item)
            self._operations[operation_key] = (expected_version, deepcopy(changes), public)
            return "updated", deepcopy(public)

    @staticmethod
    def _public(item: dict[str, Any]) -> dict[str, Any]:
        public = deepcopy(item)
        public.pop("organization_id")
        return public


_DEMO_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "pipeline_demo_01",
        "organization_id": "org_demo",
        "consumer": {
            "id": "consumer_demo_01",
            "display_name": "Lead demonstrativo",
            "instagram_username": "lead_demo",
        },
        "stage": "qualified",
        "next_action": "Responder pelo Instagram",
        "version": 1,
        "updated_at": "2026-09-05T12:00:00Z",
    }
]
