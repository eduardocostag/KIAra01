from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class WindowSelector:
    title: str | None = None
    process: str | None = None
    class_name: str | None = None

    def validate(self) -> None:
        if not any((self.title, self.process, self.class_name)):
            raise ValueError("Window selector requires title, process, or class_name")


@dataclass(frozen=True, slots=True)
class ElementSelector:
    automation_id: str | None = None
    name: str | None = None
    control_type: str | None = None
    class_name: str | None = None

    def validate(self) -> None:
        if not any((self.automation_id, self.name, self.control_type, self.class_name)):
            raise ValueError("Element selector requires a UI Automation property")


class WindowOperation(StrEnum):
    FOCUS = "focus"
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"
    RESTORE = "restore"
    CLOSE = "close"


class PostConditionKind(StrEnum):
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    FOCUSED = "focused"
    VALUE_EQUALS = "value_equals"
    WINDOW_TITLE_CONTAINS = "window_title_contains"


@dataclass(frozen=True, slots=True)
class PostCondition:
    kind: PostConditionKind
    expected: str | None = None
