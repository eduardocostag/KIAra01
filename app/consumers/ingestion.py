"""Provider-neutral, fail-closed normalization for inbound consumer leads.

This module deliberately performs no network calls and writes no data. Provider
webhook handlers can adapt their payloads here before handing validated records
to a persistence boundary.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, ClassVar

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_TEXT_LENGTH = 4_000
MAX_FIELDS = 100
MAX_DEPTH = 6


class ConsumerIngestionError(ValueError):
    """A payload was rejected before entering the consumer pipeline."""


class SocialPlatform(StrEnum):
    FORM = "form"
    META = "meta"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"


_ALLOWED_ORIGINS: dict[SocialPlatform, frozenset[str]] = {
    SocialPlatform.FORM: frozenset({"website_form", "landing_page", "manual_import"}),
    SocialPlatform.META: frozenset({"meta_lead_ads", "instagram_inbound", "facebook_inbound"}),
    SocialPlatform.TIKTOK: frozenset({"tiktok_lead_generation", "tiktok_inbound"}),
    SocialPlatform.LINKEDIN: frozenset({"linkedin_lead_gen", "linkedin_event"}),
}

_SENSITIVE_FIELDS = frozenset(
    {
        "biometric",
        "biometrics",
        "disability",
        "ethnicity",
        "facial_embedding",
        "facial_recognition",
        "genetic_data",
        "health",
        "medical_condition",
        "political_opinion",
        "politics",
        "race",
        "religion",
        "sexual_orientation",
        "union_membership",
    }
)


@dataclass(frozen=True, slots=True)
class ConsumerLeadPayload:
    platform: SocialPlatform
    origin: str
    external_id: str
    idempotency_key: str
    captured_at: datetime
    consent_at: datetime
    consent_source: str
    consent_purpose: str
    allowed_channels: tuple[str, ...]
    full_name: str = ""
    email: str = ""
    phone: str = ""
    social_handle: str = ""
    campaign_id: str = ""
    message: str = ""
    attributes: tuple[tuple[str, str], ...] = ()


def _text(value: Any, field: str, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ConsumerIngestionError(f"Campo {field!r} deve ser texto.")
    result = str(value).strip()
    if required and not result:
        raise ConsumerIngestionError(f"Campo obrigatório ausente: {field}.")
    if len(result) > MAX_TEXT_LENGTH:
        raise ConsumerIngestionError(f"Campo {field!r} excede o limite permitido.")
    return result


def _instant(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result_value = value.replace("Z", "+00:00")
            result = datetime.fromisoformat(result_value)
        except ValueError as exc:
            raise ConsumerIngestionError(f"Data inválida em {field!r}.") from exc
    else:
        raise ConsumerIngestionError(f"Data obrigatória ausente: {field}.")
    if result.tzinfo is None:
        raise ConsumerIngestionError(f"Data {field!r} deve conter fuso horário.")
    return result.astimezone(UTC)


def _inspect(value: Any, *, depth: int = 0) -> int:
    if depth > MAX_DEPTH:
        raise ConsumerIngestionError("Payload excede a profundidade permitida.")
    if isinstance(value, Mapping):
        count = len(value)
        for key, child in value.items():
            normalized = str(key).strip().casefold().replace("-", "_").replace(" ", "_")
            if normalized in _SENSITIVE_FIELDS:
                raise ConsumerIngestionError(f"Dado pessoal sensível não permitido: {key}.")
            count += _inspect(child, depth=depth + 1)
        return count
    if isinstance(value, (list, tuple)):
        return sum(_inspect(child, depth=depth + 1) for child in value)
    if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
        raise ConsumerIngestionError("Payload contém texto acima do limite permitido.")
    return 0


def _validate_envelope(payload: Mapping[str, Any]) -> None:
    try:
        encoded = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ConsumerIngestionError("Payload não é serializável.") from exc
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ConsumerIngestionError("Payload excede 64 KiB.")
    if _inspect(payload) > MAX_FIELDS:
        raise ConsumerIngestionError("Payload possui campos demais.")


def _reject_minor(payload: Mapping[str, Any], captured_at: datetime) -> None:
    if payload.get("is_minor") is True or payload.get("declared_minor") is True:
        raise ConsumerIngestionError("Leads menores de idade não são aceitos.")
    age = payload.get("age")
    if age not in (None, ""):
        try:
            normalized_age = int(age)
        except (TypeError, ValueError) as exc:
            raise ConsumerIngestionError("Idade inválida.") from exc
        if normalized_age < 18:
            raise ConsumerIngestionError("Leads menores de idade não são aceitos.")
    birth_date = payload.get("birth_date") or payload.get("date_of_birth")
    if birth_date:
        try:
            born = date.fromisoformat(str(birth_date))
        except ValueError as exc:
            raise ConsumerIngestionError("Data de nascimento inválida.") from exc
        years = captured_at.date().year - born.year
        years -= (captured_at.date().month, captured_at.date().day) < (born.month, born.day)
        if years < 18:
            raise ConsumerIngestionError("Leads menores de idade não são aceitos.")


def normalize_consumer_payload(
    payload: Mapping[str, Any], *, platform: SocialPlatform | str, origin: str
) -> ConsumerLeadPayload:
    """Validate and normalize one already-authenticated inbound event."""
    if not isinstance(payload, Mapping):
        raise ConsumerIngestionError("Payload deve ser um objeto.")
    _validate_envelope(payload)
    try:
        normalized_platform = SocialPlatform(str(platform).strip().casefold())
    except ValueError as exc:
        raise ConsumerIngestionError("Plataforma não suportada.") from exc
    normalized_origin = _text(origin, "origin", required=True).casefold()
    if normalized_origin not in _ALLOWED_ORIGINS[normalized_platform]:
        raise ConsumerIngestionError("Origem incompatível com a plataforma.")

    captured_at = _instant(payload.get("captured_at"), "captured_at")
    _reject_minor(payload, captured_at)
    consent = payload.get("consent")
    if not isinstance(consent, Mapping) or consent.get("granted") is not True:
        raise ConsumerIngestionError("Consentimento explícito é obrigatório.")
    consent_at = _instant(consent.get("at"), "consent.at")
    if consent_at > captured_at:
        raise ConsumerIngestionError("Consentimento não pode ser posterior à captura.")
    consent_source = _text(consent.get("source"), "consent.source", required=True)
    consent_purpose = _text(consent.get("purpose"), "consent.purpose", required=True)
    channels_value = consent.get("channels")
    if not isinstance(channels_value, (list, tuple)) or not channels_value:
        raise ConsumerIngestionError("Ao menos um canal consentido é obrigatório.")
    channels = tuple(dict.fromkeys(_text(v, "consent.channels", required=True).casefold()
                                   for v in channels_value))
    allowed_channels = {"email", "phone", "sms", "whatsapp", "instagram", "facebook",
                        "tiktok", "linkedin"}
    if not set(channels) <= allowed_channels:
        raise ConsumerIngestionError("Canal de consentimento não suportado.")

    external_id = _text(payload.get("external_id"), "external_id", required=True)
    if not any(_text(payload.get(key), key) for key in ("email", "phone", "social_handle")):
        raise ConsumerIngestionError("Informe email, telefone ou identidade social.")
    stable = f"consumer:{normalized_platform.value}:{normalized_origin}:{external_id}"
    idempotency_key = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    reserved = {
        "external_id", "captured_at", "consent", "full_name", "email", "phone",
        "social_handle", "campaign_id", "message", "age", "birth_date", "date_of_birth",
        "is_minor", "declared_minor",
    }
    attributes = tuple(sorted(
        (str(key), _text(value, str(key))) for key, value in payload.items()
        if key not in reserved and isinstance(value, (str, int, float)) and not isinstance(value, bool)
    ))
    return ConsumerLeadPayload(
        platform=normalized_platform,
        origin=normalized_origin,
        external_id=external_id,
        idempotency_key=idempotency_key,
        captured_at=captured_at,
        consent_at=consent_at,
        consent_source=consent_source,
        consent_purpose=consent_purpose,
        allowed_channels=channels,
        full_name=_text(payload.get("full_name"), "full_name"),
        email=_text(payload.get("email"), "email"),
        phone=_text(payload.get("phone"), "phone"),
        social_handle=_text(payload.get("social_handle"), "social_handle"),
        campaign_id=_text(payload.get("campaign_id"), "campaign_id"),
        message=_text(payload.get("message"), "message"),
        attributes=attributes,
    )


class _BaseAdapter:
    platform: ClassVar[SocialPlatform]
    default_origin: ClassVar[str]

    def adapt(self, payload: Mapping[str, Any], *, origin: str | None = None) -> ConsumerLeadPayload:
        return normalize_consumer_payload(
            payload, platform=self.platform, origin=origin or self.default_origin
        )


class GenericFormAdapter(_BaseAdapter):
    platform = SocialPlatform.FORM
    default_origin = "website_form"


class MetaLeadAdapter(_BaseAdapter):
    platform = SocialPlatform.META
    default_origin = "meta_lead_ads"


class TikTokLeadAdapter(_BaseAdapter):
    platform = SocialPlatform.TIKTOK
    default_origin = "tiktok_lead_generation"


class LinkedInLeadAdapter(_BaseAdapter):
    platform = SocialPlatform.LINKEDIN
    default_origin = "linkedin_lead_gen"
