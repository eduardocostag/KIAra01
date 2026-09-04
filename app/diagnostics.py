from __future__ import annotations

import importlib.util
import json
import platform
import shutil

from app.config import load_settings
from app.perception.windows import get_active_window
from app.voice.diagnostics import voice_diagnostics


def run() -> dict[str, object]:
    settings = load_settings()
    return {
        "python": platform.python_version(),
        "windows": platform.system() == "Windows",
        "powershell": shutil.which("powershell.exe") is not None,
        "config": settings.get("assistant.name") == "Kiara",
        "active_window": get_active_window().window_title,
        "dependencies": {
            name: importlib.util.find_spec(name) is not None for name in ("yaml", "mss", "win32gui")
        },
        "audit_directory_writable": (settings.root / "data").parent.exists(),
        "voice": voice_diagnostics(),
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
