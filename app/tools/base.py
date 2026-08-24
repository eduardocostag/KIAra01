from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models import PermissionLevel, ToolResult


class Tool(ABC):
    name: str
    description: str
    permission_level: PermissionLevel

    def validate(self, parameters: dict[str, Any]) -> None:
        return None

    @abstractmethod
    async def execute(self, **parameters: Any) -> ToolResult:
        raise NotImplementedError
