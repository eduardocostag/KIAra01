from __future__ import annotations

import pytest

from app.integrations.mcp import McpHub, McpServerConfig
from app.models import AutonomyMode
from app.security.audit import AuditLog
from app.security.permissions import PermissionGate
from app.tools.mcp import CallMcpTool, DiscoverMcpToolsTool, ListMcpServersTool
from app.tools.registry import ToolRegistry


class FakeTransport:
    def __init__(self) -> None:
        self.calls = []

    async def list_tools(self, server):
        return [
            {
                "name": "search",
                "description": "Search records",
                "input_schema": {"type": "object"},
            }
        ]

    async def call_tool(self, server, tool, arguments):
        self.calls.append((server.name, tool, arguments))
        return {"is_error": False, "content": [{"type": "text", "text": "ok"}]}


def server(**overrides) -> McpServerConfig:
    values = {
        "name": "local",
        "command": "python",
        "allowed_tools": frozenset({"search"}),
    }
    values.update(overrides)
    return McpServerConfig(**values)


def test_mcp_config_rejects_http_unknown_fields_and_secret_values() -> None:
    with pytest.raises(ValueError, match="Somente transporte"):
        McpServerConfig.from_mapping(
            {"name": "remote", "transport": "http", "command": "python"}
        )
    with pytest.raises(ValueError, match="campos desconhecidos"):
        McpServerConfig.from_mapping(
            {"name": "local", "command": "python", "api_key": "secret"}
        )


async def test_discovery_and_allowlisted_call_use_injected_transport() -> None:
    transport = FakeTransport()
    hub = McpHub([server()], transport)

    tools = await hub.discover("LOCAL")
    result = await hub.call("local", "search", {"query": "cafeteria"})

    assert tools[0]["name"] == "search"
    assert result["is_error"] is False
    assert transport.calls == [("local", "search", {"query": "cafeteria"})]
    with pytest.raises(PermissionError, match="não permitida"):
        await hub.call("local", "delete", {})


async def test_mcp_confirmation_and_audit_never_include_argument_values(tmp_path) -> None:
    prompts = []
    audit = AuditLog(tmp_path / "audit.jsonl")
    hub = McpHub([server()], FakeTransport())
    registry = ToolRegistry(
        PermissionGate(
            AutonomyMode.EXECUTE_WITH_CONFIRMATION,
            confirm=lambda summary: prompts.append(summary) or True,
        ),
        audit,
    )
    registry.register(ListMcpServersTool(hub))
    registry.register(DiscoverMcpToolsTool(hub))
    registry.register(CallMcpTool(hub))

    result = await registry.execute(
        "call_mcp_tool",
        server="local",
        tool="search",
        arguments={"api_key": "super-secret", "query": "private subject"},
    )

    assert result.success is True
    assert "super-secret" not in prompts[0]
    assert "private subject" not in prompts[0]
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "super-secret" not in audit_text
    assert "private subject" not in audit_text
    assert "argument_keys" in audit_text
    assert "call_mcp_tool" not in {
        item["name"] for item in registry.planning_catalog()
    }


async def test_external_mcp_error_is_sanitized() -> None:
    class FailingTransport(FakeTransport):
        async def call_tool(self, server, tool, arguments):
            raise RuntimeError("token=do-not-leak")

    hub = McpHub([server()], FailingTransport())
    with pytest.raises(RuntimeError) as captured:
        await hub.call("local", "search", {})
    assert "do-not-leak" not in str(captured.value)


def test_mcp_rejects_deep_or_oversized_arguments() -> None:
    deep = value = {}
    for _ in range(10):
        value["next"] = {}
        value = value["next"]
    with pytest.raises(ValueError, match="profundidade"):
        McpHub._validate_json(deep)
