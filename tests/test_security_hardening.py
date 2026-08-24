from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import AutonomyMode
from app.security.audit import AuditLog
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.tools.powershell import PowerShellTool
from app.tools.registry import ToolRegistry
from app.tools.windows import OpenUrlTool


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "file:///tmp/a", "https://user:secret@example.com"],
)
def test_url_tool_rejects_non_https_or_embedded_credentials(url: str):
    with pytest.raises(ValueError):
        OpenUrlTool().validate({"url": url})


def test_url_tool_accepts_https():
    OpenUrlTool().validate({"url": "https://example.com/path"})


def test_powershell_output_is_bounded():
    tool = PowerShellTool([], 1, KillSwitch(), max_output=1_024)
    output = tool._bounded("x" * 2_000)
    assert len(output) < 1_100
    assert output.endswith("[saída truncada]")


@pytest.mark.asyncio
async def test_audit_has_action_id_and_redacts_parameters(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    registry = ToolRegistry(PermissionGate(AutonomyMode.OBSERVE), AuditLog(path))
    await registry.execute("missing", token="secret-value")
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["action_id"]
    assert entry["parameters_safe"]["token"] == "[REDACTED]"
