from app.consumers import (
    ConsumerIntelligenceService,
    ConsumerStatus,
)

CONSENT = {
    "granted": True,
    "channel": "instagram_dm",
    "purpose": "responder solicitação comercial",
    "source": "instagram lead form",
}


def _evidence(*fields: str) -> list[dict[str, object]]:
    return [
        {
            "field": field,
            "value": f"confirmed-{field}",
            "status": "CONFIRMED",
            "source_url": f"https://crm.test/{field}",
            "confidence": 0.9,
        }
        for field in fields
    ]


def test_consent_is_a_hard_gate_even_for_high_scores() -> None:
    room = ConsumerIntelligenceService().generate(
        {
            "name": "Ana",
            "signals": ["price_request"],
            "data_confidence_score": 95,
            **{f"{name}_score": 95 for name in (
                "fit", "need", "intent", "urgency", "capacity", "engagement"
            )},
        },
        evidence=_evidence("need", "intent", "urgency", "capacity"),
    )

    assert room.qualification.status == ConsumerStatus.BLOCKED
    assert not room.handoff.ready
    assert "consentimento" in room.next_action.casefold()


def test_likes_and_follows_never_become_sql() -> None:
    room = ConsumerIntelligenceService().generate(
        {
            "name": "Bia",
            "signals": ["like", "follow"],
            "data_confidence_score": 100,
            **{f"{name}_score": 100 for name in (
                "fit", "need", "intent", "urgency", "capacity", "engagement"
            )},
        },
        consent=CONSENT,
        evidence=_evidence("need", "intent", "urgency", "capacity"),
    )

    assert room.qualification.status == ConsumerStatus.NURTURE
    assert room.qualification.readiness <= 39
    assert "fraca" in room.inferences[0].value.casefold()


def test_explicit_intent_and_verified_criteria_create_ready_customer_room() -> None:
    room = ConsumerIntelligenceService().generate(
        {
            "id": "person-1",
            "name": "Carla",
            "platform": "instagram",
            "signals": ["inbound_dm", "asked_price"],
            "recommended_offer": "Plano Premium",
            "data_confidence_score": 90,
            "fit_score": 85,
            "need_score": 90,
            "intent_score": 95,
            "urgency_score": 75,
            "capacity_score": 70,
            "engagement_score": 80,
        },
        consent=CONSENT,
        evidence=_evidence("need", "intent", "urgency", "capacity"),
    )

    assert room.qualification.status == ConsumerStatus.SQL
    assert room.qualification.data_confidence == 90
    assert {item.name for item in room.qualification.dimensions} == {
        "fit", "need", "intent", "urgency", "capacity", "engagement"
    }
    assert room.handoff.ready
    assert room.handoff.recommended_offer == "Plano Premium"
    assert not room.unknowns


def test_unverified_claims_remain_unknown_and_do_not_raise_scores() -> None:
    room = ConsumerIntelligenceService().generate(
        {"name": "Dani", "signals": ["form_submitted"], "fit_score": 80},
        consent=CONSENT,
        evidence=[{
            "field": "budget", "value": "R$ 5.000", "status": "OBSERVED",
            "source_url": "https://social.test/post", "confidence": 0.95,
        }],
    )

    assert room.qualification.status == ConsumerStatus.RESEARCH
    assert not room.facts
    assert {claim.field for claim in room.unknowns} >= {"need", "intent", "urgency", "capacity"}
    assert all(claim.kind.value == "unknown" for claim in room.unknowns)
