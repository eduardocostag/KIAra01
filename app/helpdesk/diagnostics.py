from __future__ import annotations

import asyncio
import ctypes
import json
import platform
import shutil
import subprocess
from collections.abc import Callable
from typing import Any, ClassVar

from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool

DiagnosticRunner = Callable[[str, float], str]


_SCRIPTS = {
    "overview": r"""
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$disks = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
  [pscustomobject]@{name=$_.DeviceID; free_gb=[math]::Round($_.FreeSpace/1GB,1); size_gb=[math]::Round($_.Size/1GB,1)}
}
[pscustomobject]@{
  os=$os.Caption; version=$os.Version; uptime_seconds=[int]((Get-Date)-$os.LastBootUpTime).TotalSeconds
  cpu=$cpu.Name; memory_total_gb=[math]::Round($os.TotalVisibleMemorySize/1MB,1)
  memory_free_gb=[math]::Round($os.FreePhysicalMemory/1MB,1); disks=@($disks)
} | ConvertTo-Json -Depth 4 -Compress
""",
    "drivers": r"""
$items = Get-CimInstance Win32_PnPEntity | Where-Object {$_.ConfigManagerErrorCode -ne 0} | Select-Object -First 30 | ForEach-Object {
  [pscustomobject]@{name=$_.Name; status=$_.Status; error_code=[int]$_.ConfigManagerErrorCode}
}
[pscustomobject]@{problem_count=@($items).Count; devices=@($items)} | ConvertTo-Json -Depth 4 -Compress
""",
    "network": r"""
$items = Get-NetAdapter -ErrorAction SilentlyContinue | Select-Object -First 30 | ForEach-Object {
  [pscustomobject]@{name=$_.Name; description=$_.InterfaceDescription; status=[string]$_.Status; link_speed=[string]$_.LinkSpeed}
}
[pscustomobject]@{adapters=@($items)} | ConvertTo-Json -Depth 4 -Compress
""",
    "battery": r"""
$items = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | ForEach-Object {
  [pscustomobject]@{name=$_.Name; charge_percent=$_.EstimatedChargeRemaining; status_code=$_.BatteryStatus}
}
[pscustomobject]@{present=@($items).Count -gt 0; batteries=@($items)} | ConvertTo-Json -Depth 4 -Compress
""",
    "events": r"""
$since = (Get-Date).AddHours(-24)
$system = @(Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2; StartTime=$since} -ErrorAction SilentlyContinue).Count
$application = @(Get-WinEvent -FilterHashtable @{LogName='Application'; Level=1,2; StartTime=$since} -ErrorAction SilentlyContinue).Count
[pscustomobject]@{window_hours=24; system_critical_or_error=$system; application_critical_or_error=$application} | ConvertTo-Json -Compress
""",
}


