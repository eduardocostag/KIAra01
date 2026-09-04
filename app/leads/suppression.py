from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def normalize_recipient(recipient: str) -> str:
    """Return a stable identity without guessing a missing country code."""
    value = recipient.strip().casefold()
    if not value:
        raise ValueError("Destinatário vazio.")
    digits = re.sub(r"\D", "", value)
    if digits and len(digits) >= 8:
        return f"phone:{digits}"
    normalized = re.sub(r"\s+", "", value.lstrip("@"))
    if len(normalized) < 2:
        raise ValueError("Destinatário inválido.")
    return f"handle:{normalized}"


def recipient_fingerprint(recipient: str) -> str:
    return hashlib.sha256(normalize_recipient(recipient).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Suppression:
    recipient_hash: str
    reason: str
    source: str
    created_at: str


class SuppressionStore:
    """Local do-not-contact registry; raw recipient values are never persisted."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=10000")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS prospecting_suppressions (
               recipient_hash TEXT PRIMARY KEY, reason TEXT NOT NULL,
               source TEXT NOT NULL, created_at TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    def suppress(self, recipient: str, *, reason: str = "opt_out", source: str = "prospect") -> None:
        fingerprint = recipient_fingerprint(recipient)
        with self._lock:
            self._connection.execute(
                """INSERT INTO prospecting_suppressions(recipient_hash,reason,source,created_at)
                   VALUES(?,?,?,?) ON CONFLICT(recipient_hash) DO UPDATE SET
                   reason=excluded.reason, source=excluded.source, created_at=excluded.created_at""",
                (fingerprint, reason.strip() or "opt_out", source.strip() or "prospect",
                 datetime.now(UTC).isoformat()),
            )
            self._connection.commit()

    def is_suppressed(self, recipient: str) -> bool:
        fingerprint = recipient_fingerprint(recipient)
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM prospecting_suppressions WHERE recipient_hash=?", (fingerprint,)
            ).fetchone()
        return row is not None

    def get(self, recipient: str) -> Suppression | None:
        fingerprint = recipient_fingerprint(recipient)
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM prospecting_suppressions WHERE recipient_hash=?", (fingerprint,)
            ).fetchone()
        return Suppression(**dict(row)) if row is not None else None

    def close(self) -> None:
        with self._lock:
            self._connection.close()
