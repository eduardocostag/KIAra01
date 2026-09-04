from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.leads.suppression import recipient_fingerprint


class ProspectingMode(StrEnum):
    ASSIST = "assist"
    AUTONOMOUS = "autonomous"


@dataclass(frozen=True, slots=True)
class ProspectingPolicy:
    mode: ProspectingMode = ProspectingMode.ASSIST
    allow_auto_send: bool = False
    daily_limit: int = 20
    cooldown: timedelta = timedelta(hours=24)
    timezone: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.daily_limit <= 200:
            raise ValueError("Limite diário deve estar entre 1 e 200.")
        if self.cooldown < timedelta(0):
            raise ValueError("Cooldown não pode ser negativo.")
        if self.timezone:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError(f"Fuso horário indisponível: {self.timezone}") from exc


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str
    reservation_id: str = ""
    remaining_today: int = 0


class ProspectingPolicyEngine:
    """Fail-closed, transactional gate to call immediately before outbound delivery."""

    def __init__(self, path: str | Path, policy: ProspectingPolicy | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = policy or ProspectingPolicy()
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._connection.executescript(
            """CREATE TABLE IF NOT EXISTS prospecting_suppressions (
                 recipient_hash TEXT PRIMARY KEY, reason TEXT NOT NULL,
                 source TEXT NOT NULL, created_at TEXT NOT NULL
               );
               CREATE TABLE IF NOT EXISTS prospecting_reservations (
                 id TEXT PRIMARY KEY, operation_id TEXT NOT NULL,
                 recipient_hash TEXT NOT NULL, local_day TEXT NOT NULL,
                 automatic INTEGER NOT NULL, status TEXT NOT NULL,
                 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
               );
               CREATE INDEX IF NOT EXISTS idx_prospecting_daily
                 ON prospecting_reservations(operation_id, local_day, status);
               CREATE INDEX IF NOT EXISTS idx_prospecting_recipient
                 ON prospecting_reservations(operation_id, recipient_hash, created_at);
            """
        )
        self._connection.commit()

    def reserve(
        self,
        recipient: str,
        *,
        operation_id: str = "default",
        automatic: bool = False,
        now: datetime | None = None,
    ) -> PolicyDecision:
        """Atomically authorize and reserve one contact slot; denial never consumes quota."""
        if automatic and (
            self.policy.mode is ProspectingMode.ASSIST or not self.policy.allow_auto_send
        ):
            return PolicyDecision(False, "Envio automático desativado pela política segura.")
        operation = operation_id.strip()
        if not operation:
            return PolicyDecision(False, "Operação comercial não informada.")
        try:
            fingerprint = recipient_fingerprint(recipient)
            instant = now or datetime.now(UTC)
            if instant.tzinfo is None:
                raise ValueError("Data/hora deve conter fuso horário.")
            instant_utc = instant.astimezone(UTC)
            local_zone = (
                ZoneInfo(self.policy.timezone)
                if self.policy.timezone
                else datetime.now().astimezone().tzinfo
            )
            local_day = instant.astimezone(local_zone).date().isoformat()
            with self._lock:
                return self._reserve_transaction(
                    fingerprint, operation, automatic, instant_utc, local_day
                )
        except (ValueError, sqlite3.Error) as exc:
            return PolicyDecision(False, f"Política bloqueou por segurança: {exc}")

    def _reserve_transaction(
        self,
        fingerprint: str,
        operation: str,
        automatic: bool,
        instant: datetime,
        local_day: str,
    ) -> PolicyDecision:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            suppressed = self._connection.execute(
                "SELECT 1 FROM prospecting_suppressions WHERE recipient_hash=?", (fingerprint,)
            ).fetchone()
            if suppressed is not None:
                self._connection.rollback()
                return PolicyDecision(False, "Destinatário consta na lista de não contato.")
            count = int(self._connection.execute(
                """SELECT COUNT(*) FROM prospecting_reservations
                   WHERE operation_id=? AND local_day=? AND status IN ('reserved','sent')""",
                (operation, local_day),
            ).fetchone()[0])
            if count >= self.policy.daily_limit:
                self._connection.rollback()
                return PolicyDecision(False, "Limite diário de contatos atingido.",
                                      remaining_today=0)
            latest = self._connection.execute(
                """SELECT created_at FROM prospecting_reservations
                   WHERE operation_id=? AND recipient_hash=? AND status IN ('reserved','sent')
                   ORDER BY created_at DESC LIMIT 1""",
                (operation, fingerprint),
            ).fetchone()
            if latest is not None:
                last_contact = datetime.fromisoformat(str(latest["created_at"]))
                if instant - last_contact < self.policy.cooldown:
                    self._connection.rollback()
                    return PolicyDecision(False, "Cooldown do destinatário ainda está ativo.",
                                          remaining_today=self.policy.daily_limit - count)
            identifier = str(uuid.uuid4())
            timestamp = instant.isoformat()
            self._connection.execute(
                """INSERT INTO prospecting_reservations
                   (id,operation_id,recipient_hash,local_day,automatic,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,'reserved',?,?)""",
                (identifier, operation, fingerprint, local_day, int(automatic), timestamp, timestamp),
            )
            self._connection.commit()
            return PolicyDecision(True, "Contato reservado para revisão/envio.", identifier,
                                  self.policy.daily_limit - count - 1)
        except Exception:
            self._connection.rollback()
            raise

    def complete(self, reservation_id: str, *, sent: bool) -> bool:
        status = "sent" if sent else "cancelled"
        with self._lock:
            cursor = self._connection.execute(
                """UPDATE prospecting_reservations SET status=?, updated_at=?
                   WHERE id=? AND status='reserved'""",
                (status, datetime.now(UTC).isoformat(), reservation_id),
            )
            self._connection.commit()
        return cursor.rowcount == 1

    def close(self) -> None:
        with self._lock:
            self._connection.close()
