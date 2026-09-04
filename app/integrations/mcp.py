from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    name: str
    command: str
    args: tuple[str, ...] = ()
    env_vars: tuple[str, ...] = ()
    allowed_tools: frozenset[str] = frozenset()
    timeout_seconds: float = 20.0

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> McpServerConfig:
        if set(raw) - {
            "name",
            "transport",
            "command",
            "args",
            "env_vars",
            "allowed_tools",
            "timeout_seconds",
        }:
            raise ValueError("Configuração MCP contém campos desconhecidos.")
        if raw.get("transport", "stdio") != "stdio":
            raise ValueError("Somente transporte MCP stdio está habilitado nesta fase.")
        name = str(raw.get("name", ""))
        command = str(raw.get("command", ""))
        args = raw.get("args", [])
        env_vars = raw.get("env_vars", [])
        allowed_tools = raw.get("allowed_tools", [])
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,50}", name):
            raise ValueError("Nome de servidor MCP inválido.")
        if not command or "\x00" in command or len(command) > 500:
            raise ValueError("Comando MCP inválido.")
        if not isinstance(args, list) or any(
            not isinstance(item, str) or "\x00" in item or len(item) > 1_000 for item in args
        ):
            raise ValueError("Argumentos MCP inválidos.")
        if not isinstance(env_vars, list) or any(
            not isinstance(item, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", item)
            for item in env_vars
        ):
            raise ValueError("Nomes de variáveis MCP inválidos.")
        if not isinstance(allowed_tools, list) or any(
            not isinstance(item, str) or not re.fullmatch(r"[\w./:-]{1,100}", item)
            for item in allowed_tools
        ):
            raise ValueError("Allowlist de ferramentas MCP inválida.")
        timeout = float(raw.get("timeout_seconds", 20))
        if not 1 <= timeout <= 120:
            raise ValueError("Timeout MCP deve ficar entre 1 e 120 segundos.")
        return cls(
            name,
            command,
            tuple(args),
            tuple(env_vars),
            frozenset(allowed_tools),
            timeout,
        )

    def resolved_command(self) -> str:
        resolved = shutil.which(self.command)
        if resolved is None:
            raise FileNotFoundError(f"Executável MCP não encontrado: {self.command}")
        return resolved

    def environment(self) -> dict[str, str]:
        return {name: os.environ[name] for name in self.env_vars if name in os.environ}


class McpTransport(Protocol):
    async def list_tools(self, server: McpServerConfig) -> list[dict[str, Any]]: ...

    async def call_tool(
        self, server: McpServerConfig, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]: ...


class OfficialMcpStdioTransport:
    """Thin lazy adapter around the official MCP Python SDK."""

    @staticmethod
    def _imports():
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            raise RuntimeError(
                "Instale o extra 'mcp' da Kiara para conectar servidores MCP."
            ) from exc
        return ClientSession, StdioServerParameters, stdio_client

    async def list_tools(self, server: McpServerConfig) -> list[dict[str, Any]]:
        ClientSession, StdioServerParameters, stdio_client = self._imports()
        parameters = StdioServerParameters(
            command=server.resolved_command(),
            args=list(server.args),
            env=server.environment() or None,
        )
        async with asyncio.timeout(server.timeout_seconds):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                        {
                            "name": item.name,
                            "description": item.description or "",
                            "input_schema": item.input_schema,
                        }
                        for item in result.tools
                    ]

    async def call_tool(
        self, server: McpServerConfig, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        ClientSession, StdioServerParameters, stdio_client = self._imports()
        parameters = StdioServerParameters(
            command=server.resolved_command(),
            args=list(server.args),
            env=server.environment() or None,
        )
        async with asyncio.timeout(server.timeout_seconds):
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments=arguments)
                    content = [
                        item.model_dump(mode="json")
                        if hasattr(item, "model_dump")
                        else {"type": "unknown", "text": str(item)}
                        for item in result.content
                    ]
                    return {
                        "is_error": bool(getattr(result, "is_error", False)),
                        "content": content,
                        "structured_content": getattr(result, "structured_content", None),
                    }


class McpHub:
    def __init__(
        self,
        servers: list[McpServerConfig],
        transport: McpTransport | None = None,
        *,
        max_output_chars: int = 20_000,
    ) -> None:
        if len({server.name.casefold() for server in servers}) != len(servers):
            raise ValueError("Nomes de servidores MCP devem ser únicos.")
        self.servers = {server.name.casefold(): server for server in servers}
        self.transport = transport or OfficialMcpStdioTransport()
        self.max_output_chars = max(1_000, min(100_000, max_output_chars))

    def server_names(self) -> tuple[str, ...]:
        return tuple(sorted(server.name for server in self.servers.values()))

    def server(self, name: str) -> McpServerConfig:
        server = self.servers.get(name.casefold().strip())
        if server is None:
            raise KeyError(f"Servidor MCP não configurado: {name}")
        return server

    async def discover(self, name: str) -> list[dict[str, Any]]:
        try:
            tools = await self.transport.list_tools(self.server(name))
        except Exception as exc:  # noqa: BLE001 - sanitize untrusted SDK/server failures
            raise RuntimeError(
                f"Falha controlada ao consultar servidor MCP ({type(exc).__name__})."
            ) from None
        return [
            {
                "name": str(item.get("name", ""))[:100],
                "description": str(item.get("description", ""))[:500],
                "input_schema": item.get("input_schema", {}),
            }
            for item in tools[:200]
        ]

    async def call(self, server_name: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        server = self.server(server_name)
        if tool not in server.allowed_tools:
            raise PermissionError(f"Ferramenta MCP não permitida no servidor {server.name}: {tool}")
        if not isinstance(arguments, dict) or len(arguments) > 100:
            raise ValueError("Argumentos MCP devem formar um objeto JSON limitado.")
        self._validate_json(arguments)
        try:
            result = await self.transport.call_tool(server, tool, arguments)
        except Exception as exc:  # noqa: BLE001 - sanitize untrusted SDK/server failures
            raise RuntimeError(
                f"Falha controlada ao executar ferramenta MCP ({type(exc).__name__})."
            ) from None
        rendered = str(result)
        if len(rendered) > self.max_output_chars:
            result = {"truncated": True, "preview": rendered[: self.max_output_chars]}
        return result

    @staticmethod
    def _validate_json(value: Any, *, depth: int = 0) -> None:
        if depth > 8:
            raise ValueError("Argumentos MCP excederam a profundidade permitida.")
        if depth == 0 and len(json.dumps(value, ensure_ascii=False, default=str)) > 50_000:
            raise ValueError("Argumentos MCP excederam o limite permitido.")
        if isinstance(value, dict):
            if any(not isinstance(key, str) or len(key) > 200 for key in value):
                raise ValueError("Chave MCP inválida.")
            for item in value.values():
                McpHub._validate_json(item, depth=depth + 1)
        elif isinstance(value, list):
            if len(value) > 1_000:
                raise ValueError("Lista MCP excedeu o limite permitido.")
            for item in value:
                McpHub._validate_json(item, depth=depth + 1)
        elif not isinstance(value, (str, int, float, bool, type(None))):
            raise TypeError("Tipo de argumento MCP não permitido.")
