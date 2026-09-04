from datetime import UTC, datetime

from app.consumers import GovernedHunterService
from app.consumers.hunter_engine import IntentKind, IntentSignal, ProspectEvidence
from app.privacy import HunterResearchRequest


def _request(**changes):
    values = {
        "subject_kind": "consumer",
        "source_is_public": True,
        "source_url": "https://instagram.com/example",
        "purpose": "commercial_research",
        "fields": frozenset({"business_handle", "public_business_signal", "source_url"}),
        "has_need_signal": True,
        "signal_age_days": 1,
    }
    values.update(changes)
    return HunterResearchRequest(**values)


def _evidence(*, inbound=False, opted_out=False):
    now = datetime(2026, 9, 4, tzinfo=UTC)
    return ProspectEvidence(
        fit=90,
        contactability=80,
        information_quality=80,
        signals=(IntentSignal(IntentKind.DIRECT, "Quanto custa?", now, "instagram://signal"),),
        available_channels=("instagram",),
        instagram_inbound=inbound,
        instagram_official_api=True,
        opted_out=opted_out,
    )


def test_public_b2c_profile_is_blocked_before_scoring_or_contact():
    result = GovernedHunterService().evaluate(_request(), _evidence())

    assert result.commercial is None
    assert result.allowed_action == "bloqueado_pela_privacidade"


def test_inbound_with_channel_consent_can_prepare_approved_route():
    result = GovernedHunterService().evaluate(
        _request(inbound_interaction=True, channel_consent=True),
        _evidence(inbound=True),
        now=datetime(2026, 9, 4, tzinfo=UTC),
    )

    assert result.commercial is not None
    assert result.commercial.route.execution_mode == "aprovação_humana"
    assert "aprovação humana" in result.allowed_action


def test_opt_out_stays_suppressed_even_with_consent_and_high_fit():
    result = GovernedHunterService().evaluate(
        _request(inbound_interaction=True, channel_consent=True, opted_out=True),
        _evidence(inbound=True, opted_out=True),
    )

    assert result.commercial is None
    assert result.allowed_action == "bloqueado_pela_privacidade"
