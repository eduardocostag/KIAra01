from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unicodedata
import webbrowser
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlsplit

from app.models import PermissionLevel, ToolResult
from app.perception.windows import inspect_active_window
from app.tools.base import Tool


class NetworkPingTool(Tool):
    name = "network_ping"
    description = "Abre o CMD e executa ping para um host validado, sem interpretar shell."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "target": {"type": "string", "maxLength": 253},
            "resolve_name": {"type": "boolean"},
        },
        "required": ["target"],
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) - {"target", "resolve_name"}:
            raise ValueError("Parâmetros desconhecidos para ping.")
        target = str(parameters.get("target", "")).strip()
        if not self._valid_target(target):
            raise ValueError("Destino de ping inválido.")
        if "resolve_name" in parameters and not isinstance(parameters["resolve_name"], bool):
            raise ValueError("resolve_name deve ser booleano.")

    async def execute(
        self, *, target: str, resolve_name: bool = False, **_: Any
    ) -> ToolResult:
        cmd = shutil.which("cmd.exe") or shutil.which("cmd")
        ping = shutil.which("ping.exe") or shutil.which("ping")
        if not cmd or not ping:
            return ToolResult(False, error="CMD ou ping não encontrado em caminho confiável.")
        arguments = [cmd, "/k", ping]
        if resolve_name:
            arguments.append("-a")
        arguments.append(target.strip())
        await asyncio.to_thread(subprocess.Popen, arguments)
        return ToolResult(True, output=f"CMD aberto executando ping em {target.strip()}.")

    @staticmethod
    def _valid_target(value: str) -> bool:
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            labels = value.rstrip(".").split(".")
            return bool(
                value
                and len(value) <= 253
                and all(
                    label
                    and len(label) <= 63
                    and re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
                    for label in labels
                )
            )


