from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


def _serialized(method):
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


class LeadStage(StrEnum):
    NEW = "novo"
    QUALIFIED = "qualificado"
    CONTACTED = "contatado"
    REPLIED = "respondeu"
    MEETING = "reuniao"
    DISCOVERY = "discovery"
    PROPOSAL = "proposta"
    NEGOTIATION = "negociacao"
    CONTRACT = "contrato"
    SIGNATURE = "assinatura"
    WON = "convertido"
    LOST = "perdido"


@dataclass(frozen=True, slots=True)
class Lead:
    id: str
    company: str
    niche: str
    location: str
    whatsapp: str
    website: str
    source_url: str
    score: int
    stage: LeadStage
    qualification: str
    notes: str
    next_action: str
    next_action_at: str
    created_at: str
    updated_at: str
    score_explanation: str = ""
    dossier: str = ""
    lost_reason: str = ""
    rating: float = 0.0
    review_count: int = 0
    confidence_score: int = 0
    fit_score: int = 0
    opportunity_score: int = 0
    engagement_score: int = 0
    score_model_version: str = ""
    qualification_data: dict[str, Any] = field(default_factory=dict)
    dossier_data: dict[str, Any] = field(default_factory=dict)
    sales_artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QualificationData:
    """Qualificação verificável. Campos ausentes devem permanecer desconhecidos."""

    status: str = "precisa_pesquisar"
    need: str = "unknown"
    timing: str = "unknown"
    authority: str = "unknown"
    capacity: str = "unknown"
    engagement: str = "unknown"
    disqualifiers: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()
    evidence: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class LeadDossier:
    executive_summary: str = ""
    decision_makers: tuple[dict[str, Any], ...] = ()
    verified_facts: tuple[dict[str, Any], ...] = ()
    hypotheses: tuple[str, ...] = ()
    triggers: tuple[dict[str, Any], ...] = ()
    risks: tuple[str, ...] = ()
    likely_objections: tuple[str, ...] = ()
    discovery_questions: tuple[str, ...] = ()
    meeting_brief: str = ""


@dataclass(frozen=True, slots=True)
class SalesArtifacts:
    opening_message: str = ""
    follow_ups: tuple[str, ...] = ()
    call_script: str = ""
    proposal: dict[str, Any] = field(default_factory=dict)
    roi_scenarios: dict[str, Any] = field(default_factory=dict)
    contract_draft: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommercialProfile:
    business_name: str = "Minha operação"
    service: str = "Serviços profissionais"
    target_niches: str = ""
    target_locations: str = ""
    ideal_customer: str = "Pequenos negócios com necessidade comercial clara"
    value_proposition: str = ""
    average_ticket: float = 0.0
    daily_contact_limit: int = 20
    offers: str = ""
    pricing_rules: str = ""
    differentiators: str = ""
    case_studies: str = ""
    qualification_rules: str = ""
    disqualifiers: str = ""
    discount_policy: str = ""
    proposal_terms: str = ""
    contract_template: str = ""


@dataclass(frozen=True, slots=True)
class Interaction:
    id: int
    lead_id: str
    channel: str
    direction: str
    outcome: str
    notes: str
    occurred_at: str


@dataclass(frozen=True, slots=True)
class FieldObservation:
    id: int
    lead_id: str
    field_name: str
    normalized_value: str
    raw_value: str
    source_url: str
    source_type: str
    status: str
    confidence: float
    observed_at: str


