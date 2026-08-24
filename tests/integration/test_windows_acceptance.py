from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.computer_use.backend import PywinautoBackend
from app.computer_use.models import WindowSelector
from app.config import Settings
from app.models import AutonomyMode
from app.perception import ScreenPerception
from app.perception.windows import get_active_window
from app.runtime import BackgroundServices
from app.security.audit import AuditLog
from app.security.kill_switch import KillSwitch
from app.security.permissions import PermissionGate
from app.tools.powershell import PowerShellTool
from app.tools.registry import ToolRegistry
from app.tools.windows import OpenApplicationTool

pytestmark = pytest.mark.windows_integration


def registry(tmp_path: Path, *, confirm=None) -> tuple[ToolRegistry, KillSwitch]:
    switch = KillSwitch()
    tools = ToolRegistry(
        PermissionGate(AutonomyMode.EXECUTE_WITH_CONFIRMATION, confirm=confirm),
        AuditLog(tmp_path / "audit.jsonl"),
        switch,
    )
    return tools, switch


def test_ui_starts_and_stops_offscreen_without_orphan_thread(tmp_path) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from app.ui.desktop import KiaraWindow

    class FakeCore:
        def __init__(self) -> None:
            self.started = False
            self.stopped = False

        async def handle(self, message: str) -> str:
            return message

        def start_background(self) -> None:
            self.started = True

        def stop_background(self) -> None:
            self.stopped = True

    app = QApplication.instance() or QApplication([])
    core = FakeCore()
    window = KiaraWindow(core, KillSwitch())
    try:
        window.show()
        app.processEvents()
        assert window.isVisible()
        assert window.input.objectName() == "messageInput"
        assert core.started is True
    finally:
        window.shutdown()
        window.close()
        app.processEvents()
    assert core.stopped is True
    assert not window._thread.isRunning()


def test_active_window_context_is_observable() -> None:
    context = get_active_window()
    if context.active_process is None:
        pytest.skip("interactive foreground window unavailable in this Windows session")
    assert context.active_process.isdigit()
    assert context.active_application
    assert context.timestamp.tzinfo is not None


async def test_open_notepad_and_close_only_test_owned_process(tmp_path, monkeypatch) -> None:
    tools, _ = registry(tmp_path)
    tools.register(OpenApplicationTool())
    real_popen = subprocess.Popen
    owned: list[subprocess.Popen] = []

    def tracked_popen(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        owned.append(process)
        return process

    monkeypatch.setattr("app.tools.windows.subprocess.Popen", tracked_popen)
    try:
        result = await tools.execute("open_application", application="notepad")
        assert result.success is True
        assert len(owned) == 1
        await asyncio.sleep(0.5)
        assert owned[0].poll() is None
    finally:
        for process in owned:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    assert all(process.poll() is not None for process in owned)


async def test_hostname_requires_confirmation_and_then_executes(tmp_path) -> None:
    decisions = iter((False, True))
    prompts: list[str] = []

    def confirm(summary: str) -> bool:
        prompts.append(summary)
        return next(decisions)

    tools, switch = registry(tmp_path, confirm=confirm)
    tool = PowerShellTool(["hostname"], 10, switch)
    if tool.executable is None:
        pytest.skip("trusted powershell.exe unavailable")
    tools.register(tool)
    denied = await tools.execute("execute_powershell", command="hostname")
    accepted = await tools.execute("execute_powershell", command="hostname")
    assert denied.success is False
    assert "confirmada" in (denied.error or "")
    assert accepted.success is True
    assert accepted.output.strip()
    assert len(prompts) == 2


def test_background_runtime_lifecycle_is_idempotent(tmp_path) -> None:
    tools, _ = registry(tmp_path, confirm=lambda _: True)
    settings = Settings(
        {
            "screen": {"enabled": False},
            "automation": {"database": "automation.db", "tick_seconds": 0.05},
        },
        tmp_path,
    )
    runtime = BackgroundServices(settings, tools)
    runtime.start()
    first_thread = runtime._thread
    runtime.start()
    assert runtime._thread is first_thread
    assert first_thread is not None and first_thread.is_alive()
    runtime.stop()
    runtime.stop()
    assert not first_thread.is_alive()


async def test_active_window_screenshot_is_ephemeral_in_memory(tmp_path) -> None:
    perception = ScreenPerception(event_bus=__import__("app.core.event_bus", fromlist=["EventBus"]).EventBus())
    try:
        capture = await perception.capture_active_window()
    except Exception as exc:  # noqa: BLE001 - real display boundary may be unavailable in CI
        pytest.skip(f"desktop capture unavailable: {type(exc).__name__}")
    if capture is None:
        pytest.skip("no capturable foreground window")
    assert capture.png.startswith(b"\x89PNG\r\n\x1a\n")
    assert capture.width > 0 and capture.height > 0
    assert list(tmp_path.iterdir()) == []
    assert not hasattr(capture, "path")


def test_real_uia_locates_owned_notepad_window() -> None:
    if os.environ.get("KIARA_RUN_UIA_INTEGRATION") != "1":
        pytest.skip("set KIARA_RUN_UIA_INTEGRATION=1 in an interactive desktop session")
    pytest.importorskip("pywinauto")
    process = subprocess.Popen(["notepad.exe"])
    try:
        backend = PywinautoBackend()
        window = None
        for _ in range(20):
            window = backend.find_window(WindowSelector(process=str(process.pid)))
            if window is not None:
                break
            import time

            time.sleep(0.1)
        if window is None:
            pytest.skip("UI Automation cannot observe the owned Notepad window in this session")
        assert backend.exists(window)
        assert backend.window_title(window) is not None
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
