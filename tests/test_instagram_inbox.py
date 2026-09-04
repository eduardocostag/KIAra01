from __future__ import annotations

import pytest


def _prepared(gate):
    gate.ingest("ig:event-ui", "recipient-123", "Quero saber o preco")
    return gate.create_draft("ig:event-ui", "Posso entender melhor o que voce procura?")


def test_inbox_approves_draft_without_sending(tmp_path, monkeypatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.automation.instagram_governance import InstagramDMGovernance
    from app.security.kill_switch import KillSwitch
    from app.ui.instagram_inbox import InstagramInbox

    app = QApplication.instance() or QApplication([])
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    action_id = _prepared(gate)
    panel = InstagramInbox(
        gate,
        KillSwitch(),
        actor_provider=lambda: "operadora@cliente",
        configuration={"webhook_configured": True, "credentials_configured": True},
    )

    assert "Segredos ocultos" in panel.configuration_status.text()
    assert panel.table.rowCount() == 1
    panel.approve_button.click()
    assert gate.get(action_id).status == "approved"
    assert gate.get(action_id).attempts == 0
    assert "recipient-123" not in panel.detail.text()
    panel.close()
    gate.close()
    app.processEvents()


def test_inbox_reflects_global_kill_switch_and_blocks_actions(tmp_path, monkeypatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.automation.instagram_governance import InstagramDMGovernance
    from app.security.kill_switch import KillSwitch
    from app.ui.instagram_inbox import InstagramInbox

    app = QApplication.instance() or QApplication([])
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    action_id = _prepared(gate)
    kill_switch = KillSwitch()
    kill_switch.trigger()
    panel = InstagramInbox(gate, kill_switch, actor_provider=lambda: "humano")

    assert "PARADA GLOBAL ATIVA" in panel.safety_status.text()
    assert panel.approve_button.isEnabled() is False
    assert panel.block_button.isEnabled() is False
    assert gate.get(action_id).status == "pending_approval"
    panel.close()
    gate.close()
    app.processEvents()


def test_inbox_operator_can_block_draft(tmp_path, monkeypatch) -> None:
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.automation.instagram_governance import InstagramDMGovernance
    from app.security.kill_switch import KillSwitch
    from app.ui.instagram_inbox import InstagramInbox

    app = QApplication.instance() or QApplication([])
    gate = InstagramDMGovernance(tmp_path / "instagram.db")
    action_id = _prepared(gate)
    panel = InstagramInbox(gate, KillSwitch(), actor_provider=lambda: "humano")
    panel.block_button.click()

    assert gate.get(action_id).status == "blocked_by_operator"
    panel.close()
    gate.close()
    app.processEvents()
