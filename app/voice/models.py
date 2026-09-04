from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: str | None = None
    wake_detected: bool = False
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class VoiceAvailability:
    available: bool
    detail: str
