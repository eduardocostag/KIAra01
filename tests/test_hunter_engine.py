from datetime import UTC, datetime, timedelta

from app.consumers.hunter_engine import (
    HunterEngine,
    IntentKind,
    IntentSignal,
    ProspectEvidence,
    Temperature,
)

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)


def test_product_brief_labels_inferred_icp_as_hypothesis():
    brief = HunterEngine().build_product_brief(product="Personal trainer",
        problem="dificuldade para emagrecer", region="Recife")
    assert brief.market == "B2C"
    assert len(brief.icp_hypotheses) == 2


def test_detect_intent_is_attributable_and_accent_insensitive():
    signals = HunterEngine().detect_intent(
        text="Preciso resolver um problema hoje. Quanto custa?", occurred_at=NOW,
        source="instagram://comment/123")
    assert {signal.kind for signal in signals} == {
        IntentKind.EXPLICIT_PROBLEM, IntentKind.DIRECT, IntentKind.TRIGGER,
    }
    assert all(signal.source == "instagram://comment/123" for signal in signals)


def test_score_is_explainable_and_recency_matters():
    recent = IntentSignal(IntentKind.EXPLICIT_PROBLEM, "Meu ar parou", NOW, "public://1")
    base = {"fit": 100, "capacity": 100, "contactability": 100,
            "information_quality": 100, "available_channels": ("email",)}
    decision = HunterEngine().evaluate(ProspectEvidence(**base, signals=(recent,)), now=NOW)
    assert decision.score.total == 95
    assert decision.temperature == Temperature.VERY_HOT
    old = IntentSignal(IntentKind.EXPLICIT_PROBLEM, "Meu ar parou",
                       NOW - timedelta(days=100), "public://1")
    assert HunterEngine().evaluate(ProspectEvidence(**base, signals=(old,)), now=NOW).score.total == 85


def test_instagram_cold_outreach_is_assisted_never_automated():
    signal = IntentSignal(IntentKind.DIRECT, "Procuro personal", NOW, "public://post")
    decision = HunterEngine().evaluate(ProspectEvidence(
        fit=80, signals=(signal,), available_channels=("instagram",),
        instagram_inbound=False, instagram_official_api=True), now=NOW)
    assert decision.route.primary == "instagram_assisted"
    assert decision.route.execution_mode == "fila_assistida"
    assert "não automatizar" in decision.next_action


def test_instagram_inbound_official_requires_human_approval():
    signal = IntentSignal(IntentKind.DIRECT, "Quanto custa?", NOW, "instagram://dm/1")
    decision = HunterEngine().evaluate(ProspectEvidence(
        fit=80, signals=(signal,), available_channels=("instagram",),
        instagram_inbound=True, instagram_official_api=True), now=NOW)
    assert decision.route.primary == "instagram"
    assert decision.route.execution_mode == "aprovação_humana"


def test_opt_out_zeroes_score_and_blocks_every_channel():
    decision = HunterEngine().evaluate(ProspectEvidence(
        fit=100, available_channels=("email", "instagram"), opted_out=True), now=NOW)
    assert decision.score.total == 0
    assert decision.temperature == Temperature.DISCARD
    assert decision.route.execution_mode == "bloqueado"
