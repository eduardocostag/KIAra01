from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class InstagramSafetyLimit(Exception):
    retry_after_seconds: int
    message: str

    def __str__(self) -> str:
        return self.message


class InstagramSafetyGuard:
    """Persistent, per-workspace request budgets for authenticated Instagram access."""

    def __init__(
        self,
        data_dir: Path,
        *,
        clock: Callable[[], float] = time.time,
        analysis_cooldown_seconds: int | None = None,
        hourly_limit: int | None = None,
        daily_limit: int | None = None,
    ) -> None:
        self._path = data_dir / "instagram-safety.json"
        self._clock = clock
        self._analysis_cooldown = analysis_cooldown_seconds or self._env_int(
            "KIARA_INSTAGRAM_ANALYSIS_COOLDOWN_SECONDS", 300, 60, 3600
        )
        self._hourly_limit = hourly_limit or self._env_int(
            "KIARA_INSTAGRAM_ANALYSIS_HOURLY_LIMIT", 4, 1, 12
        )
        self._daily_limit = daily_limit or self._env_int(
            "KIARA_INSTAGRAM_ANALYSIS_DAILY_LIMIT", 12, 1, 50
        )
        self._lock = asyncio.Lock()

    @staticmethod
    def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError:
            value = default
        return max(minimum, min(value, maximum))

    @staticmethod
    def _workspace_key(workspace_id: str) -> str:
        salt = os.getenv("KIARA_PROFILE_SALT") or os.getenv("KIARA_WORKER_TOKEN", "")
        return hmac.new(salt.encode(), workspace_id.encode(), hashlib.sha256).hexdigest()

    def _read(self) -> dict[str, dict[str, object]]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(self._path)

    async def reserve_analysis(self, workspace_id: str) -> None:
        """Reserve one analysis attempt before any Instagram request is made."""
        async with self._lock:
            now = self._clock()
            state = self._read()
            key = self._workspace_key(workspace_id)
            record = state.get(key, {})
            attempts = [
                float(value)
                for value in record.get("analysis_attempts", [])
                if isinstance(value, (int, float)) and now - float(value) < 86_400
            ]
            blocked_until = float(record.get("blocked_until", 0) or 0)
            if blocked_until > now:
                retry_after = max(1, int(blocked_until - now))
                raise InstagramSafetyLimit(
                    retry_after,
                    "As consultas do Instagram estão em pausa preventiva para proteger a conta conectada.",
                )
            if attempts and now - attempts[-1] < self._analysis_cooldown:
                retry_after = max(1, int(self._analysis_cooldown - (now - attempts[-1])))
                raise InstagramSafetyLimit(
                    retry_after,
                    "Aguarde o intervalo de segurança antes de iniciar outra análise.",
                )
            hourly = [value for value in attempts if now - value < 3_600]
            if len(hourly) >= self._hourly_limit:
                retry_after = max(1, int(3_600 - (now - hourly[0])))
                raise InstagramSafetyLimit(
                    retry_after,
                    "O limite preventivo de análises por hora foi atingido.",
                )
            if len(attempts) >= self._daily_limit:
                retry_after = max(1, int(86_400 - (now - attempts[0])))
                raise InstagramSafetyLimit(
                    retry_after,
                    "O limite preventivo diário de análises foi atingido.",
                )
            attempts.append(now)
            state[key] = {**record, "analysis_attempts": attempts}
            self._write(state)

    async def pause(self, workspace_id: str, seconds: int) -> None:
        """Persist a longer circuit-breaker after a platform safety response."""
        async with self._lock:
            now = self._clock()
            state = self._read()
            key = self._workspace_key(workspace_id)
            record = state.get(key, {})
            record["blocked_until"] = max(float(record.get("blocked_until", 0) or 0), now + seconds)
            state[key] = record
            self._write(state)
