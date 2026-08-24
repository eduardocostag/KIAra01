from __future__ import annotations

import platform
import sys
from pathlib import Path

APP_NAME = "KiaraAssistant"


def command_for_current_install() -> str:
    executable = Path(sys.executable).resolve()
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    return f'"{executable}" -m app'


def is_enabled() -> bool:
    if platform.system() != "Windows":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _run_key()) as key:
            winreg.QueryValueEx(key, APP_NAME)
    except FileNotFoundError:
        return False
    return True


def enable() -> None:
    """Opt-in only: callers must obtain explicit user consent before invoking."""
    if platform.system() != "Windows":
        raise RuntimeError("Autostart é suportado somente no Windows.")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _run_key()) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command_for_current_install())


def disable() -> None:
    if platform.system() != "Windows":
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _run_key(), 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        return


def _run_key() -> str:
    return r"Software\Microsoft\Windows\CurrentVersion\Run"