class OpenApplicationTool(Tool):
    name = "open_application"
    description = "Abre um aplicativo permitido pelo nome."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "application": {"type": "string", "maxLength": 80},
            "new_tab": {"type": "boolean"},
        },
        "required": ["application"],
    }
    APPS: ClassVar[dict[str, str]] = {
        "bloco de notas": "notepad.exe",
        "notepad": "notepad.exe",
        "calculadora": "calc.exe",
        "explorador de arquivos": "explorer.exe",
        "explorer": "explorer.exe",
        "paint": "mspaint.exe",
        "terminal": "wt.exe",
        "cmd": "cmd.exe",
        "prompt de comando": "cmd.exe",
        "powershell": "powershell.exe",
        "windows powershell": "powershell.exe",
        "gerenciador de tarefas": "taskmgr.exe",
        "configurações": "ms-settings:",
        "configuracoes": "ms-settings:",
        "lixeira": "explorer.exe",
        "downloads": "explorer.exe",
        "pasta downloads": "explorer.exe",
        "pasta de downloads": "explorer.exe",
        "teams": "msteams:",
        "microsoft teams": "msteams:",
        "obsidian": "obsidian://open",
        "documentos": "explorer.exe",
        "pasta de documentos": "explorer.exe",
        "imagens": "explorer.exe",
        "fotos": "explorer.exe",
        "músicas": "explorer.exe",
        "musicas": "explorer.exe",
        "vídeos": "explorer.exe",
        "videos": "explorer.exe",
        "área de trabalho": "explorer.exe",
        "area de trabalho": "explorer.exe",
        "este computador": "explorer.exe",
        "meu computador": "explorer.exe",
        "painel de controle": "control.exe",
        "gerenciador de dispositivos": "mmc.exe",
        "device manager": "mmc.exe",
    }
    ARGUMENTS: ClassVar[dict[str, list[str]]] = {
        "lixeira": ["shell:RecycleBinFolder"],
        "downloads": ["shell:Downloads"],
        "pasta downloads": ["shell:Downloads"],
        "pasta de downloads": ["shell:Downloads"],
        "documentos": ["shell:Personal"],
        "pasta de documentos": ["shell:Personal"],
        "imagens": ["shell:My Pictures"],
        "fotos": ["shell:My Pictures"],
        "músicas": ["shell:My Music"],
        "musicas": ["shell:My Music"],
        "vídeos": ["shell:My Video"],
        "videos": ["shell:My Video"],
        "área de trabalho": ["shell:Desktop"],
        "area de trabalho": ["shell:Desktop"],
        "este computador": ["shell:MyComputerFolder"],
        "meu computador": ["shell:MyComputerFolder"],
        "gerenciador de dispositivos": ["devmgmt.msc"],
        "device manager": ["devmgmt.msc"],
    }
    START_MENU_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "teams": ("microsoft teams", "new microsoft teams"),
        "anydesk": ("anydesk", "anydesk client"),
        "obsidian": ("obsidian",),
        "powershell": ("windows powershell", "powershell 7"),
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) - {"application", "new_tab"}:
            raise ValueError("ParÃ¢metros desconhecidos para abertura de aplicativo.")
        application = parameters.get("application")
        if not isinstance(application, str) or not 1 <= len(application.strip()) <= 80:
            raise ValueError("Informe um aplicativo vÃ¡lido.")
        if "new_tab" in parameters and not isinstance(parameters["new_tab"], bool):
            raise ValueError("new_tab deve ser booleano.")

    async def execute(self, *, application: str, new_tab: bool = False, **_: Any) -> ToolResult:
        normalized = application.casefold().strip()
        executable = self.APPS.get(normalized)
        arguments: list[str] = list(self.ARGUMENTS.get(normalized, []))
        if normalized in {"chrome", "google chrome"}:
            executable = self._chrome_executable()
            if new_tab:
                arguments = ["--new-tab", "about:blank"]
        elif normalized in {"edge", "microsoft edge"}:
            executable = self._common_executable(
                "msedge.exe", "Microsoft/Edge/Application/msedge.exe"
            )
        elif normalized in {"firefox", "mozilla firefox"}:
            executable = self._common_executable("firefox.exe", "Mozilla Firefox/firefox.exe")
        elif normalized in {"vscode", "visual studio code", "code"}:
            executable = self._common_executable(
                "Code.exe", "Microsoft VS Code/Code.exe", local_program=True
            )
        elif normalized == "spotify":
            executable = self._common_executable(
                "Spotify.exe", "Spotify/Spotify.exe", local_program=True
            )
        elif normalized == "anydesk":
            executable = self._common_executable(
                "AnyDesk.exe", "AnyDesk/AnyDesk.exe", local_program=True
            )
        elif normalized == "obsidian":
            executable = self._common_executable(
                "Obsidian.exe", "Obsidian/Obsidian.exe", local_program=True
            ) or executable
        if not executable:
            executable = self._path_executable(normalized)
        if not executable:
            executable = self._start_menu_shortcut(normalized)
        if not executable:
            executable = self._personal_folder(normalized)
        if not executable:
            return ToolResult(
                False,
                error=(
                    "Aplicativo não encontrado pelo nome exato. Use o nome exibido no menu "
                    "Iniciar ou peça para abrir o site correspondente."
                ),
            )
        if self._requires_shell_activation(executable):
            await asyncio.to_thread(os.startfile, executable)
        else:
            await asyncio.to_thread(subprocess.Popen, [executable, *arguments])
        return ToolResult(True, output=f"{application} aberto.")

    @staticmethod
    def _requires_shell_activation(target: str) -> bool:
        lowered = target.casefold()
        return (
            lowered.endswith((".lnk", ".url"))
            or Path(target).is_dir()
            or ":" in target
            and not Path(target).is_absolute()
        )

    @staticmethod
    def _path_executable(normalized: str) -> str | None:
        if normalized.startswith(("uninstall", "desinstalar", "remove ")):
            return None
        if not all(character.isalnum() or character in " ._-" for character in normalized):
            return None
        candidates = {normalized, normalized.replace(" ", "")}
        for candidate in candidates:
            discovered = shutil.which(candidate) or shutil.which(f"{candidate}.exe")
            if discovered and Path(discovered).suffix.casefold() in {".exe", ".com"}:
                return discovered
        return None

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

    @staticmethod
    def _common_executable(
        executable: str, relative_path: str, *, local_program: bool = False
    ) -> str | None:
        discovered = shutil.which(executable)
        if discovered:
            return discovered
        roots = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]
        if local_program:
            roots.insert(0, str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"))
            roots.insert(1, os.environ.get("APPDATA", ""))
        return next(
            (
                str(candidate)
                for root in roots
                if root
                if (candidate := Path(root) / relative_path).is_file()
            ),
            None,
        )

    @staticmethod
    def _start_menu_shortcut(normalized: str) -> str | None:
        roots = (
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path.home() / "Desktop",
            Path(os.environ.get("PUBLIC", "")) / "Desktop",
        )
        blocked_prefixes = ("uninstall", "desinstalar", "remove ")
        if normalized.startswith(blocked_prefixes):
            return None
        accepted_names = {normalized, *OpenApplicationTool.START_MENU_ALIASES.get(normalized, ())}
        accepted_canonical = {OpenApplicationTool._canonical_name(name) for name in accepted_names}
        matches: list[Path] = []
        for root in roots:
            if not root.is_dir():
                continue
            for shortcut in root.rglob("*.lnk"):
                stem = shortcut.stem.casefold().strip()
                if stem.startswith(blocked_prefixes):
                    continue
                if stem in accepted_names or OpenApplicationTool._canonical_name(stem) in accepted_canonical:
                    matches.append(shortcut)
        unique = {str(path.resolve()): path for path in matches}
        return str(next(iter(unique.values()))) if len(unique) == 1 else None

    @staticmethod
    def _canonical_name(value: str) -> str:
        folded = unicodedata.normalize("NFKD", value.casefold())
        ascii_name = "".join(
            character for character in folded if not unicodedata.combining(character)
        )
        words = re.sub(r"[^a-z0-9]+", " ", ascii_name).split()
        ignored = {"app", "desktop", "x64", "64", "bit", "atalho"}
        return " ".join(word for word in words if word not in ignored)

    @staticmethod
    def _personal_folder(normalized: str) -> str | None:
        requested = re.sub(r"^(?:a\s+)?pasta(?:\s+de)?\s+", "", normalized).strip()
        if not requested or requested == normalized:
            return None
        roots = (Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads")
        matches = [
            child
            for root in roots
            if root.is_dir()
            for child in root.iterdir()
            if child.is_dir() and child.name.casefold() == requested
        ]
        return str(matches[0]) if len(matches) == 1 else None


class OpenUrlTool(Tool):
    name = "open_url"
    description = "Abre uma URL HTTPS no navegador padrão."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"url": {"type": "string", "format": "uri", "maxLength": 2048}},
        "required": ["url"],
    }

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"url"}:
            raise ValueError("A abertura de URL aceita somente o campo url.")
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
