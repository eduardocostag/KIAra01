from pathlib import Path

import pytest

from app.models import AutonomyMode, PermissionLevel, ToolResult
from app.security.audit import AuditLog
from app.security.permissions import PermissionGate
from app.tools.base import Tool
from app.tools.registry import ToolRegistry


class Echo(Tool):
    name = "echo"
    description = "echo"
    permission_level = PermissionLevel.READ_ONLY

    async def execute(self, **parameters):
        return ToolResult(True, output=parameters["value"])


class SensitiveEcho(Echo):
    name = "sensitive_echo"
    permission_level = PermissionLevel.SENSITIVE_ACTION


@pytest.mark.asyncio
async def test_registry_executes_and_audits(tmp_path: Path):
    audit_path = tmp_path / "audit.jsonl"
    registry = ToolRegistry(PermissionGate(AutonomyMode.OBSERVE), AuditLog(audit_path))
    registry.register(Echo())
    result = await registry.execute("echo", value="ok")
    assert result.output == "ok"
    assert audit_path.exists()


@pytest.mark.asyncio
async def test_registry_redacts_sensitive_confirmation_and_audit(tmp_path: Path):
    summaries = []
    audit_path = tmp_path / "audit.jsonl"
    gate = PermissionGate(
        AutonomyMode.EXECUTE_WITH_CONFIRMATION,
        confirm=lambda summary: summaries.append(summary) or True,
    )
    registry = ToolRegistry(gate, AuditLog(audit_path))
    registry.register(SensitiveEcho())

    await registry.execute("sensitive_echo", value="typed-password")

    assert "typed-password" not in summaries[0]
    assert "typed-password" not in audit_path.read_text(encoding="utf-8")
