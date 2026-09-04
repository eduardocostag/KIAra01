from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, ClassVar


class ConsumerStatus(StrEnum):
    SQL = "sql"
    NURTURE = "nurture"
    RESEARCH = "research"
    BLOCKED = "blocked"
    DISQUALIFIED = "disqualified"


class ClaimKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ConsumerClaim:
    field: str
    value: str
    kind: ClaimKind
    rationale: str = ""
    source_url: str = ""
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ConsentGate:
    granted: bool
    channel: str = ""
    purpose: str = ""
    source: str = ""
    recorded_at: str = ""
    reason: str = ""

    @property
    def can_contact(self) -> bool:
        return bool(self.granted and self.channel and self.purpose and self.source)


@dataclass(frozen=True, slots=True)
class QualificationDimension:
    name: str
    score: int | None
    known: bool
    rationale: str


@dataclass(frozen=True, slots=True)
class ConsumerQualification:
    status: ConsumerStatus
    readiness: int
    data_confidence: int
    dimensions: tuple[QualificationDimension, ...]
    reasons: tuple[str, ...]
    model_version: str = "consumer-conservative-v1"


@dataclass(frozen=True, slots=True)
class HandoffBrief:
    ready: bool
    objective: str
    verified_context: tuple[str, ...]
    questions_to_confirm: tuple[str, ...]
    recommended_offer: str
    owner_action: str