class LeadStore:
    """Pipeline SDR local. Mantém identidade, estágio e próxima ação fora do histórico de chat."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            PRAGMA busy_timeout=5000;
            CREATE TABLE IF NOT EXISTS leads (
              id TEXT PRIMARY KEY, company TEXT NOT NULL, niche TEXT NOT NULL DEFAULT '',
              location TEXT NOT NULL DEFAULT '', whatsapp TEXT NOT NULL DEFAULT '',
              website TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
              score INTEGER NOT NULL DEFAULT 0 CHECK(score BETWEEN 0 AND 100),
              stage TEXT NOT NULL DEFAULT 'novo', qualification TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '', next_action TEXT NOT NULL DEFAULT '',
              next_action_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_identity
              ON leads(company, whatsapp, location);
            CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
            CREATE INDEX IF NOT EXISTS idx_leads_next_action ON leads(next_action_at);
            CREATE TABLE IF NOT EXISTS commercial_profile (
              id INTEGER PRIMARY KEY CHECK(id=1), business_name TEXT NOT NULL,
              service TEXT NOT NULL, target_niches TEXT NOT NULL, target_locations TEXT NOT NULL,
              ideal_customer TEXT NOT NULL, value_proposition TEXT NOT NULL,
              average_ticket REAL NOT NULL DEFAULT 0, daily_contact_limit INTEGER NOT NULL DEFAULT 20
            );
            CREATE TABLE IF NOT EXISTS lead_interactions (
              id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT NOT NULL,
              channel TEXT NOT NULL, direction TEXT NOT NULL, outcome TEXT NOT NULL,
              notes TEXT NOT NULL DEFAULT '', occurred_at TEXT NOT NULL,
              FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_interactions_lead ON lead_interactions(lead_id, occurred_at);
            CREATE TABLE IF NOT EXISTS lead_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT NOT NULL,
              event_type TEXT NOT NULL, from_stage TEXT NOT NULL DEFAULT '',
              to_stage TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL DEFAULT '{}',
              occurred_at TEXT NOT NULL,
              FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_lead_events_lead_time
              ON lead_events(lead_id, occurred_at);
            CREATE TABLE IF NOT EXISTS source_snapshots (
              id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_url TEXT NOT NULL,
              query TEXT NOT NULL DEFAULT '', collector_version TEXT NOT NULL DEFAULT '',
              content_hash TEXT NOT NULL DEFAULT '', collected_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS field_observations (
              id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT NOT NULL,
              field_name TEXT NOT NULL, normalized_value TEXT NOT NULL DEFAULT '',
              raw_value TEXT NOT NULL DEFAULT '', source_snapshot_id TEXT,
              source_url TEXT NOT NULL DEFAULT '', source_type TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'OBSERVED', confidence REAL NOT NULL DEFAULT 0,
              observed_at TEXT NOT NULL,
              FOREIGN KEY(lead_id) REFERENCES leads(id) ON DELETE CASCADE,
              FOREIGN KEY(source_snapshot_id) REFERENCES source_snapshots(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS idx_field_observations_lead_field
              ON field_observations(lead_id, field_name, observed_at DESC);
            """
        )
        self._ensure_column("leads", "score_explanation", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("leads", "dossier", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("leads", "lost_reason", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("leads", "rating", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("leads", "review_count", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("leads", "confidence_score", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("leads", "fit_score", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("leads", "opportunity_score", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("leads", "engagement_score", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("leads", "score_model_version", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("leads", "qualification_data", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("leads", "dossier_data", "TEXT NOT NULL DEFAULT '{}'")
        self._ensure_column("leads", "sales_artifacts", "TEXT NOT NULL DEFAULT '{}'")
        for name, definition in (
            ("offers", "TEXT NOT NULL DEFAULT ''"),
            ("pricing_rules", "TEXT NOT NULL DEFAULT ''"),
            ("differentiators", "TEXT NOT NULL DEFAULT ''"),
            ("case_studies", "TEXT NOT NULL DEFAULT ''"),
            ("qualification_rules", "TEXT NOT NULL DEFAULT ''"),
            ("disqualifiers", "TEXT NOT NULL DEFAULT ''"),
            ("discount_policy", "TEXT NOT NULL DEFAULT ''"),
            ("proposal_terms", "TEXT NOT NULL DEFAULT ''"),
            ("contract_template", "TEXT NOT NULL DEFAULT ''"),
        ):
            self._ensure_column("commercial_profile", name, definition)
        # Mantemos o marcador histórico: a migração é aditiva e guiada por introspecção.
        self._connection.execute("PRAGMA user_version=5")
        self._connection.commit()

    @_serialized
    def upsert(self, *, company: str, niche: str = "", location: str = "", whatsapp: str = "",
               website: str = "", source_url: str = "", score: int = 0,
               qualification: str = "", score_explanation: str = "", dossier: str = "",
               rating: float = 0.0, review_count: int = 0,
               confidence_score: int = 0, fit_score: int = 0,
               opportunity_score: int = 0, engagement_score: int = 0,
               score_model_version: str = "",
               qualification_data: QualificationData | dict[str, Any] | None = None,
               dossier_data: LeadDossier | dict[str, Any] | None = None,
               sales_artifacts: SalesArtifacts | dict[str, Any] | None = None) -> str:
        now = datetime.now(UTC).isoformat()
        identifier = str(uuid.uuid4())
        self._connection.execute(
            """INSERT INTO leads(id,company,niche,location,whatsapp,website,source_url,score,
               stage,qualification,created_at,updated_at,score_explanation,dossier,rating,review_count,
               confidence_score,fit_score,opportunity_score,engagement_score,score_model_version,
               qualification_data,dossier_data,sales_artifacts)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(company,whatsapp,location) DO UPDATE SET
                 niche=excluded.niche, website=excluded.website, source_url=excluded.source_url,
                 score=excluded.score, qualification=excluded.qualification,
                 score_explanation=excluded.score_explanation, dossier=excluded.dossier,
                 rating=excluded.rating, review_count=excluded.review_count,
                 confidence_score=excluded.confidence_score, fit_score=excluded.fit_score,
                 opportunity_score=excluded.opportunity_score,
                 engagement_score=excluded.engagement_score,
                 score_model_version=excluded.score_model_version,
                 qualification_data=CASE WHEN excluded.qualification_data='{}'
                   THEN leads.qualification_data ELSE excluded.qualification_data END,
                 dossier_data=CASE WHEN excluded.dossier_data='{}'
                   THEN leads.dossier_data ELSE excluded.dossier_data END,
                 sales_artifacts=CASE WHEN excluded.sales_artifacts='{}'
                   THEN leads.sales_artifacts ELSE excluded.sales_artifacts END,
                 updated_at=excluded.updated_at""",
            (identifier, company.strip(), niche.strip(), location.strip(), whatsapp.strip(),
             website.strip(), source_url.strip(), max(0, min(100, int(score))),
             LeadStage.NEW.value, qualification.strip(), now, now,
             score_explanation.strip(), dossier.strip(), max(0.0, min(5.0, float(rating))),
             max(0, int(review_count)), max(0, min(100, int(confidence_score))),
             max(0, min(100, int(fit_score))), max(0, min(100, int(opportunity_score))),
             max(0, min(100, int(engagement_score))), score_model_version.strip(),
             self._json_payload(qualification_data), self._json_payload(dossier_data),
             self._json_payload(sales_artifacts)),
        )
        row = self._connection.execute(
            "SELECT id FROM leads WHERE company=? AND whatsapp=? AND location=?",
            (company.strip(), whatsapp.strip(), location.strip()),
        ).fetchone()
        self._connection.commit()
        return str(row["id"])

    @_serialized
    def list(self, *, stage: LeadStage | None = None, limit: int = 500) -> list[Lead]:
        if stage is None:
            rows = self._connection.execute(
                "SELECT * FROM leads ORDER BY score DESC, updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM leads WHERE stage=? ORDER BY score DESC, updated_at DESC LIMIT ?",
                (stage.value, limit),
            ).fetchall()
        return [self._lead(row) for row in rows]

    @_serialized
    def update(self, identifier: str, *, stage: LeadStage | None = None, notes: str | None = None,
               next_action: str | None = None, next_action_at: str | None = None) -> bool:
        now = datetime.now(UTC).isoformat()
        changes: dict[str, Any] = {"updated_at": now}
        current = self._connection.execute(
            "SELECT stage FROM leads WHERE id=?", (identifier,)
        ).fetchone()
        if current is None:
            return False
        if stage is not None:
            changes["stage"] = stage.value
        if notes is not None:
            changes["notes"] = notes.strip()
        if next_action is not None:
            changes["next_action"] = next_action.strip()
        if next_action_at is not None:
            changes["next_action_at"] = next_action_at.strip()
        clause = ", ".join(f"{key}=?" for key in changes)
        cursor = self._connection.execute(
            f"UPDATE leads SET {clause} WHERE id=?", (*changes.values(), identifier)
        )
        if stage is not None and str(current["stage"]) != stage.value:
            self._connection.execute(
                """INSERT INTO lead_events(lead_id,event_type,from_stage,to_stage,payload,occurred_at)
                   VALUES(?,?,?,?,?,?)""",
                (identifier, "stage_changed", str(current["stage"]), stage.value, "{}", now),
            )
        self._connection.commit()
        return cursor.rowcount > 0

    @_serialized
    def metrics(self) -> dict[str, int]:
        counts = {stage.value: 0 for stage in LeadStage}
        for row in self._connection.execute("SELECT stage, COUNT(*) count FROM leads GROUP BY stage"):
            counts[str(row["stage"])] = int(row["count"])
        counts["total"] = sum(counts.values())
        opportunity_stages = (
            LeadStage.QUALIFIED, LeadStage.REPLIED, LeadStage.MEETING, LeadStage.DISCOVERY,
            LeadStage.PROPOSAL, LeadStage.NEGOTIATION, LeadStage.CONTRACT, LeadStage.SIGNATURE,
        )
        counts["oportunidades"] = sum(counts[stage] for stage in opportunity_stages)
        counts["interacoes"] = int(
            self._connection.execute("SELECT COUNT(*) FROM lead_interactions").fetchone()[0]
        )
        return counts

    @_serialized
    def save_profile(self, profile: CommercialProfile) -> None:
        self._connection.execute(
            """INSERT INTO commercial_profile(
                 id,business_name,service,target_niches,target_locations,ideal_customer,
                 value_proposition,average_ticket,daily_contact_limit,offers,pricing_rules,
                 differentiators,case_studies,qualification_rules,disqualifiers,discount_policy,
                 proposal_terms,contract_template
               ) VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET business_name=excluded.business_name,
               service=excluded.service,target_niches=excluded.target_niches,
               target_locations=excluded.target_locations,ideal_customer=excluded.ideal_customer,
               value_proposition=excluded.value_proposition,average_ticket=excluded.average_ticket,
               daily_contact_limit=excluded.daily_contact_limit,offers=excluded.offers,
               pricing_rules=excluded.pricing_rules,differentiators=excluded.differentiators,
               case_studies=excluded.case_studies,qualification_rules=excluded.qualification_rules,
               disqualifiers=excluded.disqualifiers,discount_policy=excluded.discount_policy,
               proposal_terms=excluded.proposal_terms,contract_template=excluded.contract_template""",
            (profile.business_name.strip(), profile.service.strip(), profile.target_niches.strip(),
             profile.target_locations.strip(), profile.ideal_customer.strip(),
             profile.value_proposition.strip(), max(0, profile.average_ticket),
             max(1, min(200, profile.daily_contact_limit)), profile.offers.strip(),
             profile.pricing_rules.strip(), profile.differentiators.strip(),
             profile.case_studies.strip(), profile.qualification_rules.strip(),
             profile.disqualifiers.strip(), profile.discount_policy.strip(),
             profile.proposal_terms.strip(), profile.contract_template.strip()),
        )
        self._connection.commit()

    @_serialized
    def profile(self) -> CommercialProfile:
        row = self._connection.execute("SELECT * FROM commercial_profile WHERE id=1").fetchone()
        if row is None:
            return CommercialProfile()
        values = dict(row)
        values.pop("id", None)
        return CommercialProfile(**values)

    @_serialized
    def add_interaction(self, lead_id: str, *, channel: str, outcome: str,
                        notes: str = "", direction: str = "outbound") -> int:
        cursor = self._connection.execute(
            """INSERT INTO lead_interactions(lead_id,channel,direction,outcome,notes,occurred_at)
               VALUES(?,?,?,?,?,?)""",
            (lead_id, channel.strip(), direction.strip(), outcome.strip(), notes.strip(),
             datetime.now(UTC).isoformat()),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    @_serialized
    def update_sales_intelligence(
        self, lead_id: str, *,
        qualification: QualificationData | dict[str, Any] | None = None,
        dossier: LeadDossier | dict[str, Any] | None = None,
        artifacts: SalesArtifacts | dict[str, Any] | None = None,
    ) -> bool:
        """Atualiza artefatos estruturados sem apagar seções não informadas."""
        current = self._connection.execute(
            "SELECT qualification_data,dossier_data,sales_artifacts FROM leads WHERE id=?",
            (lead_id,),
        ).fetchone()
        if current is None:
            return False
        supplied = {
            "qualification_data": qualification,
            "dossier_data": dossier,
            "sales_artifacts": artifacts,
        }
        changes: dict[str, str] = {}
        for column, value in supplied.items():
            if value is None:
                continue
            previous = self._decode_json(current[column])
            incoming = self._payload_dict(value)
            changes[column] = json.dumps(
                {**previous, **incoming}, ensure_ascii=False, sort_keys=True
            )
        if not changes:
            return True
        changes["updated_at"] = datetime.now(UTC).isoformat()
        clause = ", ".join(f"{key}=?" for key in changes)
        self._connection.execute(
            f"UPDATE leads SET {clause} WHERE id=?", (*changes.values(), lead_id)
        )
        self._connection.commit()
        return True

    @_serialized
    def interactions(self, lead_id: str) -> list[Interaction]:
        rows = self._connection.execute(
            "SELECT * FROM lead_interactions WHERE lead_id=? ORDER BY occurred_at DESC", (lead_id,)
        ).fetchall()
        return [Interaction(**dict(row)) for row in rows]

    @_serialized
    def add_observation(
        self, lead_id: str, *, field_name: str, value: str, source_url: str,
        source_type: str = "web", status: str = "OBSERVED", confidence: float = 0.5,
        raw_value: str | None = None, snapshot_id: str | None = None,
    ) -> int:
        """Preserve field-level provenance without replacing older evidence."""
        allowed = {"VERIFIED", "OBSERVED", "INFERRED", "UNKNOWN", "CONFLICTING", "STALE"}
        normalized_status = status.strip().upper()
        if normalized_status not in allowed:
            raise ValueError(f"Invalid evidence status: {status}")
        if self._connection.execute("SELECT 1 FROM leads WHERE id=?", (lead_id,)).fetchone() is None:
            raise KeyError(lead_id)
        cursor = self._connection.execute(
            """INSERT INTO field_observations(
                 lead_id,field_name,normalized_value,raw_value,source_snapshot_id,
                 source_url,source_type,status,confidence,observed_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (lead_id, field_name.strip(), value.strip().casefold(),
             (value if raw_value is None else raw_value).strip(), snapshot_id,
             source_url.strip(), source_type.strip(), normalized_status,
             max(0.0, min(1.0, float(confidence))), datetime.now(UTC).isoformat()),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    @_serialized
    def observations(self, lead_id: str) -> list[FieldObservation]:
        rows = self._connection.execute(
            """SELECT id,lead_id,field_name,normalized_value,raw_value,source_url,
                      source_type,status,confidence,observed_at
               FROM field_observations WHERE lead_id=? ORDER BY observed_at DESC,id DESC""",
            (lead_id,),
        ).fetchall()
        return [FieldObservation(**dict(row)) for row in rows]

    @_serialized
    def due_actions(self, *, through: str, limit: int = 100) -> list[Lead]:
        rows = self._connection.execute(
            """SELECT * FROM leads WHERE next_action_at != '' AND next_action_at <= ?
                 AND stage NOT IN ('convertido','perdido')
               ORDER BY next_action_at ASC, score DESC LIMIT ?""",
            (through, max(1, min(1000, int(limit)))),
        ).fetchall()
        return [self._lead(row) for row in rows]

    @_serialized
    def funnel_metrics(self) -> dict[str, float]:
        metrics = self.metrics()
        total = metrics["total"]
        after_meeting = (
            "reuniao", "discovery", "proposta", "negociacao", "contrato", "assinatura",
            "convertido",
        )
        contacted = sum(metrics[key] for key in ("contatado", "respondeu", *after_meeting))
        replies = sum(metrics[key] for key in ("respondeu", *after_meeting))
        meetings = sum(metrics[key] for key in after_meeting)
        return {
            **metrics,
            "contact_rate": round(100 * contacted / total, 1) if total else 0.0,
            "reply_rate": round(100 * replies / contacted, 1) if contacted else 0.0,
            "meeting_rate": round(100 * meetings / replies, 1) if replies else 0.0,
        }

    @_serialized
    def record_interaction_and_transition(
        self, lead_id: str, *, channel: str, outcome: str, stage: LeadStage,
        notes: str = "", direction: str = "outbound",
    ) -> int:
        """Record the activity and stage transition as one all-or-nothing unit."""
        now = datetime.now(UTC).isoformat()
        with self._connection:
            current = self._connection.execute(
                "SELECT stage FROM leads WHERE id=?", (lead_id,)
            ).fetchone()
            if current is None:
                raise KeyError(lead_id)
            cursor = self._connection.execute(
                """INSERT INTO lead_interactions(lead_id,channel,direction,outcome,notes,occurred_at)
                   VALUES(?,?,?,?,?,?)""",
                (lead_id, channel.strip(), direction.strip(), outcome.strip(), notes.strip(), now),
            )
            previous = str(current["stage"])
            self._connection.execute(
                "UPDATE leads SET stage=?,updated_at=? WHERE id=?", (stage.value, now, lead_id)
            )
            self._connection.execute(
                """INSERT INTO lead_events(lead_id,event_type,from_stage,to_stage,payload,occurred_at)
                   VALUES(?,?,?,?,?,?)""",
                (lead_id, "interaction_recorded", previous, stage.value,
                 json.dumps({"channel": channel.strip(), "outcome": outcome.strip()}), now),
            )
        return int(cursor.lastrowid)

    @_serialized
    def close(self) -> None:
        self._connection.close()

    def _ensure_column(self, table: str, name: str, definition: str) -> None:
        columns = {str(row[1]) for row in self._connection.execute(f"PRAGMA table_info({table})")}
        if name not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    @staticmethod
    def _payload_dict(value: Any) -> dict[str, Any]:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        if isinstance(value, dict):
            return value
        raise TypeError("sales intelligence payload must be a dataclass or dict")

    @classmethod
    def _json_payload(cls, value: Any | None) -> str:
        if value is None:
            return "{}"
        return json.dumps(cls._payload_dict(value), ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _decode_json(value: Any) -> dict[str, Any]:
        try:
            decoded = json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}

    @staticmethod
    def _lead(row: sqlite3.Row) -> Lead:
        values = dict(row)
        values["stage"] = LeadStage(values["stage"])
        for name in ("qualification_data", "dossier_data", "sales_artifacts"):
            values[name] = LeadStore._decode_json(values.get(name))
        return Lead(**values)
