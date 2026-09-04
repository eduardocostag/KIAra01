from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import B2CStage, ConsentRecord, PersonLead, SocialIdentity, Touchpoint
from .organic import OrganicOpportunity


def _now() -> str:
    return datetime.now(UTC).isoformat()


def normalize_contact(kind: str, value: str) -> str:
    """Normaliza apenas contatos declarados, sem inferir país ou identidade."""
    kind = kind.strip().casefold()
    value = value.strip()
    if kind == "email":
        normalized = value.casefold()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("E-mail inválido.")
        return normalized
    if kind == "phone":
        normalized = re.sub(r"\D", "", value)
        if len(normalized) < 8:
            raise ValueError("Telefone inválido.")
        return normalized
    raise ValueError("Tipo de contato deve ser 'email' ou 'phone'.")


def _fingerprint(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}:{normalize_contact(kind, value)}".encode()).hexdigest()


class ConsumerStore:
    """Persistência B2C isolada, com identidade explícita e privacidade por padrão."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self._db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                PRAGMA busy_timeout=10000;
                CREATE TABLE IF NOT EXISTS consumer_people (
                  id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '',
                  stage TEXT NOT NULL DEFAULT 'novo_opt_in', email TEXT NOT NULL DEFAULT '',
                  phone TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
                  notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL, retained_until TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_consumer_people_stage
                  ON consumer_people(stage, updated_at DESC);
                CREATE TABLE IF NOT EXISTS consumer_contacts (
                  person_id TEXT NOT NULL, kind TEXT NOT NULL, normalized_value TEXT NOT NULL,
                  declared_at TEXT NOT NULL, PRIMARY KEY(kind, normalized_value),
                  FOREIGN KEY(person_id) REFERENCES consumer_people(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS consumer_social_identities (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, person_id TEXT NOT NULL,
                  platform TEXT NOT NULL, scoped_id TEXT NOT NULL, handle TEXT NOT NULL DEFAULT '',
                  profile_url TEXT NOT NULL DEFAULT '', verified_at TEXT NOT NULL DEFAULT '',
                  UNIQUE(platform, scoped_id),
                  FOREIGN KEY(person_id) REFERENCES consumer_people(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_consumer_social_person
                  ON consumer_social_identities(person_id);
                CREATE TABLE IF NOT EXISTS consumer_consents (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, person_id TEXT NOT NULL,
                  channel TEXT NOT NULL, purpose TEXT NOT NULL, status TEXT NOT NULL,
                  legal_basis TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
                  captured_at TEXT NOT NULL, expires_at TEXT NOT NULL DEFAULT '',
                  revoked_at TEXT NOT NULL DEFAULT '',
                  FOREIGN KEY(person_id) REFERENCES consumer_people(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_consumer_consent_person
                  ON consumer_consents(person_id, channel, purpose, captured_at DESC);
                CREATE TABLE IF NOT EXISTS consumer_touchpoints (
                  id INTEGER PRIMARY KEY AUTOINCREMENT, person_id TEXT NOT NULL,
                  platform TEXT NOT NULL, kind TEXT NOT NULL, direction TEXT NOT NULL,
                  content TEXT NOT NULL DEFAULT '', campaign TEXT NOT NULL DEFAULT '',
                  occurred_at TEXT NOT NULL,
                  FOREIGN KEY(person_id) REFERENCES consumer_people(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_consumer_touchpoint_person
                  ON consumer_touchpoints(person_id, occurred_at DESC);
                CREATE TABLE IF NOT EXISTS consumer_suppressions (
                  contact_hash TEXT PRIMARY KEY, reason TEXT NOT NULL,
                  source TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consumer_organic_opportunities (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  platform TEXT NOT NULL, source_url TEXT NOT NULL UNIQUE,
                  title TEXT NOT NULL DEFAULT '', excerpt TEXT NOT NULL DEFAULT '',
                  intent_score INTEGER NOT NULL DEFAULT 0,
                  intent_signals TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'revisar', discovered_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_consumer_organic_priority
                  ON consumer_organic_opportunities(status, intent_score DESC, discovered_at DESC);
                """
            )
            # Marcador informativo; as tabelas são sempre criadas de forma aditiva.
            current = int(self._db.execute("PRAGMA user_version").fetchone()[0])
            if current < 1:
                self._db.execute("PRAGMA user_version=1")
            self._db.commit()

    def save_organic_opportunity(self, opportunity: OrganicOpportunity) -> int:
        """Persiste somente o sinal público; não concede consentimento nem cria uma pessoa."""
        with self._lock:
            self._db.execute(
                """INSERT INTO consumer_organic_opportunities
                   (platform,source_url,title,excerpt,intent_score,intent_signals,location,status,discovered_at)
                   VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(source_url) DO UPDATE SET
                   title=excluded.title,excerpt=excluded.excerpt,
                   intent_score=excluded.intent_score,intent_signals=excluded.intent_signals,
                   location=excluded.location""",
                (opportunity.platform, opportunity.source_url, opportunity.title,
                 opportunity.excerpt, opportunity.intent_score,
                 "|".join(opportunity.intent_signals), opportunity.location,
                 opportunity.status, _now()),
            )
            row = self._db.execute(
                "SELECT id FROM consumer_organic_opportunities WHERE source_url=?",
                (opportunity.source_url,),
            ).fetchone()
            self._db.commit()
            return int(row[0])

    def list_organic_opportunities(self, *, limit: int = 200) -> list[dict[str, object]]:
        with self._lock:
            rows = self._db.execute(
                """SELECT * FROM consumer_organic_opportunities
                   ORDER BY intent_score DESC, discovered_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["intent_signals"] = tuple(filter(None, str(item["intent_signals"]).split("|")))
            result.append(item)
        return result

    def get_organic_opportunity(self, opportunity_id: int) -> dict[str, object] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM consumer_organic_opportunities WHERE id=?", (opportunity_id,)
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["intent_signals"] = tuple(filter(None, str(item["intent_signals"]).split("|")))
        return item

    def upsert_person(self, *, display_name: str = "", platform: str = "",
                      scoped_id: str = "", email: str = "", phone: str = "",
                      source: str = "", retained_until: str = "") -> str:
        platform, scoped_id = platform.strip().casefold(), scoped_id.strip()
        contacts = [("email", email)] if email.strip() else []
        if phone.strip():
            contacts.append(("phone", phone))
        normalized = [(kind, normalize_contact(kind, value)) for kind, value in contacts]
        with self._lock:
            candidates: set[str] = set()
            if platform and scoped_id:
                row = self._db.execute(
                    "SELECT person_id FROM consumer_social_identities WHERE platform=? AND scoped_id=?",
                    (platform, scoped_id),
                ).fetchone()
                if row:
                    candidates.add(str(row[0]))
            for kind, value in normalized:
                row = self._db.execute(
                    "SELECT person_id FROM consumer_contacts WHERE kind=? AND normalized_value=?",
                    (kind, value),
                ).fetchone()
                if row:
                    candidates.add(str(row[0]))
            if len(candidates) > 1:
                raise ValueError("Identidades conflitantes; revisão humana necessária.")
            identifier = next(iter(candidates), str(uuid.uuid4()))
            now = _now()
            self._db.execute(
                """INSERT INTO consumer_people
                   (id,display_name,email,phone,source,created_at,updated_at,retained_until)
                   VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                   display_name=CASE WHEN excluded.display_name='' THEN consumer_people.display_name ELSE excluded.display_name END,
                   email=CASE WHEN excluded.email='' THEN consumer_people.email ELSE excluded.email END,
                   phone=CASE WHEN excluded.phone='' THEN consumer_people.phone ELSE excluded.phone END,
                   source=CASE WHEN excluded.source='' THEN consumer_people.source ELSE excluded.source END,
                   retained_until=CASE WHEN excluded.retained_until='' THEN consumer_people.retained_until ELSE excluded.retained_until END,
                   updated_at=excluded.updated_at""",
                (identifier, display_name.strip(), email.strip().casefold(), phone.strip(), source.strip(),
                 now, now, retained_until.strip()),
            )
            for kind, value in normalized:
                self._db.execute(
                    "INSERT OR IGNORE INTO consumer_contacts VALUES(?,?,?,?)",
                    (identifier, kind, value, now),
                )
            if platform and scoped_id:
                self._db.execute(
                    """INSERT INTO consumer_social_identities
                       (person_id,platform,scoped_id,verified_at) VALUES(?,?,?,?)
                       ON CONFLICT(platform,scoped_id) DO UPDATE SET verified_at=excluded.verified_at""",
                    (identifier, platform, scoped_id, now),
                )
            self._db.commit()
            return identifier

    def get_person(self, person_id: str) -> PersonLead | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM consumer_people WHERE id=?", (person_id,)).fetchone()
        return self._person(row) if row else None

    def list_people(self, *, stage: B2CStage | None = None, limit: int = 500) -> list[PersonLead]:
        with self._lock:
            if stage is None:
                rows = self._db.execute(
                    "SELECT * FROM consumer_people ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = self._db.execute(
                    "SELECT * FROM consumer_people WHERE stage=? ORDER BY updated_at DESC LIMIT ?",
                    (stage.value, limit),
                ).fetchall()
        return [self._person(row) for row in rows]

    def set_stage(self, person_id: str, stage: B2CStage) -> bool:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE consumer_people SET stage=?,updated_at=? WHERE id=?",
                (stage.value, _now(), person_id),
            )
            self._db.commit()
            return cursor.rowcount > 0

    def add_identity(self, person_id: str, *, platform: str, scoped_id: str,
                     handle: str = "", profile_url: str = "") -> int:
        if not platform.strip() or not scoped_id.strip():
            raise ValueError("Plataforma e ID escopado são obrigatórios.")
        with self._lock:
            cursor = self._db.execute(
                """INSERT INTO consumer_social_identities
                   (person_id,platform,scoped_id,handle,profile_url,verified_at)
                   VALUES(?,?,?,?,?,?)""",
                (person_id, platform.strip().casefold(), scoped_id.strip(), handle.strip(),
                 profile_url.strip(), _now()),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def identities(self, person_id: str) -> list[SocialIdentity]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM consumer_social_identities WHERE person_id=? ORDER BY id", (person_id,)
            ).fetchall()
        return [SocialIdentity(**dict(row)) for row in rows]

    def record_consent(self, person_id: str, *, channel: str, purpose: str,
                       status: str = "granted", legal_basis: str = "consent",
                       source: str = "", expires_at: str = "") -> int:
        if status not in {"granted", "denied", "revoked"}:
            raise ValueError("Status de consentimento inválido.")
        now = _now()
        with self._lock:
            cursor = self._db.execute(
                """INSERT INTO consumer_consents
                   (person_id,channel,purpose,status,legal_basis,source,captured_at,expires_at,revoked_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (person_id, channel.strip().casefold(), purpose.strip(), status,
                 legal_basis.strip(), source.strip(), now, expires_at.strip(),
                 now if status == "revoked" else ""),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def has_active_consent(self, person_id: str, *, channel: str, purpose: str,
                           at: str | None = None) -> bool:
        instant = at or _now()
        with self._lock:
            row = self._db.execute(
                """SELECT status,expires_at FROM consumer_consents
                   WHERE person_id=? AND channel=? AND purpose=? ORDER BY captured_at DESC,id DESC LIMIT 1""",
                (person_id, channel.strip().casefold(), purpose.strip()),
            ).fetchone()
        return bool(row and row["status"] == "granted" and
                    (not row["expires_at"] or row["expires_at"] > instant))

    def consents(self, person_id: str) -> list[ConsentRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM consumer_consents WHERE person_id=? ORDER BY captured_at DESC,id DESC",
                (person_id,),
            ).fetchall()
        return [ConsentRecord(**dict(row)) for row in rows]

    def add_touchpoint(self, person_id: str, *, platform: str, kind: str,
                       direction: str, content: str = "", campaign: str = "",
                       occurred_at: str = "") -> int:
        if direction not in {"inbound", "outbound"}:
            raise ValueError("Direção deve ser inbound ou outbound.")
        with self._lock:
            cursor = self._db.execute(
                """INSERT INTO consumer_touchpoints
                   (person_id,platform,kind,direction,content,campaign,occurred_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (person_id, platform.strip().casefold(), kind.strip(), direction,
                 content.strip(), campaign.strip(), occurred_at or _now()),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    def touchpoints(self, person_id: str) -> list[Touchpoint]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM consumer_touchpoints WHERE person_id=? ORDER BY occurred_at DESC,id DESC",
                (person_id,),
            ).fetchall()
        return [Touchpoint(**dict(row)) for row in rows]

    def suppress_contact(self, kind: str, value: str, *, reason: str = "opt_out",
                         source: str = "consumer") -> None:
        digest = _fingerprint(kind, value)
        with self._lock:
            self._db.execute(
                """INSERT INTO consumer_suppressions VALUES(?,?,?,?)
                   ON CONFLICT(contact_hash) DO UPDATE SET reason=excluded.reason,
                   source=excluded.source,created_at=excluded.created_at""",
                (digest, reason.strip() or "opt_out", source.strip() or "consumer", _now()),
            )
            self._db.commit()

    def is_suppressed(self, kind: str, value: str) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM consumer_suppressions WHERE contact_hash=?", (_fingerprint(kind, value),)
            ).fetchone()
        return row is not None

    def can_contact(self, person_id: str, *, channel: str, purpose: str,
                    contact_kind: str, contact_value: str, at: str | None = None) -> bool:
        return (not self.is_suppressed(contact_kind, contact_value) and
                self.has_active_consent(person_id, channel=channel, purpose=purpose, at=at))

    def purge_expired(self, *, at: str | None = None) -> int:
        """Remove pessoas vencidas e seus dados dependentes; supressões são preservadas."""
        instant = at or _now()
        with self._lock:
            cursor = self._db.execute(
                "DELETE FROM consumer_people WHERE retained_until<>'' AND retained_until<=?", (instant,)
            )
            self._db.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @staticmethod
    def _person(row: sqlite3.Row) -> PersonLead:
        values = dict(row)
        values["stage"] = B2CStage(values["stage"])
        return PersonLead(**values)
