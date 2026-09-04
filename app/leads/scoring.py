from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from app.leads.store import CommercialProfile


@dataclass(frozen=True, slots=True)
class ScoreReason:
    dimension: str
    points: int
    reason: str
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class LeadScore:
    """Resultado reproduzível, mantendo a API histórica de ``total``."""

    total: int
    explanation: str
    qualification: str
    confidence: int = 0
    fit: int = 0
    opportunity: int = 0
    engagement: int = 0
    priority: int = 0
    model_version: str = "sdr-multidimensional-v1"
    breakdown: tuple[ScoreReason, ...] = ()
    need: int = 0
    timing: int = 0
    authority: int = 0
    capacity: int = 0
    readiness: int = 0
    qualification_status: str = "precisa_pesquisar"
    missing_information: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["breakdown"] = [asdict(reason) for reason in self.breakdown]
        return payload


class LeadScoringPolicy:
    """Separa qualidade do dado, fit, oportunidade e engajamento comercial."""

    MODEL_VERSION: ClassVar[str] = "sdr-multidimensional-v1"

    def evaluate(self, lead: dict[str, object], profile: CommercialProfile) -> LeadScore:
        reasons: list[ScoreReason] = []
        confidence = self._confidence(lead, reasons)
        fit = self._fit(lead, profile, reasons)
        opportunity = self._opportunity(lead, reasons)
        engagement, has_engagement = self._engagement(lead, reasons)
        need = self._commercial_signal(lead, "need", reasons)
        if not need:
            # Uma lacuna verificada é evidência de necessidade, mas não prova intenção de compra.
            need = min(70, opportunity)
        timing = self._commercial_signal(lead, "timing", reasons)
        authority = self._commercial_signal(lead, "authority", reasons)
        capacity = self._commercial_signal(lead, "capacity", reasons)

        if has_engagement:
            priority = round(
                confidence * 0.25 + fit * 0.35 + opportunity * 0.30 + engagement * 0.10
            )
        else:
            # Engagement ainda não existe antes do contato e não deve punir o lead.
            priority = round((confidence * 0.25 + fit * 0.35 + opportunity * 0.30) / 0.90)
        if confidence < 60:
            priority = min(priority, 59)
            reasons.append(
                ScoreReason(
                    "priority",
                    0,
                    "prioridade limitada por baixa confiança dos dados",
                    f"confidence={confidence}",
                )
            )
        priority = max(0, min(100, priority))

        if priority >= 75:
            qualification = "Alta aderência — priorizar abordagem personalizada"
        elif priority >= 55:
            qualification = "Aderência média — revisar contexto antes do contato"
        else:
            qualification = "Baixa confiança — enriquecer antes de abordar"
        explanation = "; ".join(
            f"{reason.dimension}: +{reason.points} {reason.reason}" for reason in reasons
        )
        dimensions = {
            "necessidade": need,
            "timing": timing,
            "autoridade": authority,
            "capacidade": capacity,
        }
        missing = tuple(name for name, value in dimensions.items() if value == 0)
        readiness = round(
            confidence * 0.15 + fit * 0.20 + need * 0.25 + timing * 0.15
            + authority * 0.15 + capacity * 0.10
        )
        disqualifiers = lead.get("disqualifiers", ())
        if isinstance(disqualifiers, str):
            disqualifiers = tuple(item.strip() for item in disqualifiers.split(",") if item.strip())
        if disqualifiers:
            status = "desqualificado"
            readiness = 0
        elif not missing and confidence >= 70 and fit >= 70 and readiness >= 65:
            status = "sql_pronto"
        elif fit >= 60 and confidence >= 60:
            status = "nutricao" if timing == 0 else "precisa_pesquisar"
        else:
            status = "precisa_pesquisar"
        return LeadScore(
            total=priority,
            explanation=explanation,
            qualification=qualification,
            confidence=confidence,
            fit=fit,
            opportunity=opportunity,
            engagement=engagement,
            priority=priority,
            model_version=self.MODEL_VERSION,
            breakdown=tuple(reasons),
            need=need,
            timing=timing,
            authority=authority,
            capacity=capacity,
            readiness=max(0, min(100, readiness)),
            qualification_status=status,
            missing_information=missing,
        )

    @staticmethod
    def _commercial_signal(
        lead: dict[str, object], dimension: str, reasons: list[ScoreReason]
    ) -> int:
        """Aceita apenas sinais explícitos; ausência não é convertida em suposição."""
        aliases = {
            "need": ("need_score", "need", "pain_score"),
            "timing": ("timing_score", "timing", "urgency_score"),
            "authority": ("authority_score", "authority", "decision_maker_score"),
            "capacity": ("capacity_score", "capacity", "budget_score"),
        }
        raw: object = 0
        evidence_key = ""
        for key in aliases[dimension]:
            if key in lead and lead[key] not in (None, ""):
                raw, evidence_key = lead[key], key
                break
        try:
            value = max(0, min(100, int(float(str(raw)))))
        except (TypeError, ValueError):
            truthy = str(raw).casefold().strip()
            value = 70 if truthy in {"sim", "yes", "verified", "confirmado"} else 0
        if value:
            reasons.append(
                ScoreReason(dimension, value, "sinal comercial explícito", evidence_key)
            )
        return value

    @staticmethod
    def _confidence(lead: dict[str, object], reasons: list[ScoreReason]) -> int:
        total = 0
        for points, label, field in (
            (15, "nome observado", "name"),
            (15, "endereço observado", "address"),
            (20, "origem rastreável", "maps_url"),
            (30, "WhatsApp observado", "whatsapp"),
        ):
            if str(lead.get(field, "")).strip():
                total += points
                reasons.append(ScoreReason("confidence", points, label, field))
        if int(lead.get("review_count", 0) or 0) > 0 or float(lead.get("rating", 0) or 0) > 0:
            total += 10
            reasons.append(ScoreReason("confidence", 10, "reputação observada", "Google Maps"))
        website_status = str(lead.get("website_status", "")).upper()
        if website_status in {"FOUND", "NOT_LISTED_ON_MAPS", "NOT_FOUND_IN_EXTERNAL_SEARCH"}:
            total += 10
            reasons.append(
                ScoreReason("confidence", 10, "status de site verificado", website_status)
            )
        elif "website" in lead and str(lead.get("maps_url", "")).strip():
            total += 10
            reasons.append(ScoreReason("confidence", 10, "site conferido na ficha", "Google Maps"))
        return min(100, total)

    def _fit(
        self,
        lead: dict[str, object],
        profile: CommercialProfile,
        reasons: list[ScoreReason],
    ) -> int:
        total = 0
        niche = str(lead.get("niche", "")).strip() or str(lead.get("name", "")).strip()
        address = str(lead.get("address", lead.get("location", ""))).strip()
        if profile.target_niches.strip():
            if self._matches(niche, profile.target_niches):
                total += 60
                reasons.append(ScoreReason("fit", 60, "nicho aderente ao ICP", niche))
        else:
            total += 30
            reasons.append(ScoreReason("fit", 30, "nicho ainda não restringido", "UNKNOWN"))
        if profile.target_locations.strip():
            if self._matches(address, profile.target_locations):
                total += 40
                reasons.append(ScoreReason("fit", 40, "localização prioritária", address))
        else:
            total += 20
            reasons.append(ScoreReason("fit", 20, "região ainda não restringida", "UNKNOWN"))
        return min(100, total)

    @staticmethod
    def _opportunity(lead: dict[str, object], reasons: list[ScoreReason]) -> int:
        total = 0
        website = str(lead.get("website", "")).strip()
        status = str(lead.get("website_status", "")).upper()
        if status == "NOT_FOUND_IN_EXTERNAL_SEARCH":
            total += 70
            reasons.append(
                ScoreReason(
                    "opportunity", 70, "lacuna digital: site não encontrado externamente", status
                )
            )
        elif status == "NOT_LISTED_ON_MAPS" or (not website and lead.get("maps_url")):
            total += 60
            reasons.append(
                ScoreReason(
                    "opportunity", 60, "lacuna digital: site não listado na ficha", "Google Maps"
                )
            )
        review_count = int(lead.get("review_count", 0) or 0)
        rating = float(lead.get("rating", 0) or 0)
        if rating >= 4.7 and review_count >= 100:
            total += 40
            reasons.append(
                ScoreReason(
                    "opportunity", 40, "forte atividade pública", f"{rating:.1f}/{review_count}"
                )
            )
        elif rating >= 4.5 and review_count >= 30:
            total += 25
            reasons.append(
                ScoreReason(
                    "opportunity", 25, "atividade pública relevante", f"{rating:.1f}/{review_count}"
                )
            )
        elif review_count > 0:
            total += 10
            reasons.append(
                ScoreReason("opportunity", 10, "atividade pública inicial", str(review_count))
            )
        return min(100, total)

    @staticmethod
    def _engagement(lead: dict[str, object], reasons: list[ScoreReason]) -> tuple[int, bool]:
        outcome = str(lead.get("outcome", lead.get("stage", ""))).casefold().strip()
        if not outcome or outcome in {"novo", "new"}:
            return 0, False
        levels = {
            "contatado": 20,
            "contacted": 20,
            "sem_resposta": 10,
            "respondeu": 60,
            "replied": 60,
            "reuniao": 85,
            "reunião": 85,
            "meeting": 85,
            "discovery": 88,
            "proposta": 92,
            "proposal": 92,
            "negociacao": 95,
            "negociação": 95,
            "negotiation": 95,
            "contrato": 97,
            "contract": 97,
            "assinatura": 99,
            "signature": 99,
            "convertido": 100,
            "won": 100,
            "perdido": 0,
            "lost": 0,
        }
        value = levels.get(outcome, 0)
        reasons.append(ScoreReason("engagement", value, "sinal de interação registrado", outcome))
        return value, True

    @classmethod
    def _matches(cls, value: str, configured: str) -> bool:
        candidates = [cls._normalize(item) for item in configured.replace(";", ",").split(",")]
        normalized = cls._normalize(value)
        return any(candidate and candidate in normalized for candidate in candidates)

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.casefold())
        return "".join(
            character for character in decomposed if not unicodedata.combining(character)
        )
