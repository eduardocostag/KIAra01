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
        assert window.sidebar.accessibleName() == "Navegação principal da Kiara"
        initial_conversations = window.conversation_list.count()
        assert initial_conversations >= 1
        assert window.workspace_stack.count() == 3
        assert window.nav_consumers.accessibleName() == "Abrir inteligência de consumidores"
        assert window.lead_table.accessibleName() == "Pipeline de leads"
        assert window.stage_editor.accessibleName() == "Etapa comercial do lead"
        assert window.interaction_outcome.accessibleName() == "Resultado do contato"
        assert window.sidebar.isHidden()
        window.resize(680, 620)
        app.processEvents()
        assert window.sidebar.isHidden()
        window.workspace_stack.setCurrentIndex(0)
        window._open_consumers()
        assert window.workspace_stack.currentIndex() == 2
        assert window.nav_consumers.isChecked()
        window._append_message("Você", "teste do usuário")
        window._append_message("Kiara", "teste da assistente")
        assert [card.text for card in window.transcript.cards[-2:]] == [
            "teste do usuário", "teste da assistente"
        ]
        assert [card.role for card in window.transcript.cards[-2:]] == ["user", "assistant"]
        window._new_conversation()
        assert window.conversation_list.count() == initial_conversations + 1
        assert window.transcript.is_empty()
        monkeypatch.setattr(
            "app.ui.desktop.QMessageBox.question",
            lambda *args, **kwargs: (
                __import__(
                    "PySide6.QtWidgets", fromlist=["QMessageBox"]
                ).QMessageBox.StandardButton.Yes
            ),
        )
        window._delete_selected_conversation()
        assert window.conversation_list.count() == initial_conversations
        assert window._conversation_store.get(window._active_conversation_id) is not None
    finally:
        window.shutdown()
        window.deleteLater()


def test_submit_is_atomic_and_busy_status_does_not_reflow(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from app.ui.desktop import KiaraWindow

    class Core:
        def start_background(self):
            return None

        def stop_background(self):
            return None

        async def handle(self, message):
            # Keep the request active long enough to exercise the synchronous
            # submission lock independently of scheduler timing.
            await __import__("asyncio").sleep(0.2)
            return message

    class Kill:
        def trigger(self):
            return None

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("app.ui.desktop.QSystemTrayIcon.isSystemTrayAvailable", lambda: False)
    window = KiaraWindow(Core(), Kill())
    submitted: list[str] = []
    window.submit_requested.connect(submitted.append)
    try:
        window.show()
        app.processEvents()
        window.input.setText("busque empresas")
        status_geometry = window.status.geometry()
        window.submit_message()
        window.submit_message()
        assert submitted == ["busque empresas"]
        assert not window.send.isEnabled()
        window._on_delta("resposta parcial muito longa " * 50)
        assert window.status.text() == "Gerando resposta…"
        assert window.status.geometry().height() == status_geometry.height()
        window._set_busy(False)
        assert window.send.isEnabled()
        assert window.input.isEnabled()
    finally:
        window.shutdown()
        window.deleteLater()


def test_copilot_first_shell_shows_navigation_and_context_on_desktop(monkeypatch):
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
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        assert window.workspace_stack.currentIndex() == 1
        assert window.sidebar.isVisible()
        assert window.context_panel.isVisible()
        assert window.context_panel.accessibleName() == "Contexto comercial da conversa"
        assert window.transcript.isVisible()
        assert window.input.isVisible()
        window.resize(900, 680)
        app.processEvents()
        assert window.sidebar.isHidden()
        assert window.context_panel.isHidden()
        assert window.input.width() > 200
    finally:
        window.shutdown()
        window.deleteLater()