@dataclass(frozen=True, slots=True)
class CustomerRoom:
    person_id: str
    display_name: str
    source_platform: str
    qualification: ConsumerQualification
    consent: ConsentGate
    facts: tuple[ConsumerClaim, ...]
    inferences: tuple[ConsumerClaim, ...]
    unknowns: tuple[ConsumerClaim, ...]
    next_action: str
    handoff: HandoffBrief

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConsumerIntelligenceService:
    """Build a conservative, auditable B2C qualification and handoff.

    Public social activity is treated as a weak signal. Only explicit, attributable
    intent plus a valid contact-purpose consent can result in an SQL.
    """

    DIMENSIONS: ClassVar[tuple[str, ...]] = (
        "fit", "need", "intent", "urgency", "capacity", "engagement"
    )
    REQUIRED_FOR_SQL: ClassVar[dict[str, int]] = {
        "fit": 60,
        "need": 60,
        "intent": 70,
        "urgency": 50,
        "capacity": 50,
        "engagement": 40,
    }
    WEIGHTS: ClassVar[dict[str, float]] = {
        "fit": 0.15,
        "need": 0.25,
        "intent": 0.25,
        "urgency": 0.15,
        "capacity": 0.10,
        "engagement": 0.10,
    }
    WEAK_SIGNALS: ClassVar[frozenset[str]] = frozenset({
        "like", "liked", "follow", "follower", "view", "impression",
        "curtida", "seguiu", "visualizacao", "visualização",
    })
    STRONG_INTENT_SIGNALS: ClassVar[frozenset[str]] = frozenset({
        "inbound_dm", "form_submitted", "lead_form", "price_request",
        "quote_request", "booking", "checkout_started", "asked_price",
        "dm_iniciada", "formulario_enviado", "formulário_enviado",
        "pediu_preco", "pediu_preço", "pediu_orcamento", "pediu_orçamento",
        "agendamento",
    })
    VERIFIED_STATUSES: ClassVar[frozenset[str]] = frozenset({"VERIFIED", "CONFIRMED"})
    CRITICAL_FIELDS: ClassVar[dict[str, tuple[str, ...]]] = {
        "need": ("need", "pain"),
        "intent": ("intent", "purchase_intent"),
        "urgency": ("urgency", "timing"),
        "capacity": ("capacity", "budget"),
    }

    def generate(
        self,
        person: Mapping[str, Any] | Any,
        *,
        evidence: Iterable[Mapping[str, Any] | Any] = (),
        consent: Mapping[str, Any] | ConsentGate | None = None,
    ) -> CustomerRoom:
        data = self._data(person)
        consent_gate = self._consent(consent or data.get("consent"))
        facts = self._facts(evidence)
        fact_fields = {claim.field for claim in facts}
        signals = self._signals(data)
        strong_intent = bool(signals & self.STRONG_INTENT_SIGNALS)
        only_weak_social = bool(signals) and signals <= self.WEAK_SIGNALS
        inferences = self._inferences(signals, strong_intent)
        dimensions = self._dimensions(data, fact_fields, signals)
        confidence = self._score(data.get("data_confidence_score"))
        if confidence is None:
            confidence = round(sum(claim.confidence or 0 for claim in facts) / len(facts) * 100) if facts else 0
        readiness = self._readiness(dimensions, confidence, only_weak_social)
        status, reasons = self._status(
            data, consent_gate, dimensions, confidence, strong_intent, only_weak_social
        )
        unknowns = self._unknowns(fact_fields, dimensions)
        qualification = ConsumerQualification(status, readiness, confidence, dimensions, reasons)
        name = self._text(data.get("display_name") or data.get("name")) or "Pessoa"
        offer = self._text(data.get("recommended_offer"))
        next_action = self._next_action(status, consent_gate, unknowns)
        handoff = HandoffBrief(
            ready=status == ConsumerStatus.SQL,
            objective=("Conduzir para pagamento ou reunião" if status == ConsumerStatus.SQL
                       else "Completar qualificação antes da oferta"),
            verified_context=tuple(f"{claim.field}: {claim.value}" for claim in facts),
            questions_to_confirm=tuple(
                f"Confirmar {claim.field}" for claim in unknowns
            ),
            recommended_offer=offer or "Definir após confirmar necessidade e capacidade",
            owner_action=next_action,
        )
        return CustomerRoom(
            person_id=self._text(data.get("id")),
            display_name=name,
            source_platform=self._text(data.get("source_platform") or data.get("platform")),
            qualification=qualification,
            consent=consent_gate,
            facts=facts,
            inferences=inferences,
            unknowns=unknowns,
            next_action=next_action,
            handoff=handoff,
        )

    def _facts(self, evidence: Iterable[Mapping[str, Any] | Any]) -> tuple[ConsumerClaim, ...]:
        result: list[ConsumerClaim] = []
        for item in evidence:
            row = self._data(item)
            field = self._text(row.get("field") or row.get("field_name"))
            value = self._text(row.get("value") or row.get("normalized_value") or row.get("raw_value"))
            source = self._text(row.get("source_url") or row.get("source"))
            confidence = self._confidence(row.get("confidence"))
            if (field and value and source
                    and self._text(row.get("status")).upper() in self.VERIFIED_STATUSES
                    and confidence >= 0.7):
                result.append(ConsumerClaim(
                    field, value, ClaimKind.FACT, source_url=source, confidence=confidence
                ))
        return tuple(result)

    def _inferences(self, signals: set[str], strong: bool) -> tuple[ConsumerClaim, ...]:
        if strong:
            return (ConsumerClaim(
                "intent", "Intenção comercial provável", ClaimKind.INFERENCE,
                "A pessoa realizou uma ação explícita; a intenção ainda deve ser confirmada.",
                confidence=0.7,
            ),)
        if signals & self.WEAK_SIGNALS:
            return (ConsumerClaim(
                "engagement", "Interação social fraca", ClaimKind.INFERENCE,
                "Curtidas, visualizações e follows não comprovam intenção de compra.",
                confidence=0.2,
            ),)
        return ()

    def _dimensions(
        self, data: Mapping[str, Any], fact_fields: set[str], signals: set[str]
    ) -> tuple[QualificationDimension, ...]:
        result = []
        for name in self.DIMENSIONS:
            value = self._score(data.get(f"{name}_score"))
            aliases = self.CRITICAL_FIELDS.get(name, (name,))
            known = value is not None and (name in {"fit", "engagement"} or bool(set(aliases) & fact_fields))
            if name == "engagement" and value is None and signals:
                value = 20 if signals <= self.WEAK_SIGNALS else 50
                known = True
            result.append(QualificationDimension(
                name, value, known,
                "Confirmado por evidência" if known else "Ainda não confirmado por evidência",
            ))
        return tuple(result)

    def _readiness(
        self, dimensions: tuple[QualificationDimension, ...], confidence: int, weak_only: bool
    ) -> int:
        values = {item.name: item.score or 0 for item in dimensions}
        total = round(sum(values[name] * self.WEIGHTS[name] for name in self.DIMENSIONS))
        if confidence < 60:
            total = min(total, 59)
        if weak_only:
            total = min(total, 39)
        return max(0, min(100, total))

    def _status(
        self,
        data: Mapping[str, Any],
        consent: ConsentGate,
        dimensions: tuple[QualificationDimension, ...],
        confidence: int,
        strong_intent: bool,
        weak_only: bool,
    ) -> tuple[ConsumerStatus, tuple[str, ...]]:
        if self._truthy(data.get("opted_out")) or self._text(data.get("disqualifier")):
            return ConsumerStatus.DISQUALIFIED, ("Opt-out ou desqualificador registrado",)
        if not consent.can_contact:
            return ConsumerStatus.BLOCKED, ("Consentimento válido para canal e finalidade é obrigatório",)
        scores = {item.name: item.score for item in dimensions}
        known = all(item.known for item in dimensions)
        thresholds = all((scores[name] or 0) >= minimum
                         for name, minimum in self.REQUIRED_FOR_SQL.items())
        if known and thresholds and confidence >= 60 and strong_intent and not weak_only:
            return ConsumerStatus.SQL, ("Intenção explícita e critérios comerciais confirmados",)
        if weak_only:
            return ConsumerStatus.NURTURE, ("Sinais sociais fracos não qualificam para venda",)
        if strong_intent:
            return ConsumerStatus.RESEARCH, ("Há intenção explícita, mas faltam critérios confirmados",)
        return ConsumerStatus.NURTURE, ("Manter nutrição até surgir intenção explícita",)

    def _unknowns(
        self, fact_fields: set[str], dimensions: tuple[QualificationDimension, ...]
    ) -> tuple[ConsumerClaim, ...]:
        unknown: list[ConsumerClaim] = []
        dimension_by_name = {item.name: item for item in dimensions}
        for name, aliases in self.CRITICAL_FIELDS.items():
            if not (set(aliases) & fact_fields) or not dimension_by_name[name].known:
                unknown.append(ConsumerClaim(
                    name, "Desconhecido", ClaimKind.UNKNOWN,
                    "Informação comercial crítica ainda não verificada",
                ))
        return tuple(unknown)

    @staticmethod
    def _next_action(
        status: ConsumerStatus, consent: ConsentGate, unknowns: tuple[ConsumerClaim, ...]
    ) -> str:
        if status == ConsumerStatus.BLOCKED:
            return "Obter consentimento válido antes de qualquer contato"
        if status == ConsumerStatus.DISQUALIFIED:
            return "Encerrar contato e respeitar a supressão"
        if status == ConsumerStatus.SQL:
            return "Entregar ao dono com oferta, contexto e próximo compromisso preparados"
        if unknowns:
            return f"Confirmar {unknowns[0].field} por canal autorizado"
        return "Manter em nutrição até manifestação explícita de intenção"

    def _consent(self, value: Mapping[str, Any] | ConsentGate | Any) -> ConsentGate:
        if isinstance(value, ConsentGate):
            return value
        data = self._data(value) if value is not None else {}
        return ConsentGate(
            granted=self._truthy(data.get("granted") or data.get("consented")),
            channel=self._text(data.get("channel")),
            purpose=self._text(data.get("purpose")),
            source=self._text(data.get("source")),
            recorded_at=self._text(data.get("recorded_at")),
            reason=self._text(data.get("reason")),
        )

    @staticmethod
    def _signals(data: Mapping[str, Any]) -> set[str]:
        raw = data.get("signals") or ()
        if isinstance(raw, str):
            raw = raw.replace(";", ",").split(",")
        return {str(item).strip().casefold() for item in raw if str(item).strip()}

    @staticmethod
    def _data(value: Any) -> Mapping[str, Any]:
        if isinstance(value, Mapping):
            return value
        fields = getattr(value, "__dataclass_fields__", {})
        return {name: getattr(value, name) for name in fields}

    @staticmethod
    def _score(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _truthy(value: Any) -> bool:
        return value is True or str(value).strip().casefold() in {"1", "true", "yes", "sim"}

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value).strip()
