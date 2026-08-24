from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_sidebar_routes_to_existing_panels_and_chat_bubbles_are_directional(monkeypatch):
    pytest.importorskip("PySide6")
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
        window.show()
        app.processEvents()
        assert [button.accessibleName() for button in window.nav_buttons] == [
            "Conversa",
            "Automações",
            "Memória",
            "Agentes",
        ]
        window.nav_buttons[2].click()
        assert window.tabs.currentIndex() == 2
        assert not window.sidebar.isHidden()
        assert window.tabs.tabBar().isHidden()
        window.resize(680, 620)
        app.processEvents()
        assert window.sidebar.isHidden()
        assert not window.tabs.tabBar().isHidden()
        window.tabs.setCurrentIndex(0)
        window._append_message("Você", "teste do usuário")
        window._append_message("Kiara", "teste da assistente")
        markup = window.transcript.toHtml()
        assert "teste do usuário" in markup
        assert "teste da assistente" in markup
        assert 'align="right"' in markup
        assert markup.index("teste do usuário") < markup.index("teste da assistente")
    finally:
        window.shutdown()
        window.deleteLater()
