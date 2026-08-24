from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class ProactivityLevel(StrEnum):
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class ProactivityPolicy:
    level: ProactivityLevel = ProactivityLevel.LOW
    cooldown: timedelta = timedelta(minutes=15)
    daily_limit: int = 8
    _last_notice: datetime | None = None
    _daily: dict[str, int] = field(default_factory=dict)

    def should_notify(self, *, importance: float, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        thresholds = {
            ProactivityLevel.OFF: 2.0,
            ProactivityLevel.LOW: 0.9,
            ProactivityLevel.MEDIUM: 0.65,
            ProactivityLevel.HIGH: 0.4,
        }
        if importance < thresholds[self.level]:
            return False
        key = now.date().isoformat()
        if self._daily.get(key, 0) >= self.daily_limit:
            return False
        if self._last_notice is not None and now - self._last_notice < self.cooldown:
            return False
        self._last_notice = now
        self._daily = {key: self._daily.get(key, 0) + 1}
        return True
