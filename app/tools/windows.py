from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlsplit

from app.models import PermissionLevel, ToolResult
from app.perception.windows import inspect_active_window
from app.tools.base import Tool


class OpenApplicationTool(Tool):
    name = "open_application"
    description = "Abre um aplicativo permitido pelo nome."
    permission_level = PermissionLevel.SAFE_ACTION
    APPS: ClassVar[dict[str, str]] = {
        "bloco de notas": "notepad.exe", "notepad": "notepad.exe", "calculadora": "calc.exe"
    }

    async def execute(
        self, *, application: str, new_tab: bool = False, **_: Any
    ) -> ToolResult:
        normalized = application.casefold().strip()
        executable = self.APPS.get(normalized)
        arguments: list[str] = []
        if normalized in {"chrome", "google chrome"}:
            executable = self._chrome_executable()
            if new_tab:
                arguments = ["--new-tab", "about:blank"]
        if not executable:
            return ToolResult(False, error="Aplicativo não está na lista permitida.")
        await asyncio.to_thread(subprocess.Popen, [executable, *arguments])
        return ToolResult(True, output=f"{application} aberto.")

    @staticmethod
    def _chrome_executable() -> str | None:
        discovered = shutil.which("chrome.exe") or shutil.which("chrome")
        if discovered:
            return discovered
        candidates = (
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Google/Chrome/Application/chrome.exe",
        )
        return next((str(path) for path in candidates if path.is_file()), None)


class OpenUrlTool(Tool):
    name = "open_url"
    description = "Abre uma URL HTTPS no navegador padrão."
    permission_level = PermissionLevel.SAFE_ACTION

    def validate(self, parameters: dict[str, Any]) -> None:
        url = str(parameters.get("url", ""))
        parsed = urlsplit(url)
        if parsed.scheme.casefold() != "https" or not parsed.hostname or parsed.username:
            raise ValueError("Apenas URLs HTTPS válidas e sem credenciais são permitidas.")

    async def execute(self, *, url: str, **_: Any) -> ToolResult:
        opened = await asyncio.to_thread(webbrowser.open, url)
        return ToolResult(bool(opened), output=f"URL aberta: {url}")


class ScreenshotTool(Tool):
    name = "take_screenshot"
    description = "Captura a tela atual sob demanda."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    async def execute(self, **_: Any) -> ToolResult:
        try:
            import mss
            import mss.tools
        except ImportError:
            return ToolResult(False, error="Dependência mss não instalada.")
        snapshot = inspect_active_window()
        if snapshot.bounds is None or snapshot.minimized:
            return ToolResult(False, error="Não há janela ativa capturável.")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="kiara-active-", suffix=".png", dir=self.output_dir, delete=False
        ) as temporary:
            path = Path(temporary.name)
        with mss.mss() as capture:
            left, top, width, height = snapshot.bounds
            monitor = {"left": left, "top": top, "width": width, "height": height}
            image = capture.grab(monitor)
            mss.tools.to_png(image.rgb, image.size, output=str(path))
        cleanup = threading.Timer(60.0, path.unlink, kwargs={"missing_ok": True})
        cleanup.daemon = True
        cleanup.start()
        return ToolResult(
            True,
            output="Janela ativa capturada temporariamente.",
            metadata={
                "path": str(path),
                "ephemeral": True,
                "expires_seconds": 60,
                "scope": "active_window",
            },
        )
