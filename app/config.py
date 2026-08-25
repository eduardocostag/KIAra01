from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_LOCAL_SECRET_NAMES = frozenset(
    {
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "NVIDIA_API_KEY",
        "ANT_LING_API_KEY",
        "TOKENRA_API_KEY",
        "AI_GATEWAY_API_KEY",
        "NEMOTRON_3_ULTRA_550B_API_KEY",
        "LING_3_0_FLASH_API_KEY",
        "LING_3_0_FLASH_VERCEL_API_KEY",
        "OX_ALPHA_API_KEY",
        "VERCEL_OIDC_TOKEN",
    }
)

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
        "remote_base_url": None,
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
    _load_local_secrets(root / ".env.local")
    configured = os.environ.get("KIARA_CONFIG")
    config_path = Path(path or configured) if path or configured else bundle_root / "config" / "kiara.yaml"
    raw = _merge({}, DEFAULTS)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            raw = _merge(raw, yaml.safe_load(handle) or {})
    return Settings(raw=raw, root=root)


def _load_local_secrets(path: Path) -> None:
    """Load only allowlisted API keys without overriding the process environment."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if name not in _LOCAL_SECRET_NAMES or name in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if value:
            os.environ[name] = value


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result
