from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar


class IntentKind(StrEnum):
    EXPLICIT_PROBLEM = "problema_explicito"
    DIRECT = "intencao_direta"
    TRIGGER = "evento_gatilho"
    INDIRECT = "intencao_indireta"
    AFFINITY = "afinidade"


class Temperature(StrEnum):
    DISCARD = "descartar"
    COLD = "frio"
    WARM = "morno"
    HOT = "quente"
    VERY_HOT = "hot"


@dataclass(frozen=True, slots=True)
class ProductBrief:
    product: str
    category: str
    price: str
    region: str
    market: str
    problem: str
    benefits: tuple[str, ...]
    barriers: tuple[str, ...]
    urgency_triggers: tuple[str, ...]
    icp_hypotheses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntentSignal:
    kind: IntentKind
    evidence: str
    occurred_at: datetime
    source: str


@dataclass(frozen=True, slots=True)
class ProspectEvidence:
    fit: int = 0
    capacity: int = 0
    contactability: int = 0
    information_quality: int = 0
    signals: tuple[IntentSignal, ...] = ()
    available_channels: tuple[str, ...] = ()
    instagram_inbound: bool = False
    instagram_official_api: bool = False
    opted_out: bool = False


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    fit: int
    intent: int
    urgency: int
    recency: int
    capacity: int
    contactability: int
    information_quality: int
    trigger_event: int

    @property
    def total(self) -> int:
        return sum(asdict(self).values())


@dataclass(frozen=True, slots=True)
class ChannelRoute:
    primary: str
    secondary: str
    backup: str
    execution_mode: str
    reason: str


@dataclass(frozen=True, slots=True)
class HunterDecision:
    score: ScoreBreakdown
    temperature: Temperature
    route: ChannelRoute
    next_action: str
    reasons: tuple[str, ...]
    model_version: str = "hunter-deterministic-v1"


