from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_STYLESHEET = """
QScrollArea#chatTranscript {
  background: #09111F;
  border: 0;
}
QScrollArea#chatTranscript > QWidget > QWidget { background: #09111F; }
QFrame#chatMessageCard {
  background: #101B2D;
  border: 1px solid #1C3150;
  border-radius: 11px;
}
QFrame#chatMessageCard[role="user"] {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4B63E8,stop:1 #7457EA);
  border-color: #7E78F3;
}
QFrame#chatMessageCard[role="assistant"] {
  background: #101B2D;
  border-color: #1C3150;
}
QFrame#chatMessageCard[role="notice"] {
  background: #282217;
  border-color: #6F5933;
}
QLabel#chatMessageAuthor { color: #BBAAFF; font-size: 10px; font-weight: 700; }
QFrame#chatMessageCard[role="user"] QLabel#chatMessageAuthor { color: #C8D3FF; }
QLabel#chatMessageTime { color: #8291AD; font-size: 10px; }
QLabel#chatMessageBody { color: #E8EEFA; font-size: 11px; }
QLabel#chatMessageAvatar {
  color: #FFFFFF; background: #6F4CE8; border-radius: 12px;
  font-size: 9px; font-weight: 700;
}
QFrame#chatMessageCard[role="user"] QLabel#chatMessageBody { color: #F7F9FF; }
QLabel#chatEmptyState { color: #8291AD; font-size: 12px; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #40577F; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def _role_for(author: str, kind: str) -> str:
    if kind == "notice":
        return "notice"
    normalized = author.strip().casefold()
    return "user" if normalized in {"você", "voce", "user", "usuário", "usuario"} else "assistant"


def _format_timestamp(value: object | None) -> str:
    if value is None:
        moment = datetime.now().astimezone()
    elif isinstance(value, datetime):
        moment = value
    else:
        raw = str(value).strip()
        try:
            moment = datetime.fromisoformat(raw)
        except ValueError:
            return raw
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return moment.strftime("%H:%M")


class ChatMessageCard(QFrame):
    """Accessible, width-aware presentation of one transcript message."""

    def __init__(
        self,
        author: str,
        text: str,
        *,
        timestamp: object | None = None,
        kind: str = "message",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, objectName="chatMessageCard")
        self.role = _role_for(author, kind)
        self.author = author.strip() or ("Você" if self.role == "user" else "Kiara")
        self.text = str(text)
        self.timestamp = _format_timestamp(timestamp)
        self.setProperty("role", self.role)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Mensagem de {self.author}, {self.timestamp}")
        self.setAccessibleDescription(self.text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 9)
        layout.setSpacing(4)
        metadata = QHBoxLayout()
        metadata.setContentsMargins(0, 0, 0, 0)
        metadata.setSpacing(10)

        self.author_label = QLabel(self.author, objectName="chatMessageAuthor")
        self.time_label = QLabel(self.timestamp, objectName="chatMessageTime")
        self.time_label.setAccessibleName(f"Horário: {self.timestamp}")
        metadata.addWidget(self.author_label)
        metadata.addStretch(1)
        metadata.addWidget(self.time_label)

        self.body_label = QLabel(self.text, objectName="chatMessageBody")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body_label.setTextFormat(Qt.TextFormat.PlainText)
        self.body_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.body_label.setAccessibleName(f"Conteúdo da mensagem de {self.author}")
        layout.addLayout(metadata)
        layout.addWidget(self.body_label)

    def set_bubble_width(self, width: int) -> None:
        maximum = max(220, width)
        preferred = 420 if self.role == "user" else 520
        self.setMinimumWidth(min(maximum, preferred))
        self.setMaximumWidth(maximum)


class ChatTranscript(QScrollArea):
    """Scrollable native-widget chat history with directional message cards.

    Integration contract: replace ``QTextBrowser`` calls with ``append_message``;
    ``clear`` and ``is_empty`` are available for conversation switching.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, objectName="chatTranscript")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Histórico da conversa")
        self.setAccessibleDescription("Mensagens recentes entre você e a Kiara")
        self.setStyleSheet(_STYLESHEET)

        self._content = QWidget(objectName="chatTranscriptContent")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(10)
        self._layout.addStretch(1)
        self.setWidget(self._content)
        self._cards: list[ChatMessageCard] = []
        self.maximum_messages = 500

        self._empty = QLabel(
            "Comece uma conversa com a Kiara.",
            self._content,
            objectName="chatEmptyState",
        )
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setAccessibleName("Nenhuma mensagem na conversa")
        self._layout.insertWidget(0, self._empty, 1)

    @property
    def cards(self) -> tuple[ChatMessageCard, ...]:
        return tuple(self._cards)

    def is_empty(self) -> bool:
        return not self._cards

    def append_message(
        self,
        author: str,
        text: str,
        *,
        timestamp: object | None = None,
        kind: str = "message",
    ) -> ChatMessageCard | None:
        clean = str(text).strip()
        if not clean:
            return None
        card = ChatMessageCard(author, clean, timestamp=timestamp, kind=kind, parent=self._content)
        row = QWidget(self._content, objectName="chatMessageRow")
        row.setProperty("role", card.role)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        avatar = QLabel("V" if card.role == "user" else "K", objectName="chatMessageAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(24, 24)
        if card.role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(card)
            row_layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
        else:
            row_layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(card)
            row_layout.addStretch(1)
        card._transcript_row = row  # Keep the row available for deterministic removal.
        self._layout.insertWidget(self._layout.count() - 1, row)
        self._cards.append(card)
        if len(self._cards) > self.maximum_messages:
            oldest = self._cards.pop(0)
            oldest_row = oldest._transcript_row
            self._layout.removeWidget(oldest_row)
            oldest_row.deleteLater()
        self._empty.hide()
        self._update_bubble_widths()
        QTimer.singleShot(0, self.scroll_to_bottom)
        return card

    def set_messages(self, messages: Iterable[Mapping[str, object]]) -> None:
        self.clear()
        for message in messages:
            self.append_message(
                str(message.get("author", "Kiara")),
                str(message.get("text", "")),
                timestamp=message.get("created_at"),
                kind=str(message.get("kind", "message")),
            )

    def clear(self) -> None:
        for card in self._cards:
            row = card._transcript_row
            self._layout.removeWidget(row)
            row.deleteLater()
        self._cards.clear()
        self._empty.show()
        self.verticalScrollBar().setValue(0)

    def scroll_to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        self._update_bubble_widths()

    def _update_bubble_widths(self) -> None:
        available = max(320, self.viewport().width() - 48)
        maximum = min(680, int(available * 0.70))
        for card in self._cards:
            card.set_bubble_width(maximum)
