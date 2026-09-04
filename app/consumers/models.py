from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class B2CStage(StrEnum):
    NEW_OPT_IN = "novo_opt_in"
    ENGAGED = "engajado"
    QUALIFYING = "qualificando"
    READY_TO_BUY = "pronto_para_comprar"
    MEETING = "reuniao_consulta"
    OFFER = "oferta"
    PAYMENT_CONTRACT = "pagamento_contrato"
    CUSTOMER = "cliente"
    NURTURE = "nutricao"
    LOST = "perdido"


@dataclass(frozen=True, slots=True)
class PersonLead:
    id: str
    display_name: str
    stage: B2CStage
    email: str
    phone: str
    source: str
    notes: str
    created_at: str
    updated_at: str
    retained_until: str


@dataclass(frozen=True, slots=True)
class SocialIdentity:
    id: int
    person_id: str
    platform: str
    scoped_id: str
    handle: str
    profile_url: str
    verified_at: str


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    id: int
    person_id: str
    channel: str
    purpose: str
    status: str
    legal_basis: str
    source: str
    captured_at: str
    expires_at: str
    revoked_at: str


@dataclass(frozen=True, slots=True)
class Touchpoint:
    id: int
    person_id: str
    platform: str
    kind: str
    direction: str
    content: str
    campaign: str
    occurred_at: str

