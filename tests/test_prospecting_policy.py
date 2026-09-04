from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from app.leads.policy import ProspectingMode, ProspectingPolicy, ProspectingPolicyEngine
from app.leads.suppression import SuppressionStore


def test_safe_defaults_block_automatic_but_allow_reviewed_contact(tmp_path) -> None:
    engine = ProspectingPolicyEngine(tmp_path / "policy.db")
    assert engine.policy.mode is ProspectingMode.ASSIST
    assert not engine.policy.allow_auto_send
    assert not engine.reserve("+55 51 99999-0000", automatic=True).allowed
    reviewed = engine.reserve("+55 51 99999-0000")
    assert reviewed.allowed
    assert reviewed.remaining_today == 19
    engine.close()


def test_opt_out_blocks_contact_without_persisting_raw_phone(tmp_path) -> None:
    path = tmp_path / "policy.db"
    suppressions = SuppressionStore(path)
    suppressions.suppress("+55 (51) 99999-0000", reason="pediu para não receber")
    engine = ProspectingPolicyEngine(path)
    assert not engine.reserve("5551999990000").allowed
    assert "5551999990000" not in path.read_bytes().decode("utf-8", errors="ignore")
    engine.close()
    suppressions.close()


def test_daily_limit_is_transactional_across_engine_instances(tmp_path) -> None:
    path = tmp_path / "policy.db"
    policy = ProspectingPolicy(daily_limit=5, cooldown=timedelta(0))
    engines = [ProspectingPolicyEngine(path, policy) for _ in range(5)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        decisions = list(pool.map(
            lambda index: engines[index % len(engines)].reserve(f"+555199999{index:04d}"),
            range(20),
        ))
    assert sum(item.allowed for item in decisions) == 5
    for engine in engines:
        engine.close()


def test_cooldown_survives_restart_and_cancel_releases_slot(tmp_path) -> None:
    path = tmp_path / "policy.db"
    policy = ProspectingPolicy(daily_limit=1, cooldown=timedelta(hours=24))
    first = ProspectingPolicyEngine(path, policy)
    instant = datetime(2026, 9, 2, 12, tzinfo=UTC)
    reserved = first.reserve("+5551999990001", now=instant)
    assert reserved.allowed
    assert first.complete(reserved.reservation_id, sent=False)
    assert first.reserve("+5551999990002", now=instant).allowed
    first.close()

    restarted = ProspectingPolicyEngine(path, ProspectingPolicy(daily_limit=2))
    assert not restarted.reserve("+5551999990002", now=instant + timedelta(hours=1)).allowed
    assert restarted.reserve("+5551999990003", now=instant + timedelta(hours=1)).allowed
    restarted.close()


def test_policy_fails_closed_for_invalid_identity_or_naive_time(tmp_path) -> None:
    engine = ProspectingPolicyEngine(tmp_path / "policy.db")
    assert not engine.reserve(" ").allowed
    naive = datetime(2026, 9, 2, tzinfo=UTC).replace(tzinfo=None)
    assert not engine.reserve("+5551999990000", now=naive).allowed
    engine.close()
