from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.automation.instagram_governance import InstagramDMGovernance


def prepared(gate: InstagramDMGovernance, suffix: str = "1") -> str:
    event = f"evt-{suffix}"
    assert gate.ingest(event, f"cliente{suffix}", "Quero saber mais") == "accepted"
    action = gate.create_draft(event, "Olá! Posso fazer algumas perguntas?")
    assert gate.approve(action, actor="operador-1")
    return action


def test_fail_closed_requires_human_approval_and_kill_switch(tmp_path) -> None:
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    event = "evt-1"
    gate.ingest(event, "@cliente", "Tenho interesse")
    action = gate.create_draft(event, "Olá!")
    assert not gate.approve(action, actor="kiara")
    assert gate.claim_delivery(action) is None
    assert gate.approve(action, actor="humano")
    assert gate.claim_delivery(action) is None
    gate.set_enabled(True, actor="admin")
    assert gate.claim_delivery(action).status == "sending"
    gate.close()


def test_operator_can_list_and_block_without_delivery(tmp_path) -> None:
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    gate.ingest("evt-block", "client-block", "Quero saber mais")
    action_id = gate.create_draft("evt-block", "Posso ajudar?")

    assert gate.is_enabled() is False
    assert [item.id for item in gate.list_actions(status="pending_approval")] == [action_id]
    assert gate.block(action_id, actor="operadora@cliente") is True
    assert gate.get(action_id).status == "blocked_by_operator"
    assert gate.claim_delivery(action_id) is None
    gate.close()


def test_block_requires_named_human_actor(tmp_path) -> None:
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    gate.ingest("evt-actor", "client-actor", "Quero saber mais")
    action_id = gate.create_draft("evt-actor", "Posso ajudar?")

    with pytest.raises(ValueError, match="ator humano"):
        gate.block(action_id, actor="kiara")
    assert gate.get(action_id).status == "pending_approval"
    gate.close()


def test_event_and_delivery_are_idempotent_under_concurrency(tmp_path) -> None:
    path = tmp_path / "instagram.db"
    first, second = InstagramDMGovernance(path), InstagramDMGovernance(path)
    action = prepared(first)
    first.set_enabled(True, actor="admin")
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda gate: gate.claim_delivery(action), (first, second)))
    assert sum(claim is not None for claim in claims) == 1
    assert first.create_draft("evt-1", "texto diferente") == action
    first.close()
    second.close()


def test_opt_out_cancels_even_after_approval(tmp_path) -> None:
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    action = prepared(gate)
    assert gate.ingest("evt-optout", "cliente1", "não quero") == "opt_out"
    gate.set_enabled(True, actor="admin")
    assert gate.claim_delivery(action) is None
    assert gate.get(action).status == "cancelled_opt_out"
    gate.close()


def test_bounded_retry_with_backoff(tmp_path) -> None:
    gate = InstagramDMGovernance(tmp_path / "instagram.db", max_attempts=2)
    action = prepared(gate)
    gate.set_enabled(True, actor="admin")
    initial = datetime.now(UTC)
    assert gate.claim_delivery(action, now=initial)
    assert gate.finish_delivery(action, success=False, retryable=True) == "retry_wait"
    assert gate.claim_delivery(action, now=initial + timedelta(seconds=10)) is None
    assert gate.claim_delivery(action, now=initial + timedelta(minutes=2))
    assert gate.finish_delivery(action, success=False, retryable=True) == "failed"
    assert gate.claim_delivery(action, now=initial + timedelta(minutes=3)) is None
    gate.close()


def test_stale_approval_expires_fail_closed(tmp_path) -> None:
    gate = InstagramDMGovernance(
        tmp_path / "instagram.db", approval_ttl=timedelta(microseconds=1)
    )
    action = prepared(gate)
    gate.set_enabled(True, actor="admin")
    assert gate.claim_delivery(action, now=datetime.now(UTC) + timedelta(seconds=1)) is None
    assert gate.get(action).status == "approval_expired"
    gate.close()
