from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True, slots=True)
class MetricSummary:
    count: int
    total_ms: float
    average_ms: float
    maximum_ms: float
    p50_ms: float
    p95_ms: float


class MetricsRegistry:
    def __init__(self) -> None:
        self._values: dict[str, list[float]] = defaultdict(list)
        self._counters: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, name: str, duration_ms: float) -> None:
        with self._lock:
            values = self._values[name]
            values.append(max(0.0, duration_ms))
            del values[:-1_000]

    def summary(self, name: str) -> MetricSummary:
        with self._lock:
            values = tuple(self._values.get(name, ()))
        total = sum(values)
        ordered = sorted(values)
        return MetricSummary(
            len(values),
            total,
            total / len(values) if values else 0.0,
            max(values, default=0.0),
            self._percentile(ordered, 0.50),
            self._percentile(ordered, 0.95),
        )

    def increment(self, name: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("counter increment cannot be negative")
        with self._lock:
            self._counters[name] += amount

    def count(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    @staticmethod
    def _percentile(values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        return values[round((len(values) - 1) * quantile)]

    def timer(self, name: str) -> Timer:
        return Timer(self, name)


class Timer:
    def __init__(self, registry: MetricsRegistry, name: str) -> None:
        self.registry, self.name, self.started = registry, name, 0.0

    def __enter__(self) -> Self:
        self.started = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.registry.observe(self.name, (time.perf_counter() - self.started) * 1_000)
