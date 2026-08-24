from __future__ import annotations

import ctypes
import platform
import threading
from collections.abc import Callable
from ctypes import wintypes


class EmergencyHotkey:
    """Registers Ctrl+Alt+Esc in an independent Windows message-loop thread."""

    HOTKEY_ID = 0x4B49
    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    VK_ESCAPE = 0x1B

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self._thread: threading.Thread | None = None
        self.registered = False
        self._thread_id: int | None = None

    def start(self) -> bool:
        if platform.system() != "Windows" or self._thread is not None:
            return False
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(ready,), daemon=True, name="kiara-hotkey")
        self._thread.start()
        ready.wait(timeout=1)
        return self.registered

    def _run(self, ready: threading.Event) -> None:
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.registered = bool(
            user32.RegisterHotKey(None, self.HOTKEY_ID, self.MOD_ALT | self.MOD_CONTROL, self.VK_ESCAPE)
        )
        ready.set()
        if not self.registered:
            return
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == self.WM_HOTKEY and message.wParam == self.HOTKEY_ID:
                    self.callback()
        finally:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.registered = False

    def close(self) -> None:
        if self._thread_id is None or self._thread is None:
            return
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None
