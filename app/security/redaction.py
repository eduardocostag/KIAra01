from __future__ import annotations

import re
from typing import Any

PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|senha)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,})\b"),
)
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "senha",
    "secret",
    # Tool payloads may contain credentials or private communications.
    "text",
    "body",
    "value",
    "content",
}


def redact_text(value: str) -> str:
    result = value
    for pattern in PATTERNS:
        result = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]" if m.lastindex == 2 else "[REDACTED]", result)
    return result


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).casefold() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
