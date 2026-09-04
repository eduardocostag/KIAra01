"""Safe application flow for authorized Instagram B2C inbound messages.

The boundary intentionally stops at a response draft. Delivery belongs to an
approved integration and must revalidate consent immediately before sending.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .ingestion import ConsumerIngestionError, MetaLeadAdapter
from .intelligence import ConsumerIntelligenceService, CustomerRoom
from .store import ConsumerStore

_OPT_OUT_TERMS = frozenset({
    "pare", "parar", "sair", "cancelar", "cancele", "remover", "remova",
    "nao quero", "não quero", "stop", "unsubscribe",
})
_PRICE_TERMS = frozenset({"preco", "preço", "valor", "orcamento", "orçamento"})


@dataclass(frozen=True, slots=True)
class InstagramDraft:
    """A local preview; this type has no delivery operation by design."""

    channel: str
    recipient_scoped_id: str
    content: str
    requires_human_approval: bool = True
    sent: bool = False


@dataclass(frozen=True, slots=True)
class InstagramFlowResult:
    person_id: str
    idempotency_key: str
    room: CustomerRoom
    draft: InstagramDraft | None
    opted_out: bool
    blocked_reason: str = ""


DraftBuilder = Callable[[CustomerRoom, str], str]


class InstagramB2CFlow:
    """Persist, qualify and prepare one authenticated Instagram inbound event."""

    def __init__(
        self,
        store: ConsumerStore,
        *,
        intelligence: ConsumerIntelligenceService | None = None,
        draft_builder: DraftBuilder | None = None,
    ) -> None:
        self._store = store
        self._intelligence = intelligence or ConsumerIntelligenceService()
        self._draft_builder = draft_builder or self._default_draft

    def process(self, payload: Mapping[str, Any]) -> InstagramFlowResult:
        lead = MetaLeadAdapter().adapt(payload, origin="instagram_inbound")
        if "instagram" not in lead.allowed_channels:
            raise ConsumerIngestionError(
                "Consentimento para o canal Instagram é obrigatório."
            )

        person_id = self._store.upsert_person(
            display_name=lead.full_name,
            platform="instagram",
            scoped_id=lead.external_id,
            email=lead.email,
            phone=lead.phone,
            source="instagram_inbound",
        )
        self._store.record_consent(
            person_id,
            channel="instagram",
            purpose=lead.consent_purpose,
            source=lead.consent_source,
        )
        self._store.add_touchpoint(
            person_id,
            platform="instagram",
            kind="direct_message",
            direction="inbound",
            content=lead.message,
            campaign=lead.campaign_id,
            occurred_at=lead.captured_at.isoformat(),
        )

        opted_out = self._is_opt_out(lead.message)
        if opted_out:
            self._store.record_consent(
                person_id,
                channel="instagram",
                purpose=lead.consent_purpose,
                status="revoked",
                source="instagram_inbound_message",
            )

        signals = ["inbound_dm"]
        if self._mentions_price(lead.message):
            signals.append("asked_price")
        evidence = []
        if lead.message:
            evidence.append({
                "field": "inbound_message",
                "value": lead.message,
                "status": "VERIFIED",
                "source": f"instagram://inbound/{lead.external_id}",
                "confidence": 1.0,
            })
        room = self._intelligence.generate(
            {
                "id": person_id,
                "display_name": lead.full_name,
                "source_platform": "instagram",
                "signals": signals,
                "opted_out": opted_out,
            },
            evidence=evidence,
            consent={
                "granted": not opted_out and self._store.has_active_consent(
                    person_id, channel="instagram", purpose=lead.consent_purpose
                ),
                "channel": "instagram",
                "purpose": lead.consent_purpose,
                "source": lead.consent_source,
                "recorded_at": lead.consent_at.isoformat(),
                "reason": "opt_out" if opted_out else "",
            },
        )

        if opted_out:
            return InstagramFlowResult(
                person_id, lead.idempotency_key, room, None, True,
                "Opt-out recebido; consentimento revogado e resposta comercial bloqueada.",
            )

        content = self._draft_builder(room, lead.message).strip()
        if not content:
            raise ValueError("O gerador retornou um rascunho vazio.")
        draft = InstagramDraft("instagram", lead.external_id, content)
        return InstagramFlowResult(
            person_id, lead.idempotency_key, room, draft, False
        )

    @staticmethod
    def _normalized_words(message: str) -> str:
        return " ".join(message.strip().casefold().split())

    @classmethod
    def _is_opt_out(cls, message: str) -> bool:
        normalized = cls._normalized_words(message)
        return normalized in _OPT_OUT_TERMS or any(
            normalized.startswith(f"{term} ") for term in _OPT_OUT_TERMS
        )

    @classmethod
    def _mentions_price(cls, message: str) -> bool:
        normalized = cls._normalized_words(message)
        words = set(re.findall(r"\w+", normalized, flags=re.UNICODE))
        return bool(words & _PRICE_TERMS)

    @staticmethod
    def _default_draft(room: CustomerRoom, _message: str) -> str:
        if room.unknowns:
            missing = room.unknowns[0].field
            return (
                f"Olá, {room.display_name}! Obrigada pela mensagem. "
                f"Para eu te orientar melhor, pode me contar um pouco sobre {missing}?"
            )
        return (
            f"Olá, {room.display_name}! Obrigada pela mensagem. "
            "Preparei o próximo passo para sua solicitação."
        )
