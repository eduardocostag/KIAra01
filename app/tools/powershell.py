from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import Any

import psutil

from app.models import PermissionLevel, ToolResult
from app.security.kill_switch import KillSwitch
from app.tools.base import Tool


class PowerShellTool(Tool):
    name = "execute_powershell"
    description = "Executa comandos PowerShell explicitamente permitidos."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(
        self,
        allowlist: list[str],
        timeout: int,
        kill_switch: KillSwitch,
        max_output: int = 16_384,
    ) -> None:
        self.allowlist = {item.casefold() for item in allowlist}
        self.timeout = timeout
        self.kill_switch = kill_switch
        self.max_output = max(1_024, max_output)
        executable = shutil.which("powershell.exe")
        self.executable = str(executable) if executable else None

    def validate(self, parameters: dict[str, Any]) -> None:
        command = str(parameters.get("command", "")).strip()
        if not command or command.casefold() not in self.allowlist:
            raise ValueError("Comando fora da lista permitida.")

    async def execute(self, *, command: str, **_: Any) -> ToolResult:
        if self.kill_switch.stopped:
            return ToolResult(False, error="Kill switch ativo.")
        return await asyncio.to_thread(self._run, command)

    def _run(self, command: str) -> ToolResult:
        if self.executable is None:
            return ToolResult(False, error="PowerShell não encontrado em caminho confiável.")
        process = subprocess.Popen(
            [self.executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.kill_switch.register(process)
        try:
            stdout, stderr = process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            self._kill_tree(process.pid)
            process.communicate()
            return ToolResult(False, error="PowerShell excedeu o tempo limite.")
        finally:
            self.kill_switch.unregister(process)
        stdout = self._bounded(stdout)
        stderr = self._bounded(stderr)
        if process.returncode != 0:
            return ToolResult(False, output=stdout, error=stderr or "Falha no PowerShell.")
        return ToolResult(True, output=stdout)

    def _bounded(self, value: str) -> str:
        value = value.strip()
        if len(value) <= self.max_output:
            return value
        return value[: self.max_output] + "\n[saída truncada]"

    @staticmethod
    def _kill_tree(pid: int) -> None:
        try:
            parent = psutil.Process(pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
        except psutil.Error:
            return
