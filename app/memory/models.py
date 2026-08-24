from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MemoryKind(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    PROJECT = "project"
    FACT = "fact"
    TASK = "task"
    DOCUMENT = "document"


class MemoryProfile(StrEnum):
    PERSONAL = "personal"
    WORK = "work"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: int
    kind: MemoryKind
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    accessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    score: float = 0.0
    profile: MemoryProfile = MemoryProfile.PERSONAL
    version: int = 1
    parent_id: int | None = None
    superseded_by: int | None = None
    provenance: str = "user"
    retrieval_explanation: dict[str, float] = field(default_factory=dict)
