from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qt_app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_transcript_aligns_roles_and_exposes_accessible_cards(qt_app):
    from app.ui.chat_widgets import ChatTranscript

    transcript = ChatTranscript()
    user = transcript.append_message("Você", "Quero buscar contas enterprise", timestamp="2026-09-02T14:05:00")
    assistant = transcript.append_message("Kiara", "Vou qualificar as melhores contas.", timestamp="2026-09-02T14:06:00")
    qt_app.processEvents()

    assert [card.role for card in transcript.cards] == ["user", "assistant"]
    assert user is not None and user._transcript_row.layout().itemAt(0).spacerItem() is not None
    assert assistant is not None and assistant._transcript_row.layout().itemAt(1).widget() is assistant
    assert user.accessibleName() == "Mensagem de Você, 14:05"
    assert assistant.accessibleDescription() == "Vou qualificar as melhores contas."
    assert user.body_label.wordWrap()
    assert user.body_label.textFormat().name == "PlainText"


def test_transcript_loads_history_ignores_empty_and_clears(qt_app):
    from app.ui.chat_widgets import ChatTranscript

    transcript = ChatTranscript()
    transcript.set_messages(
        [
            {"author": "Você", "text": "Primeira", "created_at": "2026-09-02T10:20:00"},
            {"author": "Kiara", "text": "Segunda", "created_at": "2026-09-02T10:21:00"},
            {"author": "Kiara", "text": "  "},
        ]
    )
    qt_app.processEvents()

    assert [card.text for card in transcript.cards] == ["Primeira", "Segunda"]
    assert not transcript.is_empty()
    transcript.clear()
    qt_app.processEvents()
    assert transcript.is_empty()
    assert transcript._empty.isVisibleTo(transcript._content)


def test_transcript_wraps_and_limits_bubbles_on_wide_layout(qt_app):
    from app.ui.chat_widgets import ChatTranscript

    transcript = ChatTranscript()
    transcript.resize(1200, 500)
    card = transcript.append_message("Kiara", "Texto longo " * 100)
    transcript.show()
    qt_app.processEvents()

    assert card is not None
    assert card.maximumWidth() <= 720
    assert card.maximumWidth() >= 260
    assert transcript.horizontalScrollBarPolicy().name == "ScrollBarAlwaysOff"
