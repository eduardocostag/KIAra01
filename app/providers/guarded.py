from __future__ import annotations

import json
import threading
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.providers.llm import LLMProvider


class CloudUsageLimitError(RuntimeError):
    pass


class CircuitOpenError(RuntimeError):
    pass


class GuardedRemoteProvider(LLMProvider):
    """Bound remote calls, redact local context and open a circuit after failures."""

    _PRIVATE_CONTEXT_KEYS = frozenset(
        {
            "active_screen",
            "screen_context_summary",
            "live_screen_understanding",
            "relevant_knowledge",
            "relevant_memories",
            "recent_actions",
        }
    )

    def __init__(
        self,
        provider: LLMProvider,
        *,
        name: str,
        ledger_path: str | Path,
        daily_request_limit: int = 500,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if daily_request_limit <= 0 or failure_threshold <= 0 or cooldown_seconds <= 0:
            raise ValueError("Limites do provider remoto devem ser positivos.")
        self.provider = provider
        self.name = name
        self.ledger_path = Path(ledger_path)
        self.daily_request_limit = daily_request_limit
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def capabilities(self) -> frozenset[str]:
        # Pixels are never forwarded by this wrapper. Cloud vision requires a separate,
        # explicit approval flow that the current LLMProvider contract does not provide.
        return frozenset({"generate"})

    async def generate(self, prompt: str) -> str:
        self._before_request()
        try:
            result = await self.provider.generate(self._sanitize(prompt))
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return result

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        self._before_request()
        emitted = False
        try:
            async for chunk in self.provider.stream(self._sanitize(prompt)):
                emitted = True
                yield chunk
        except Exception:
            self._record_failure()
            raise
        if emitted:
            self._record_success()

    def _before_request(self) -> None:
        with self._lock:
            if self._opened_at is not None:
                if self._clock() - self._opened_at < self.cooldown_seconds:
                    raise CircuitOpenError(f"Circuit breaker aberto para {self.name}.")
                self._opened_at = None
                self._failures = 0
            ledger = self._read_ledger()
            today = datetime.now(UTC).date().isoformat()
            entry = ledger.get(self.name, {})
            count = int(entry.get("count", 0)) if entry.get("date") == today else 0
            if count >= self.daily_request_limit:
                raise CloudUsageLimitError(
                    f"Limite diário local de {self.daily_request_limit} chamadas atingido para {self.name}."
                )
            ledger[self.name] = {"date": today, "count": count + 1}
            self._write_ledger(ledger)

    def _record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = self._clock()

    def _record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def _sanitize(self, prompt: str) -> str:
        try:
            payload = json.loads(prompt)
        except (json.JSONDecodeError, TypeError):
            return prompt
        if not isinstance(payload, dict):
            return prompt
        sanitized = self._remove_private_context(payload)
        sanitized["privacy_notice"] = (
            "Contexto local de tela, memória e documentos foi removido antes desta chamada."
        )
        return json.dumps(sanitized, ensure_ascii=False)

    def _remove_private_context(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._remove_private_context(item)
                for key, item in value.items()
                if key not in self._PRIVATE_CONTEXT_KEYS
            }
        if isinstance(value, list):
            return [self._remove_private_context(item) for item in value]
        return value

    def _read_ledger(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_ledger(self, payload: dict[str, dict[str, Any]]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.ledger_path)
