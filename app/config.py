from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "assistant": {"name": "Kiara", "language": "pt-BR"},
    "voice": {
        "enabled": True,
        "wake_word": "Kiara",
        "require_wake_word": True,
        "vad_enabled": True,
        "continuous_conversation": False,
        "always_listen_for_wake_word": True,
        "conversation_requires_wake_word": True,
        "tts_voice_name": None,
        "tts_rate": -1,
        "tts_volume": 92,
        "tts_language": "pt-BR",
        "tts_max_chunk_chars": 280,
    },
    "screen": {"enabled": True, "monitor_active_window": True, "capture_active_window": True},
    "autonomy": {"mode": "execute_with_confirmation"},
    "security": {"powershell_timeout_seconds": 15, "allowlisted_commands": ["hostname"]},
    "memory": {"enabled": True, "database": "data/memory.db"},
    "planning": {"enabled": False, "database": "data/planning.db"},
    "llm": {
        "provider": "local",
        "model": None,
        "vision_enabled": False,
        "vision_model": None,
        "vision_num_gpu": 0,
    },
}


@dataclass(frozen=True, slots=True)
class Settings:
    raw: dict[str, Any]
    root: Path

    def get(self, dotted_key: str, default: Any = None) -> Any:
        value: Any = self.raw
        for key in dotted_key.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value


def load_settings(path: str | Path | None = None) -> Settings:
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        root = Path(os.environ.get("KIARA_DATA_ROOT", Path(os.environ["LOCALAPPDATA"]) / "Kiara"))
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        root = Path(os.environ.get("KIARA_DATA_ROOT", Path.cwd()))
        bundle_root = Path.cwd()
    configured = os.environ.get("KIARA_CONFIG")
    config_path = Path(path or configured) if path or configured else bundle_root / "config" / "kiara.yaml"
    raw = _merge({}, DEFAULTS)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            raw = _merge(raw, yaml.safe_load(handle) or {})
    return Settings(raw=raw, root=root)


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result
