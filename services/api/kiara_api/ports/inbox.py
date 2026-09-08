from __future__ import annotations

from typing import Any, Protocol


class InboxRepository(Protocol):
    async def ready(self) -> bool: ...

    async def list_threads(self, organization_id: str) -> list[dict[str, Any]]: ...

    async def get_thread(self, organization_id: str, thread_id: str) -> dict[str, Any] | None: ...