class SystemDiagnosticsTool(Tool):
    name = "system_diagnostics"
    description = (
        "Coleta um snapshot somente leitura e limitado de saúde, drivers, rede, bateria ou "
        "contagem de erros recentes do Windows."
    )
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"category": {"type": "string", "enum": sorted(_SCRIPTS)}},
        "required": ["category"],
    }

    def __init__(
        self, *, runner: DiagnosticRunner | None = None, timeout_seconds: float = 15.0
    ) -> None:
        self.runner = runner or _run_powershell
        self.timeout_seconds = max(1.0, min(timeout_seconds, 30.0))

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"category"} or parameters.get("category") not in _SCRIPTS:
            raise ValueError(f"category must be one of: {', '.join(sorted(_SCRIPTS))}")

    async def execute(self, *, category: str, **_: Any) -> ToolResult:
        try:
            if category == "overview" and self.runner is _run_powershell:
                snapshot = await asyncio.to_thread(_native_overview)
            else:
                raw = await asyncio.to_thread(
                    self.runner, _SCRIPTS[category], self.timeout_seconds
                )
                snapshot = json.loads(raw)
        except subprocess.TimeoutExpired:
            return ToolResult(False, error="Diagnóstico excedeu o tempo limite.")
        except (json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
            return ToolResult(False, error=f"Diagnóstico indisponível ({type(exc).__name__}).")
        if not isinstance(snapshot, dict):
            return ToolResult(False, error="O Windows retornou um diagnóstico inválido.")
        bounded = _bound(snapshot)
        return ToolResult(
            True,
            output=f"Snapshot de diagnóstico '{category}' coletado em modo somente leitura.",
            metadata={"category": category, "snapshot": bounded, "verified": True},
        )


def compare_snapshots(
    before: dict[str, Any], after: dict[str, Any], *, category: str | None = None
) -> dict[str, Any]:
    """Return deterministic evidence; no improvement is inferred without comparable fields."""
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes.append({"field": key, "before": old, "after": new})
    confirmed, reason = _resolution_criterion(category, before, after)
    return {
        "comparable": bool(before) and bool(after),
        "changed": bool(changes),
        "changes": changes[:30],
        "resolution_confirmed": confirmed,
        "reason": reason,
    }


def _resolution_criterion(
    category: str | None, before: dict[str, Any], after: dict[str, Any]
) -> tuple[bool, str]:
    if category == "drivers":
        old = before.get("problem_count")
        new = after.get("problem_count")
        if isinstance(old, int) and isinstance(new, int) and old > 0 and new == 0:
            return True, "Os dispositivos com código de erro passaram de um valor positivo para zero."
    if category == "network":
        old_down = _adapter_down_count(before)
        new_down = _adapter_down_count(after)
        if old_down > 0 and new_down == 0:
            return (
                True,
                "Os adaptadores antes indisponíveis agora aparecem operacionais; ainda convém testar conectividade.",
            )
    return (
        False,
        "Não há critério técnico específico satisfeito; mudança isolada não prova resolução.",
    )


def _adapter_down_count(snapshot: dict[str, Any]) -> int:
    adapters = snapshot.get("adapters", [])
    if not isinstance(adapters, list):
        return 0
    operational = {"up", "connected", "operational"}
    return sum(
        1
        for item in adapters
        if isinstance(item, dict)
        and str(item.get("status", "")).casefold() not in operational
    )


def _run_powershell(script: str, timeout_seconds: float) -> str:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Restricted",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.stdout[:100_000]


def _native_overview() -> dict[str, Any]:
    """Collect non-identifying health metrics without WMI or administrator rights."""

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    memory = MemoryStatus()
    memory.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("GlobalMemoryStatusEx failed")
    drives = []
    mask = int(ctypes.windll.kernel32.GetLogicalDrives())
    for index in range(26):
        if not mask & (1 << index):
            continue
        root = f"{chr(65 + index)}:\\"
        if int(ctypes.windll.kernel32.GetDriveTypeW(root)) != 3:
            continue
        try:
            usage = shutil.disk_usage(root)
        except OSError:
            continue
        drives.append(
            {
                "name": root[:2],
                "free_gb": round(usage.free / (1024**3), 1),
                "size_gb": round(usage.total / (1024**3), 1),
            }
        )
    return {
        "os": platform.system(),
        "version": platform.version()[:100],
        "uptime_seconds": int(ctypes.windll.kernel32.GetTickCount64() / 1000),
        "cpu_architecture": platform.machine()[:100],
        "memory_total_gb": round(memory.total_physical / (1024**3), 1),
        "memory_free_gb": round(memory.available_physical / (1024**3), 1),
        "memory_load_percent": int(memory.memory_load),
        "disks": drives,
    }


def _bound(value: Any, *, depth: int = 0) -> Any:
    if depth >= 5:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {str(key)[:100]: _bound(item, depth=depth + 1) for key, item in list(value.items())[:50]}
    if isinstance(value, list):
        return [_bound(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return value[:1000]
    return value
