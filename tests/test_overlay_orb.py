from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.overlay import StatusOverlay


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_orb_is_accessible_always_on_top_and_expands() -> None:
    _app()
    overlay = StatusOverlay()
    try:
        assert overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        assert overlay.accessibleName()
        assert "abrir" in overlay.accessibleDescription().casefold()
        assert not overlay.is_expanded()
        overlay.set_expanded(True)
        assert overlay.is_expanded()
        overlay.set_state("Pensando")
        assert "pensando" in overlay.accessibleDescription().casefold()
        assert "pensando" in overlay.accessibleDescription()
    finally:
        overlay.close()


def test_single_click_opens_and_closes_quick_chat_immediately() -> None:
    _app()
    activations: list[str] = []
    overlay = StatusOverlay(lambda: activations.append("activate"))
    try:
        overlay.show()
        orb_center = overlay.orb.geometry().center()
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=orb_center)
        assert overlay.is_expanded()
        QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=overlay.orb.geometry().center())
        assert not overlay.is_expanded()
        assert activations == []
        QApplication.sendEvent(overlay, QFocusEvent(QEvent.Type.FocusIn))
        assert overlay.orb.property("keyboardFocus") is True
        overlay.set_expanded(False)
        QTest.keyClick(overlay, Qt.Key.Key_Return)
        assert overlay.is_expanded()
    finally:
        overlay.close()


def test_clicking_orb_widget_opens_quick_chat() -> None:
    _app()
    overlay = StatusOverlay()
    try:
        overlay.show()
        QTest.mouseClick(overlay.orb, Qt.MouseButton.LeftButton)
        assert overlay.is_expanded()
    finally:
        overlay.close()


def test_central_button_requests_main_window_and_double_click_does_not() -> None:
    _app()
    requested: list[str] = []
    overlay = StatusOverlay()
    overlay.main_window_requested.connect(lambda: requested.append("main"))
    try:
        overlay.show()
        QTest.mouseDClick(overlay, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        QApplication.processEvents()
        assert requested == []
        assert not overlay.is_expanded()
        overlay.set_expanded(True)
        overlay.open_central_button.click()
        assert requested == ["main"]
        assert not overlay.is_expanded()
    finally:
        overlay.close()


def test_quick_message_and_response_contract() -> None:
    _app()
    messages: list[str] = []
    voice_requests: list[str] = []
    overlay = StatusOverlay()
    overlay.quick_message_submitted.connect(messages.append)
    overlay.voice_requested.connect(lambda: voice_requests.append("voice"))
    try:
        overlay.show()
        overlay.set_expanded(True)
        QApplication.processEvents()
        assert "aberta" in overlay.accessibleDescription().casefold()
        assert overlay.quick_input.hasFocus()
        assert (
            overlay.response_label.textInteractionFlags()
            & Qt.TextInteractionFlag.TextSelectableByMouse
        )
        overlay.quick_input.setText("  Olá, Kiara  ")
        QTest.keyClick(overlay.quick_input, Qt.Key.Key_Return)
        assert messages == ["Olá, Kiara"]
        assert "pensando" in overlay.response_label.text().casefold()
        overlay.show_response("Olá! Tudo bem?")
        assert overlay.response_label.text() == "Olá! Tudo bem?"
        overlay.show_error("sem conexão")
        assert "sem conexão" in overlay.response_label.text()
        overlay.set_listening(True)
        assert "ouvindo" in overlay.accessibleDescription().casefold()
        assert overlay.orb.property("listening") is True
        overlay.voice_button.click()
        assert voice_requests == ["voice"]
        QTest.keyClick(overlay.quick_input, Qt.Key.Key_Escape)
        assert not overlay.is_expanded()
        assert not overlay.hasFocus()
        assert overlay.focusPolicy() == Qt.FocusPolicy.NoFocus
    finally:
        overlay.close()


def test_drag_does_not_trigger_quick_chat_or_main_window() -> None:
    _app()
    requested: list[str] = []
    overlay = StatusOverlay()
    overlay.main_window_requested.connect(lambda: requested.append("main"))
    try:
        overlay.show()
        start = QPoint(20, 20)
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(overlay, QPoint(45, 45), delay=10)
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(45, 45))
        assert not overlay.is_expanded()
        assert requested == []
    finally:
        overlay.close()


def test_hidden_orb_does_not_accept_input() -> None:
    _app()
    overlay = StatusOverlay()
    try:
        overlay.show_discreetly()
        assert overlay.isVisible()
        overlay.hide()
        assert not overlay.isVisible()
        assert not overlay.isActiveWindow()
    finally:
        overlay.close()


def test_programmatic_response_never_focuses_orb_or_quick_input() -> None:
    app = _app()
    overlay = StatusOverlay()
    try:
        overlay.show_discreetly()
        overlay.show_response("Resposta concluída")
        app.processEvents()

        assert overlay.is_expanded()
        assert overlay.focusPolicy() == Qt.FocusPolicy.NoFocus
        assert not overlay.quick_input.hasFocus()
        assert not overlay.hasFocus()
    finally:
        overlay.close()


def test_quick_chat_stays_inside_screen_when_expanded_from_right_edge() -> None:
    app = _app()
    overlay = StatusOverlay()
    try:
        overlay.show_discreetly()
        app.processEvents()
        available = overlay.screen().geometry()
        overlay.move(
            available.right() - overlay.width() + 1, available.bottom() - overlay.height() + 1
        )
        overlay.set_expanded(True)
        app.processEvents()
        assert available.contains(overlay.geometry())
        assert overlay.quick_panel.isVisible()
        overlay.set_expanded(False)
        app.processEvents()
        assert overlay.width() < 140
        left = overlay._clamped_position(QPoint(available.left() - 500, available.top()))
        overlay.move(left)
        app.processEvents()
        assert overlay.geometry().left() == available.left()
        assert overlay.orb.mapToGlobal(QPoint(0, 0)).x() <= available.left() + 10
    finally:
        overlay.close()


def test_idle_orb_is_static_and_timer_runs_only_for_active_states() -> None:
    _app()
    overlay = StatusOverlay()
    assert overlay.orb._state == "pronta"
    assert overlay.orb._timer.isActive() is False

    overlay.set_state("pensando")
    assert overlay.orb._timer.isActive() is True

    overlay.set_state("pronta")
    assert overlay.orb._timer.isActive() is False
    assert overlay.orb._phase == 0.0
    overlay.close()
