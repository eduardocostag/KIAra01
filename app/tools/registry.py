from __future__ import annotations

import time
import uuid
from typing import Any

from app.models import ToolResult
from app.security.audit import AuditLog
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.security.redaction import redact
from app.tools.base import Tool


class ToolRegistry:
    def __init__(self, permission_gate: PermissionGate, audit: AuditLog, kill_switch: KillSwitch | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.permission_gate = permission_gate
        self.audit = audit
        self.kill_switch = kill_switch

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Ferramenta já registrada: {tool.name}")
        self._tools[tool.name] = tool

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def permission_level(self, name: str):
        return self._tools[name].permission_level

    def planning_catalog(self) -> tuple[dict[str, Any], ...]:
        """Expose only tools with an explicit parameter contract to autonomous planning."""
        return tuple(
            {
                "name": tool.name,
                "description": tool.description,
                "permission": tool.permission_level.value,
                "schema": tool.schema,
            }
            for tool in self._tools.values()
            if hasattr(tool, "schema")
        )

    def permission_for(self, name: str):
        tool = self._tools.get(name)
        return tool.permission_level if tool is not None else None

    async def execute(self, name: str, **parameters: Any) -> ToolResult:
        action_id = str(uuid.uuid4())
        tool = self._tools.get(name)
        if tool is None:
            result = ToolResult(False, error=f"Ferramenta desconhecida: {name}")
            self.audit.record(
                action_id=action_id,
                agent="AgentCore",
                tool=name,
                intent=name,
                parameters_safe=parameters,
                result=False,
                error=result.error,
            )
            return result
        started = time.perf_counter()
        confirmed = False
        result = ToolResult(False, error="A execução não foi iniciada.")
        try:
            if self.kill_switch is not None and self.kill_switch.stopped:
                raise RuntimeError("Kill switch ativo; retome manualmente antes de novas ações.")
            tool.validate(parameters)
            self.permission_gate.authorize(tool.permission_level, f"{name}: {redact(parameters)}")
            confirmed = tool.permission_level.value in {"sensitive_action", "critical_action"}
            result = await tool.execute(**parameters)
            return result
        except Exception as exc:  # noqa: BLE001 - tool boundary converts adapter failures to results
            result = ToolResult(False, error=str(exc))
            return result
        finally:
            self.audit.record(action_id=action_id, agent="AgentCore", tool=name, intent=name, parameters_safe=parameters,
                              result=result.success, error=result.error,
                              duration_ms=round((time.perf_counter() - started) * 1000, 2),
                              permission=tool.permission_level.value, user_confirmation=confirmed)
