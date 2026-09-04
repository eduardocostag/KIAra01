from __future__ import annotations

import json
from typing import Any, ClassVar

from app.integrations.mcp import McpHub
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class ListMcpServersTool(Tool):
    name = "list_mcp_servers"
    description = "Lista os servidores MCP configurados localmente."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {"properties": {}, "required": []}

    def __init__(self, hub: McpHub) -> None:
        self.hub = hub

    def validate(self, parameters: dict[str, Any]) -> None:
        if parameters:
            raise ValueError("Esta ferramenta não recebe parâmetros.")

    async def execute(self, **_: Any) -> ToolResult:
        names = self.hub.server_names()
        return ToolResult(
            True,
            output=(
                "Servidores MCP: " + ", ".join(names)
                if names
                else "Nenhum servidor MCP foi configurado."
            ),
            metadata={"server_count": len(names)},
        )


class DiscoverMcpToolsTool(Tool):
    name = "discover_mcp_tools"
    description = "Lista ferramentas declaradas por um servidor MCP configurado."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"server": {"type": "string", "maxLength": 50}},
        "required": ["server"],
    }

    def __init__(self, hub: McpHub) -> None:
        self.hub = hub

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"server"} or not isinstance(parameters["server"], str):
            raise ValueError("Informe somente o servidor MCP.")
        self.hub.server(parameters["server"])

    async def execute(self, *, server: str, **_: Any) -> ToolResult:
        tools = await self.hub.discover(server)
        return ToolResult(
            True,
            output=json.dumps(tools, ensure_ascii=False),
            metadata={"server": server, "tool_count": len(tools)},
        )


class CallMcpTool(Tool):
    name = "call_mcp_tool"
    description = "Executa ferramenta allowlisted de um servidor MCP após confirmação."
    permission_level = PermissionLevel.CRITICAL_ACTION
    plannable = False
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "server": {"type": "string", "maxLength": 50},
            "tool": {"type": "string", "maxLength": 100},
            "arguments": {"type": "object"},
        },
        "required": ["server", "tool", "arguments"],
    }

    def __init__(self, hub: McpHub) -> None:
        self.hub = hub

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"server", "tool", "arguments"}:
            raise ValueError("Informe server, tool e arguments.")
        server = self.hub.server(str(parameters["server"]))
        tool = parameters["tool"]
        if not isinstance(tool, str) or tool not in server.allowed_tools:
            raise PermissionError("Ferramenta MCP ausente da allowlist.")
        if not isinstance(parameters["arguments"], dict):
            raise TypeError("arguments deve ser um objeto JSON.")

    @staticmethod
    def _safe_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
        arguments = parameters.get("arguments", {})
        return {
            "server": parameters.get("server"),
            "tool": parameters.get("tool"),
            "argument_keys": sorted(arguments) if isinstance(arguments, dict) else [],
            "argument_types": {str(key): type(value).__name__ for key, value in arguments.items()}
            if isinstance(arguments, dict)
            else {},
        }

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return self._safe_parameters(parameters)

    def confirmation_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return self._safe_parameters(parameters)

    async def execute(self, *, server: str, tool: str, arguments: dict, **_: Any) -> ToolResult:
        result = await self.hub.call(server, tool, arguments)
        failed = bool(result.get("is_error"))
        return ToolResult(
            not failed,
            output=json.dumps(result, ensure_ascii=False, default=str) if not failed else "",
            error="O servidor MCP informou falha." if failed else None,
            metadata={"server": server, "remote_tool": tool},
        )
