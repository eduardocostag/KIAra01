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
        assert window.sidebar.accessibleName() == "Conversas salvas da Kiara"
        initial_conversations = window.conversation_list.count()
        assert initial_conversations >= 1
        assert window.tabs.count() == 1
        assert window.tabs.tabText(0) == "Conversa"
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
        window._new_conversation()
        assert window.conversation_list.count() == initial_conversations + 1
        assert window.transcript.document().isEmpty()
    finally:
        window.shutdown()
        window.deleteLater()
