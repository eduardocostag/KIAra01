from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

import psutil

from app.models import ScreenContext


@dataclass(frozen=True, slots=True)
class WindowSnapshot:
    context: ScreenContext
    handle: int | None = None
    bounds: tuple[int, int, int, int] | None = None
    minimized: bool = False


def inspect_active_window() -> WindowSnapshot:
    """Return foreground-window metadata without retaining screen content."""
    try:
        import win32gui

        handle = int(win32gui.GetForegroundWindow())
        if not handle:
            return WindowSnapshot(ScreenContext())
        title = win32gui.GetWindowText(handle)
        process_id = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        process = psutil.Process(process_id.value)
        left, top, right, bottom = win32gui.GetWindowRect(handle)
        return WindowSnapshot(
            ScreenContext(
                active_application=process.name(),
                active_process=str(process_id.value),
                window_title=title,
            ),
            handle=handle,
            bounds=(left, top, right - left, bottom - top),
            minimized=bool(win32gui.IsIconic(handle)),
        )
    except (ImportError, OSError, RuntimeError, ValueError, psutil.Error):
        return WindowSnapshot(ScreenContext())


def get_active_window() -> ScreenContext:
    """Compatibility wrapper for phase-one callers."""
    return inspect_active_window().context
