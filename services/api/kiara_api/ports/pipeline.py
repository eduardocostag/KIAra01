from __future__ import annotations

from typing import Any, Protocol


class PipelineRepository(Protocol):
    async def list_entries(self, organization_id: str) -> list[dict[str, Any]]: ...

    async def update_entry(
        self,
        organization_id: str,
        entry_id: str,
        idempotency_key: str,
        expected_version: int,
        changes: dict[str, Any],
    ) -> tuple[str, dict[str, Any] | None]: ...
