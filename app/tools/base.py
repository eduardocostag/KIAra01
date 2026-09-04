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

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return parameters

    def confirmation_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return parameters

    @abstractmethod
    async def execute(self, **parameters: Any) -> ToolResult:
        raise NotImplementedError
