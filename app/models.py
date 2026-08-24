from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class PermissionLevel(StrEnum):
    READ_ONLY = "read_only"
    SAFE_ACTION = "safe_action"
    SENSITIVE_ACTION = "sensitive_action"
    CRITICAL_ACTION = "critical_action"


class AutonomyMode(StrEnum):
    OBSERVE = "observe"
    ASSIST = "assist"
    EXECUTE_WITH_CONFIRMATION = "execute_with_confirmation"
    AUTONOMOUS = "autonomous"


@dataclass(slots=True)
class ScreenContext:
    active_application: str | None = None
    active_process: str | None = None
    window_title: str | None = None
    visible_text: str | None = None
    screenshot_path: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ToolResult:
    success: bool
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
