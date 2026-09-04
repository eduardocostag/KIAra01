from __future__ import annotations

from copy import deepcopy

import pytest

from app.consumers.ingestion import (
    ConsumerIngestionError,
    GenericFormAdapter,
    LinkedInLeadAdapter,
    MetaLeadAdapter,
    SocialPlatform,
    TikTokLeadAdapter,
    normalize_consumer_payload,
)


@pytest.fixture
def valid_payload() -> dict:
    return {
        "external_id": "lead-42",
        "captured_at": "2026-09-03T12:00:00-03:00",
        "full_name": "Ana Silva",
        "email": "ana@example.com",
        "campaign_id": "campaign-7",
        "message": "Quero receber uma proposta.",
        "consent": {
            "granted": True,
            "at": "2026-09-03T11:59:00-03:00",
            "source": "checkbox_form",
            "purpose": "contato comercial solicitado",
            "channels": ["email", "whatsapp", "email"],
        },
    }


def test_normalizes_payload_and_builds_stable_idempotency_key(valid_payload: dict) -> None:
    first = GenericFormAdapter().adapt(valid_payload)
    second = GenericFormAdapter().adapt(deepcopy(valid_payload))

    assert first.platform is SocialPlatform.FORM
    assert first.origin == "website_form"
    assert first.allowed_channels == ("email", "whatsapp")
    assert first.idempotency_key == second.idempotency_key
    assert len(first.idempotency_key) == 64


@pytest.mark.parametrize(
    ("adapter", "platform"),
    [
        (MetaLeadAdapter(), SocialPlatform.META),
        (TikTokLeadAdapter(), SocialPlatform.TIKTOK),
        (LinkedInLeadAdapter(), SocialPlatform.LINKEDIN),
    ],
)
def test_provider_adapters_are_local_and_normalize(valid_payload, adapter, platform) -> None:
    assert adapter.adapt(valid_payload).platform is platform


def test_rejects_missing_or_implicit_consent(valid_payload: dict) -> None:
    valid_payload["consent"]["granted"] = "true"
    with pytest.raises(ConsumerIngestionError, match="Consentimento explícito"):
        GenericFormAdapter().adapt(valid_payload)


@pytest.mark.parametrize("minor_field", [{"age": 17}, {"is_minor": True},
                                           {"birth_date": "2012-01-01"}])
def test_rejects_minors(valid_payload: dict, minor_field: dict) -> None:
    valid_payload.update(minor_field)
    with pytest.raises(ConsumerIngestionError, match="menores de idade"):
        GenericFormAdapter().adapt(valid_payload)


def test_rejects_nested_sensitive_data(valid_payload: dict) -> None:
    valid_payload["answers"] = {"profile": {"religion": "não deve entrar"}}
    with pytest.raises(ConsumerIngestionError, match="sensível"):
        GenericFormAdapter().adapt(valid_payload)


def test_rejects_platform_origin_mismatch(valid_payload: dict) -> None:
    with pytest.raises(ConsumerIngestionError, match="Origem incompatível"):
        normalize_consumer_payload(valid_payload, platform="meta", origin="tiktok_inbound")


def test_rejects_oversized_and_overdeep_payloads(valid_payload: dict) -> None:
    oversized = deepcopy(valid_payload)
    oversized["message"] = "x" * 70_000
    with pytest.raises(ConsumerIngestionError, match="64 KiB"):
        GenericFormAdapter().adapt(oversized)

    deep = deepcopy(valid_payload)
    deep["answers"] = {"a": {"b": {"c": {"d": {"e": {"f": {"g": "x"}}}}}}}
    with pytest.raises(ConsumerIngestionError, match="profundidade"):
        GenericFormAdapter().adapt(deep)


def test_requires_contact_identity_and_timezone(valid_payload: dict) -> None:
    valid_payload["email"] = ""
    valid_payload["captured_at"] = "2026-09-03T12:00:00"
    with pytest.raises(ConsumerIngestionError, match="fuso horário"):
        GenericFormAdapter().adapt(valid_payload)

    valid_payload["captured_at"] = "2026-09-03T12:00:00-03:00"
    with pytest.raises(ConsumerIngestionError, match="identidade social"):
        GenericFormAdapter().adapt(valid_payload)