class HunterEngine:
    """Motor B2C determinístico; não descobre perfis nem executa contatos."""

    INTENT_POINTS: ClassVar[dict[IntentKind, int]] = {
        IntentKind.EXPLICIT_PROBLEM: 25, IntentKind.DIRECT: 23,
        IntentKind.TRIGGER: 18, IntentKind.INDIRECT: 12, IntentKind.AFFINITY: 5,
    }
    CHANNEL_ORDER: ClassVar[tuple[str, ...]] = (
        "whatsapp", "email", "phone", "form", "instagram"
    )
    INTENT_TERMS: ClassVar[dict[IntentKind, tuple[str, ...]]] = {
        IntentKind.EXPLICIT_PROBLEM: ("nao consigo", "parou", "problema", "preciso resolver"),
        IntentKind.DIRECT: ("preciso", "procuro", "quero", "indica", "quanto custa", "orcamento"),
        IntentKind.TRIGGER: ("urgente", "hoje", "essa semana", "acabou de", "mudanca"),
        IntentKind.INDIRECT: ("pesquisando", "comparando", "pensando em", "interessado"),
        IntentKind.AFFINITY: (),
    }

    def build_product_brief(
        self, *, product: str, problem: str, category: str = "não informado",
        price: str = "não informado", region: str = "não informado",
        benefits: tuple[str, ...] = (), barriers: tuple[str, ...] = (),
        urgency_triggers: tuple[str, ...] = (), audience_hints: tuple[str, ...] = (),
    ) -> ProductBrief:
        product, problem = product.strip(), problem.strip()
        if not product or not problem:
            raise ValueError("produto e problema resolvido são obrigatórios")
        hypotheses = tuple(dict.fromkeys(item.strip() for item in audience_hints if item.strip()))
        hypotheses = hypotheses or (
            f"Pessoa na região {region} que relata: {problem}",
            f"Pessoa buscando ou comparando {product}",
        )
        return ProductBrief(product, category.strip(), price.strip(), region.strip(), "B2C", problem,
                            self._clean(benefits), self._clean(barriers),
                            self._clean(urgency_triggers), hypotheses)

    def detect_intent(
        self, *, text: str, occurred_at: datetime, source: str
    ) -> tuple[IntentSignal, ...]:
        """Classifica termos auditáveis; campanhas podem fornecer sinais já classificados."""
        normalized = self.normalize(text)
        return tuple(
            IntentSignal(kind, text.strip(), self._aware(occurred_at), source.strip())
            for kind, terms in self.INTENT_TERMS.items()
            if terms and any(term in normalized for term in terms)
        )

    def evaluate(self, evidence: ProspectEvidence, *, now: datetime | None = None) -> HunterDecision:
        instant = self._aware(now or datetime.now(UTC))
        if evidence.opted_out:
            empty = ScoreBreakdown(0, 0, 0, 0, 0, 0, 0, 0)
            route = ChannelRoute("nenhum", "nenhum", "nenhum", "bloqueado", "Opt-out registrado")
            return HunterDecision(empty, Temperature.DISCARD, route,
                                  "Encerrar e manter supressão", ("Opt-out prevalece",))
        signals = tuple(s for s in evidence.signals if s.evidence.strip() and s.source.strip())
        kinds = {signal.kind for signal in signals}
        newest_days = min((max(0, (instant - self._aware(s.occurred_at)).days) for s in signals),
                          default=None)
        score = ScoreBreakdown(
            self._scale(evidence.fit, 25),
            min(25, max((self.INTENT_POINTS[k] for k in kinds), default=0)),
            15 if IntentKind.EXPLICIT_PROBLEM in kinds else 12 if IntentKind.DIRECT in kinds
            else 7 if IntentKind.TRIGGER in kinds else 0,
            self._recency(newest_days), self._scale(evidence.capacity, 10),
            self._scale(evidence.contactability, 5),
            self._scale(evidence.information_quality, 5),
            5 if IntentKind.TRIGGER in kinds else 0,
        )
        route = self._route(evidence)
        temperature = self._temperature(score.total)
        reasons = tuple([f"{k.value}: evidência atribuível" for k in sorted(kinds, key=str)] +
                        [f"recência: {newest_days} dia(s)" if newest_days is not None
                         else "recência: sem sinal"])
        return HunterDecision(score, temperature, route,
                              self._next_action(temperature, route, bool(signals)), reasons)

    def _route(self, evidence: ProspectEvidence) -> ChannelRoute:
        channels = tuple(dict.fromkeys(c.casefold().strip() for c in evidence.available_channels))
        eligible = [channel for channel in self.CHANNEL_ORDER if channel in channels]
        if "instagram" in channels and not (evidence.instagram_inbound and
                                             evidence.instagram_official_api):
            if "instagram" in eligible:
                eligible.remove("instagram")
            eligible.append("instagram_assisted")
        primary, secondary, backup = (eligible + ["nenhum"] * 3)[:3]
        if primary == "instagram":
            return ChannelRoute(primary, secondary, backup, "aprovação_humana",
                                "Inbound via API oficial; preparar rascunho para aprovação")
        if primary == "instagram_assisted":
            return ChannelRoute(primary, secondary, backup, "fila_assistida",
                                "Instagram não autoriza DM fria automatizada")
        return ChannelRoute(primary, secondary, backup,
                            "aprovação_humana" if primary != "nenhum" else "pesquisa",
                            "Validar consentimento e política antes do contato")

    @staticmethod
    def _next_action(temp: Temperature, route: ChannelRoute, has_signal: bool) -> str:
        if not has_signal or temp in {Temperature.DISCARD, Temperature.COLD}:
            return "Não abordar; enriquecer evidências ou aguardar novo sinal"
        if route.execution_mode == "fila_assistida":
            return "Adicionar à fila humana; não automatizar DM no Instagram"
        if route.primary == "nenhum":
            return "Pesquisar canal comercial legítimo sem inventar dados"
        return f"Preparar abordagem contextual por {route.primary} para aprovação humana"

    @staticmethod
    def _temperature(score: int) -> Temperature:
        if score <= 30: return Temperature.DISCARD
        if score <= 50: return Temperature.COLD
        if score <= 70: return Temperature.WARM
        if score <= 85: return Temperature.HOT
        return Temperature.VERY_HOT

    @staticmethod
    def _recency(days: int | None) -> int:
        if days is None: return 0
        if days <= 1: return 10
        if days <= 7: return 8
        if days <= 30: return 5
        if days <= 90: return 2
        return 0

    @staticmethod
    def _scale(value: int, maximum: int) -> int:
        return round(max(0, min(100, value)) * maximum / 100)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _clean(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(item.strip() for item in values if item.strip())

    @staticmethod
    def normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        return "".join(char for char in normalized if not unicodedata.combining(char))
