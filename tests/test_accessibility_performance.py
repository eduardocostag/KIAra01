from __future__ import annotations

import asyncio
import os

import pytest

from app.core.event_bus import EventBus
from app.models import ScreenContext
from app.observability.metrics import MetricsRegistry
from app.perception.screen import PerceptionOptions, ScreenPerception
from app.perception.windows import WindowSnapshot


def test_metrics_memory_is_bounded():
    metrics = MetricsRegistry()
    for value in range(2_000):
        metrics.observe("latency", value)
    summary = metrics.summary("latency")
    assert summary.count == 1_000
    assert summary.maximum_ms == 1_999


@pytest.mark.asyncio
async def test_screen_polling_has_minimum_interval_and_stops_promptly():
    calls = 0

    def inspect():
        nonlocal calls
        calls += 1
        return WindowSnapshot(ScreenContext(window_title="same"))

    perception = ScreenPerception(
        EventBus(), PerceptionOptions(poll_interval_seconds=0), inspector=inspect
    )
    await perception.start()
    await asyncio.sleep(0.03)
    await asyncio.wait_for(perception.stop(), timeout=0.1)
    assert calls <= 1


def test_ui_accessibility_names_shortcuts_and_bounded_history(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.ui.desktop import KiaraWindow

    class Core:
        def start_background(self):
            return None

        def stop_background(self):
            return None

        async def handle(self, message):
            return message

    class Kill:
        def trigger(self):
            return None

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("app.ui.desktop.QSystemTrayIcon.isSystemTrayAvailable", lambda: False)
    window = KiaraWindow(Core(), Kill())
    try:
        widgets = (window.transcript, window.status, window.input, window.send, window.talk, window.stop)
        assert all(widget.accessibleName().strip() for widget in widgets)
        assert window.send.shortcut().toString() == "Alt+E"
        assert window.talk.shortcut().toString() == "Alt+F"
        assert window.stop.shortcut().toString() == "Esc"
        assert window.stop.isHidden()
        window._set_busy(True)
        assert not window.stop.isHidden()
        assert window.stop.focusPolicy() != Qt.FocusPolicy.NoFocus
        window._set_busy(False)
        assert window.stop.isHidden()
        window._set_voice_state("Ouvindo…")
        assert not window.stop.isHidden()
        window._set_voice_state("Pronta")
        assert window.stop.isHidden()
        # The full SDR workspace needs a real desktop minimum; accepting 440px
        # compressed the inspector controls until they overlapped.
        assert window.minimumWidth() == 900
        assert window.minimumHeight() == 680
        assert window.workspace_stack.count() == 3
        assert "desativado" in window.conversation.text().casefold()
        window.conversation.setChecked(True)
        assert "ativado" in window.conversation.text().casefold()
        assert "ativado" in window.conversation.accessibleName().casefold()
        palette = window.input.palette()
        foreground = palette.color(palette.ColorRole.Text)
        background = palette.color(palette.ColorRole.Base)

        def luminance(color):
            channels = [color.redF(), color.greenF(), color.blueF()]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
        assert (lighter + 0.05) / (darker + 0.05) >= 4.5
        window.show()
        app.processEvents()
        # Offscreen Qt cannot reliably model Windows foreground activation when
        # tool overlays from earlier tests still exist. Verify keyboard focus is
        # enabled; interactive focus transfer is covered by the overlay tests.
        assert window.input.focusPolicy() != Qt.FocusPolicy.NoFocus
        assert not window.sidebar.isVisible()
        assert window.rail.isVisible()
        window.workspace_stack.setCurrentIndex(1)
        app.processEvents()
        assert not window.sidebar.isVisible()
        assert window.rail.isVisible()
        window.workspace_stack.setCurrentIndex(0)
        window.resize(900, 600)
        app.processEvents()
        assert not window.sidebar.isVisible()
        assert window.rail.isVisible()
        for index in range(510):
            window.transcript.append_message("Kiara", f"linha {index}")
        assert len(window.transcript.cards) <= 500
    finally:
        window.shutdown()
        window.deleteLater()
