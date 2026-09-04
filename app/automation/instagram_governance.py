from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.leads.suppression import recipient_fingerprint

OPT_OUT_TERMS = frozenset(
    {"pare", "parar", "sair", "cancele", "cancelar", "nao quero", "não quero"}
)


@dataclass(frozen=True, slots=True)
class GovernedDM:
    id: str
    status: str
    recipient_hash: str
    draft: str
    attempts: int
    next_attempt_at: str | None


class InstagramDMGovernance:
    """Persistent autonomy-level-3 gate for Instagram DM delivery.

    Ingestion and drafting are automatic. Delivery is only claimable after an
    explicit approval, and each inbound platform event is processed once.
    """

    def __init__(
        self, path: str | Path, *, max_attempts: int = 3, approval_ttl: timedelta = timedelta(minutes=15)
    ) -> None:
        if not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts deve estar entre 1 e 10")
        self.max_attempts = max_attempts
        if approval_ttl <= timedelta(0) or approval_ttl > timedelta(hours=24):
            raise ValueError("approval_ttl deve estar entre zero e 24 horas")
        self.approval_ttl = approval_ttl
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS instagram_governance_state (
              singleton INTEGER PRIMARY KEY CHECK(singleton=1),
              enabled INTEGER NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prospecting_suppressions (
              recipient_hash TEXT PRIMARY KEY, reason TEXT NOT NULL,
              source TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS instagram_inbound_events (
              event_id TEXT PRIMARY KEY, recipient_hash TEXT NOT NULL,
              received_at TEXT NOT NULL, outcome TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS instagram_dm_actions (
              id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
              recipient_hash TEXT NOT NULL, draft TEXT NOT NULL,
              status TEXT NOT NULL, approved_by TEXT, approved_at TEXT,
              attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TEXT,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              FOREIGN KEY(event_id) REFERENCES instagram_inbound_events(event_id)
            );
            CREATE TABLE IF NOT EXISTS instagram_audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT,
              event_type TEXT NOT NULL, actor TEXT NOT NULL,
              occurred_at TEXT NOT NULL, detail TEXT NOT NULL
            );
            """
        )
        now = datetime.now(UTC).isoformat()
        self._db.execute(
            "INSERT OR IGNORE INTO instagram_governance_state VALUES(1,0,?,?)",
            (now, "safe_default"),
        )
        self._db.commit()

    def set_enabled(self, enabled: bool, *, actor: str) -> None:
        actor = actor.strip()
        if not actor:
            raise ValueError("ator obrigatório")
        now = datetime.now(UTC).isoformat()
        with self._lock, self._db:
            self._db.execute(
                "UPDATE instagram_governance_state SET enabled=?,updated_at=?,updated_by=? WHERE singleton=1",
                (int(enabled), now, actor),
            )
            self._audit(None, "kill_switch_enabled" if enabled else "kill_switch_disabled", actor)

    def ingest(self, event_id: str, recipient: str, message: str) -> str:
        """Record an inbound event once and immediately honor explicit opt-out."""
        event_id, message = event_id.strip(), message.strip()
        if not event_id or not message:
            raise ValueError("event_id e mensagem são obrigatórios")
        fingerprint = recipient_fingerprint(recipient)
        normalized = " ".join(message.casefold().split())
        opted_out = normalized in OPT_OUT_TERMS
        now = datetime.now(UTC).isoformat()
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT outcome FROM instagram_inbound_events WHERE event_id=?", (event_id,)
            ).fetchone()
            if existing:
                return str(existing["outcome"])
            outcome = "opt_out" if opted_out else "accepted"
            self._db.execute(
                "INSERT INTO instagram_inbound_events VALUES(?,?,?,?)",
                (event_id, fingerprint, now, outcome),
            )
            if opted_out:
                self._db.execute(
                    """INSERT INTO prospecting_suppressions(recipient_hash,reason,source,created_at)
                    VALUES(?,?,?,?) ON CONFLICT(recipient_hash) DO UPDATE SET
                    reason=excluded.reason,source=excluded.source,created_at=excluded.created_at""",
                    (fingerprint, "opt_out", "instagram_dm", now),
                )
            self._audit(None, f"inbound_{outcome}", "instagram")
            return outcome

    def create_draft(self, event_id: str, draft: str, *, actor: str = "kiara") -> str:
        draft, actor = draft.strip(), actor.strip()
        if not draft or not actor:
            raise ValueError("rascunho e ator são obrigatórios")
        now, identifier = datetime.now(UTC).isoformat(), str(uuid.uuid4())
        with self._lock, self._db:
            event = self._db.execute(
                "SELECT recipient_hash,outcome FROM instagram_inbound_events WHERE event_id=?",
                (event_id,),
            ).fetchone()
            if event is None or event["outcome"] != "accepted":
                raise ValueError("evento ausente ou bloqueado")
            existing = self._db.execute(
                "SELECT id FROM instagram_dm_actions WHERE event_id=?", (event_id,)
            ).fetchone()
            if existing:
                return str(existing["id"])
            self._db.execute(
                """INSERT INTO instagram_dm_actions
                (id,event_id,recipient_hash,draft,status,created_at,updated_at)
                VALUES(?,?,?,?,'pending_approval',?,?)""",
                (identifier, event_id, event["recipient_hash"], draft, now, now),
            )
            self._audit(identifier, "draft_created", actor)
            return identifier

    def action_for_event(self, event_id: str) -> GovernedDM | None:
        """Return an existing action so webhook redelivery has no repeated side effects."""
        row = self._db.execute(
            """SELECT id,status,recipient_hash,draft,attempts,next_attempt_at
            FROM instagram_dm_actions WHERE event_id=?""",
            (event_id,),
        ).fetchone()
        return GovernedDM(**dict(row)) if row else None

    def approve(self, action_id: str, *, actor: str) -> bool:
        actor, now = actor.strip(), datetime.now(UTC).isoformat()
        if not actor or actor == "kiara":
            return False
        with self._lock, self._db:
            cursor = self._db.execute(
                """UPDATE instagram_dm_actions SET status='approved',approved_by=?,
                approved_at=?,updated_at=? WHERE id=? AND status='pending_approval'""",
                (actor, now, now, action_id),
            )
            if cursor.rowcount:
                self._audit(action_id, "approved", actor)
            return cursor.rowcount == 1

    def claim_delivery(self, action_id: str, *, now: datetime | None = None) -> GovernedDM | None:
        instant = now or datetime.now(UTC)
        if instant.tzinfo is None:
            raise ValueError("data/hora deve conter fuso")
        timestamp = instant.astimezone(UTC).isoformat()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                enabled = self._db.execute(
                    "SELECT enabled FROM instagram_governance_state WHERE singleton=1"
                ).fetchone()[0]
                if not enabled:
                    self._db.rollback()
                    return None
                row = self._db.execute(
                    "SELECT * FROM instagram_dm_actions WHERE id=?", (action_id,)
                ).fetchone()
                if row is None or row["status"] not in ("approved", "retry_wait"):
                    self._db.rollback()
                    return None
                approved_at = datetime.fromisoformat(str(row["approved_at"]))
                if instant.astimezone(UTC) - approved_at.astimezone(UTC) > self.approval_ttl:
                    self._db.execute(
                        "UPDATE instagram_dm_actions SET status='approval_expired',updated_at=? WHERE id=?",
                        (timestamp, action_id),
                    )
                    self._audit(action_id, "approval_expired", "policy")
                    self._db.commit()
                    return None
                if row["next_attempt_at"] and row["next_attempt_at"] > timestamp:
                    self._db.rollback()
                    return None
                suppressed = self._db.execute(
                    "SELECT 1 FROM prospecting_suppressions WHERE recipient_hash=?",
                    (row["recipient_hash"],),
                ).fetchone()
                if suppressed:
                    self._db.execute(
                        "UPDATE instagram_dm_actions SET status='cancelled_opt_out',updated_at=? WHERE id=?",
                        (timestamp, action_id),
                    )
                    self._audit(action_id, "delivery_cancelled_opt_out", "policy")
                    self._db.commit()
                    return None
                self._db.execute(
                    """UPDATE instagram_dm_actions SET status='sending',attempts=attempts+1,
                    next_attempt_at=NULL,updated_at=? WHERE id=?""",
                    (timestamp, action_id),
                )
                self._audit(action_id, "delivery_claimed", "connector")
                self._db.commit()
                claimed = self.get(action_id)
                return claimed
            except Exception:
                self._db.rollback()
                raise

    def finish_delivery(self, action_id: str, *, success: bool, retryable: bool = False) -> str:
        now = datetime.now(UTC)
        with self._lock, self._db:
            row = self._db.execute(
                "SELECT attempts FROM instagram_dm_actions WHERE id=? AND status='sending'",
                (action_id,),
            ).fetchone()
            if row is None:
                return "unchanged"
            attempts = int(row["attempts"])
            if success:
                status, next_attempt = "sent", None
            elif retryable and attempts < self.max_attempts:
                status = "retry_wait"
                next_attempt = (now + timedelta(seconds=30 * 2 ** (attempts - 1))).isoformat()
            else:
                status, next_attempt = "failed", None
            self._db.execute(
                "UPDATE instagram_dm_actions SET status=?,next_attempt_at=?,updated_at=? WHERE id=?",
                (status, next_attempt, now.isoformat(), action_id),
            )
            self._audit(action_id, f"delivery_{status}", "connector")
            return status

    def get(self, action_id: str) -> GovernedDM | None:
        row = self._db.execute(
            "SELECT id,status,recipient_hash,draft,attempts,next_attempt_at FROM instagram_dm_actions WHERE id=?",
            (action_id,),
        ).fetchone()
        return GovernedDM(**dict(row)) if row else None

    def is_enabled(self) -> bool:
        """Return whether governed delivery is explicitly enabled."""
        with self._lock:
            row = self._db.execute(
                "SELECT enabled FROM instagram_governance_state WHERE singleton=1"
            ).fetchone()
        return bool(row and row["enabled"])

    def list_actions(self, *, status: str | None = None, limit: int = 200) -> tuple[GovernedDM, ...]:
        """List recent governed actions without exposing recipient identifiers."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit deve estar entre 1 e 1000")
        query = (
            "SELECT id,status,recipient_hash,draft,attempts,next_attempt_at "
            "FROM instagram_dm_actions"
        )
        params: tuple[object, ...]
        if status is None:
            query += " ORDER BY updated_at DESC LIMIT ?"
            params = (limit,)
        else:
            query += " WHERE status=? ORDER BY updated_at DESC LIMIT ?"
            params = (status.strip(), limit)
        with self._lock:
            rows = self._db.execute(query, params).fetchall()
        return tuple(GovernedDM(**dict(row)) for row in rows)

    def block(self, action_id: str, *, actor: str) -> bool:
        """Block a draft before delivery and record the named human decision."""
        actor = actor.strip()
        if not actor or actor == "kiara":
            raise ValueError("ator humano obrigatorio")
        now = datetime.now(UTC).isoformat()
        with self._lock, self._db:
            cursor = self._db.execute(
                """UPDATE instagram_dm_actions SET status='blocked_by_operator',updated_at=?
                WHERE id=? AND status IN ('pending_approval','approved','retry_wait')""",
                (now, action_id),
            )
            if cursor.rowcount:
                self._audit(action_id, "blocked_by_operator", actor)
            return cursor.rowcount == 1

    def _audit(self, action_id: str | None, event_type: str, actor: str) -> None:
        self._db.execute(
            "INSERT INTO instagram_audit(action_id,event_type,actor,occurred_at,detail) VALUES(?,?,?,?,?)",
            (action_id, event_type, actor, datetime.now(UTC).isoformat(), "{}"),
        )

    def close(self) -> None:
        self._db.close()
