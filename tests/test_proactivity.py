from datetime import UTC, datetime, timedelta

from app.proactivity import ProactivityLevel, ProactivityPolicy


def test_low_only_allows_important_notice_and_applies_cooldown():
    now = datetime.now(UTC)
    policy = ProactivityPolicy(ProactivityLevel.LOW)
    assert not policy.should_notify(importance=0.5, now=now)
    assert policy.should_notify(importance=0.95, now=now)
    assert not policy.should_notify(importance=1.0, now=now + timedelta(minutes=1))


def test_off_never_notifies():
    assert not ProactivityPolicy(ProactivityLevel.OFF).should_notify(importance=1.0)
