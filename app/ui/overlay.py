from __future__ import annotations

import math
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, QLineF, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAccessible,
    QAccessibleEvent,
    QColor,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _asset_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "app" / "ui" / "assets" / name


class AnimatedOrb(QWidget):
    """Orbe de vidro animado, com movimento distinto por estado."""

    _LOGICAL_SIZE = 92
    _DISPLAY_SIZE = 82

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(self._DISPLAY_SIZE, self._DISPLAY_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setProperty("listening", False)
        self.setProperty("keyboardFocus", False)
        self._state = "pronta"
        self._phase = 0.0
        self._image = QPixmap(str(_asset_path("kiara-orb-v2.png"))).scaled(
            84,
            84,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def set_visual_state(self, state: str) -> None:
        self._state = state.casefold()
        self.update()

    def _advance(self) -> None:
        speeds = {"pensando": 0.16, "falando": 0.24, "ouvindo": 0.12}
        self._phase = (self._phase + speeds.get(self._state, 0.045)) % (math.tau * 4)
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale_factor = self._DISPLAY_SIZE / self._LOGICAL_SIZE
        painter.scale(scale_factor, scale_factor)
        active = self._state in {"pensando", "falando", "ouvindo", "ocupada"}
        pulse = math.sin(self._phase)
        scale = 1.0 + (0.075 if active else 0.025) * pulse
        diameter = 76 * scale
        orb_rect = QRectF((92 - diameter) / 2 - 3, (86 - diameter) / 2, diameter, diameter)

        # HUD tecnológico contínuo: arcos contrarrotativos e partículas.
        ring_alpha = int((95 if active else 54) + 35 * (pulse + 1) / 2)
        outer = orb_rect.adjusted(-4, -4, 4, 4)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(58, 255, 236, ring_alpha), 1.45))
        start = int((self._phase * 78) % 360 * 16)
        for offset in (0, 120, 240):
            painter.drawArc(outer, start + offset * 16, 48 * 16)
        painter.setPen(QPen(QColor(58, 188, 255, max(35, ring_alpha - 22)), 1.0))
        inner_ring = orb_rect.adjusted(2, 2, -2, -2)
        reverse = int((-self._phase * 52) % 360 * 16)
        for offset in (25, 205):
            painter.drawArc(inner_ring, reverse + offset * 16, 92 * 16)

        orbit = self._phase * (1.55 if self._state == "pensando" else 0.92)
        particle_count = 5 if active else 3
        for index in range(particle_count):
            angle = orbit + index * math.tau / particle_count
            radius = 39 + 1.5 * math.sin(self._phase * 1.7 + index)
            x = 43 + math.cos(angle) * radius
            y = 41 + math.sin(angle) * radius
            alpha = 225 if index == 0 else 105 + index * 18
            size = 4.5 if index == 0 else 2.7
            painter.setBrush(QColor(91, 255, 238, alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(x - size / 2, y - size / 2, size, size))

        painter.save()
        center = orb_rect.center()
        painter.translate(center)
        if self._state in {"pensando", "ocupada"}:
            painter.rotate(math.sin(self._phase * 0.55) * 4.5)
        painter.translate(-center)
        painter.drawPixmap(orb_rect, self._image, QRectF(self._image.rect()))
        painter.restore()

        # Linha de varredura interna, lenta em repouso e rápida durante atividade.
        scan_progress = (math.sin(self._phase * (1.4 if active else 0.75)) + 1) / 2
        scan_y = orb_rect.top() + 8 + scan_progress * max(1, orb_rect.height() - 16)
        painter.save()
        painter.setClipPath(self._ellipse_path(orb_rect.adjusted(5, 5, -5, -5)))
        painter.setPen(QPen(QColor(93, 255, 239, 80 if active else 42), 1.2))
        painter.drawLine(QLineF(orb_rect.left() + 10, scan_y, orb_rect.right() - 10, scan_y))
        painter.restore()

        if self._state == "falando":
            painter.setPen(QPen(QColor(93, 255, 239, 180), 2.0))
            for index in range(3):
                height = 5 + abs(math.sin(self._phase + index * 0.8)) * 11
                x = 35 + index * 8
                painter.drawLine(QLineF(x, 43 - height / 2, x, 43 + height / 2))
        elif self._state == "ouvindo":
            painter.setPen(QPen(QColor(116, 255, 239, 150), 1.6))
            for index in range(2):
                radius = 34 + index * 4 + 2 * pulse
                painter.drawArc(QRectF(43 - radius, 43 - radius, radius * 2, radius * 2), -55 * 16, 110 * 16)

    @staticmethod
    def _ellipse_path(rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(rect)
        return path


class MicrophoneButton(QPushButton):
    """Botão com ícone de microfone desenhado, independente de fontes/emoji."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#eaffff") if self.isEnabled() else QColor("#668087")
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = self.width() / 2
        cy = self.height() / 2 - 1
        painter.drawRoundedRect(QRectF(cx - 3.5, cy - 7, 7, 12), 3.5, 3.5)
        painter.drawArc(QRectF(cx - 7, cy - 3, 14, 12), 180 * 16, 180 * 16)
        painter.drawLine(QLineF(cx, cy + 9, cx, cy + 13))
        painter.drawLine(QLineF(cx - 4, cy + 13, cx + 4, cy + 13))


class CentralButton(QPushButton):
    """Botão de expansão com ícone vetorial de alto contraste."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#ffffff") if self.isEnabled() else QColor("#668087")
        painter.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        left, top, right, bottom = 9.0, 9.0, self.width() - 9.0, self.height() - 9.0
        painter.drawLine(QLineF(left, bottom, right, top))
        painter.drawLine(QLineF(right - 6, top, right, top))
        painter.drawLine(QLineF(right, top, right, top + 6))
        painter.drawLine(QLineF(left, bottom - 5, left, bottom))
        painter.drawLine(QLineF(left, bottom, left + 5, bottom))


class StatusOverlay(QWidget):
    """Orbe sempre disponível com conversa rápida, sem acesso privilegiado."""

    activation_requested = Signal()  # compatibilidade com desktop.py
    main_window_requested = Signal()
    quick_message_submitted = Signal(str)
    voice_requested = Signal()
    _DRAG_THRESHOLD = 6

    def __init__(self, on_activation_requested: Callable[[], None] | None = None) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("statusOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Orbe da Kiara")
        self._expanded = False
        self._state = "pronta"
        self._listening = False
        self._press_global: QPoint | None = None
        self._window_at_press: QPoint | None = None
        self._dragged = False
        self._suppress_release = False
        self._response_timer = QTimer(self)
        self._response_timer.setSingleShot(True)
        self._response_timer.timeout.connect(self._expire_response)

        self.orb = AnimatedOrb()
        self.orb.setObjectName("kiaraOrb")
        self.orb.setProperty("keyboardFocus", False)
        self.quick_panel = QWidget()
        self.quick_panel.setObjectName("quickPanel")
        panel = QVBoxLayout(self.quick_panel)
        panel.setContentsMargins(12, 10, 12, 12)
        panel.setSpacing(8)
        self.response_label = QLabel("Como posso ajudar você?")
        self.response_label.setObjectName("quickResponse")
        self.response_label.setWordWrap(True)
        self.response_label.setMinimumWidth(270)
        self.response_label.setMaximumWidth(360)
        self.response_label.setAccessibleName("Resposta da Kiara")
        row = QHBoxLayout()
        self.quick_input = QLineEdit()
        self.quick_input.setObjectName("quickInput")
        self.quick_input.setPlaceholderText("Converse com a Kiara…")
        self.quick_input.setAccessibleName("Mensagem rápida para a Kiara")
        self.quick_input.setAccessibleDescription(
            "Digite uma mensagem e pressione Enter. Pressione Escape para fechar."
        )
        self.quick_input.installEventFilter(self)
        self.quick_input.returnPressed.connect(self._submit_quick_message)
        row.addWidget(self.quick_input, 1)
        panel_header = QHBoxLayout()
        panel_header.addStretch(1)
        self.open_central_button = CentralButton("")
        self.open_central_button.setObjectName("openCentral")
        self.open_central_button.setFixedSize(34, 34)
        self.open_central_button.setAccessibleName("Abrir central completa da Kiara")
        self.open_central_button.setToolTip("Abrir central completa")
        self.open_central_button.clicked.connect(self._request_main_window)
        panel_header.addWidget(self.open_central_button)
        self.voice_button = MicrophoneButton("")
        self.voice_button.setObjectName("quickVoice")
        self.voice_button.setFixedSize(34, 34)
        self.voice_button.setAccessibleName("Falar com a Kiara")
        self.voice_button.setToolTip("Falar com a Kiara")
        self.voice_button.clicked.connect(self.voice_requested.emit)
        row.addWidget(self.voice_button)
        panel.addLayout(panel_header)
        panel.addWidget(self.response_label)
        panel.addLayout(row)
        self.quick_panel.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(5)
        layout.addWidget(self.quick_panel, 0, Qt.AlignmentFlag.AlignRight)
        orb_row = QHBoxLayout()
        orb_row.addStretch(1)
        orb_row.addWidget(self.orb)
        layout.addLayout(orb_row)
        self.setStyleSheet(self._style_sheet())
        self._update_accessibility()
        self.adjustSize()
        if on_activation_requested is not None:
            self.activation_requested.connect(on_activation_requested)

    @staticmethod
    def _style_sheet() -> str:
        return """
        #statusOverlay { background: transparent; }
        #quickPanel { background-color:rgba(4,20,28,248); border:1px solid rgba(56,221,235,170); border-radius:16px; }
        #quickResponse { color:#e8fbff; font-size:13px; padding:3px; }
        #quickInput { color:#efffff; background:rgba(12,38,49,245); border:1px solid #257b87; border-radius:10px; padding:8px; }
        #quickInput:focus { border:1px solid #63fff2; }
        #quickVoice { background:#087c83; border:1px solid #43e1df; border-radius:17px; }
        #quickVoice:hover, #quickVoice:focus { background:#0aa1a5; border:2px solid #fff; }
        #openCentral { background:#087c83; border:2px solid #63fff2; border-radius:10px; }
        #openCentral:hover, #openCentral:focus { background:#0db1b1; border:2px solid #ffffff; }
        """

    def set_state(self, state: str) -> None:
        self._state = state.strip().casefold() or "pronta"
        self.orb.set_visual_state(self._state)
        self._update_accessibility()
        self.adjustSize()

    def set_listening(self, listening: bool) -> None:
        self._listening = listening
        self.orb.setProperty("listening", listening)
        if listening:
            self.orb.set_visual_state("ouvindo")
        elif self._state == "ouvindo":
            self.orb.set_visual_state("pronta")
        self.orb.style().unpolish(self.orb)
        self.orb.style().polish(self.orb)
        self._update_accessibility()

    def show_response(self, text: str) -> None:
        self.response_label.setText(text.strip() or "Resposta vazia.")
        QAccessible.updateAccessibility(
            QAccessibleEvent(self.response_label, QAccessible.Event.Alert)
        )
        self.set_state("pronta")
        self.set_expanded(True)
        # This tool window stays above other apps. Do not leave a potentially
        # sensitive answer exposed indefinitely on the desktop.
        self._response_timer.start(30_000)

    def show_error(self, text: str) -> None:
        self.response_label.setText(f"Erro: {text.strip() or 'Não foi possível responder.'}")
        QAccessible.updateAccessibility(
            QAccessibleEvent(self.response_label, QAccessible.Event.Alert)
        )
        self.set_state("erro")
        self.set_expanded(True)
        self._response_timer.start(30_000)

    def _expire_response(self) -> None:
        self.response_label.setText("Como posso ajudar você?")
        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        # Keep the orb anchored to the same screen corner while the quick-chat
        # panel changes this tool window's size.
        old_right = self.geometry().right()
        old_bottom = self.geometry().bottom()
        if self._expanded == expanded:
            return
        self.setUpdatesEnabled(False)
        self._expanded = expanded
        self.quick_panel.setVisible(expanded)
        # adjustSize() alone may preserve the former top-level width on
        # Windows. That leaves a wide invisible window after the quick chat is
        # hidden and makes the visible orb stop far from the left edge.
        self.layout().invalidate()
        self.layout().activate()
        self.resize(self.sizeHint())
        if self.isVisible():
            anchored = QPoint(old_right - self.width() + 1, old_bottom - self.height() + 1)
            self.move(self._clamped_position(anchored))
        if expanded:
            # WA_ShowWithoutActivating keeps the idle orb discreet. Once the user
            # explicitly opens chat, the editor must become operable by keyboard.
            self.activateWindow()
            self.quick_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        else:
            # The idle always-on-top orb must never steal keyboard input from
            # the user's active application.
            self.quick_input.clearFocus()
            self.clearFocus()
        self._update_accessibility()
        self.setUpdatesEnabled(True)
        self.update()

    def is_expanded(self) -> bool:
        return self._expanded

    def _submit_quick_message(self) -> None:
        message = self.quick_input.text().strip()
        if not message:
            return
        self.quick_input.clear()
        self.response_label.setText("Pensando…")
        self.set_state("pensando")
        self.quick_message_submitted.emit(message)

    def _apply_single_click(self) -> None:
        self.set_expanded(not self.is_expanded())

    def _request_main_window(self) -> None:
        self.set_expanded(False)
        self.main_window_requested.emit()
        self.activation_requested.emit()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._suppress_release = True
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._window_at_press = self.pos()
            self._dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_global is None or self._window_at_press is None:
            super().mouseMoveEvent(event)
            return
        delta = event.globalPosition().toPoint() - self._press_global
        if delta.manhattanLength() >= self._DRAG_THRESHOLD:
            self._dragged = True
            self.move(self._clamped_position(self._window_at_press + delta))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._suppress_release:
            self._suppress_release = False
            self._press_global = None
            self._window_at_press = None
            self._dragged = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._press_global is not None:
            should_click = not self._dragged
            self._press_global = None
            self._window_at_press = None
            self._dragged = False
            if should_click:
                self._apply_single_click()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._apply_single_click()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape and self.is_expanded():
            self.set_expanded(False)
            self.activateWindow()
            self.setFocus(Qt.FocusReason.ShortcutFocusReason)
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event: QEvent) -> bool:
        if (
            watched is self.quick_input
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            self.set_expanded(False)
            # Escape is an explicit keyboard interaction, so returning focus
            # to the orb is safe and keeps keyboard navigation available.
            self.activateWindow()
            self.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return True
        return super().eventFilter(watched, event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self._set_keyboard_focus_visible(True)
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._set_keyboard_focus_visible(False)
        super().focusOutEvent(event)

    def _set_keyboard_focus_visible(self, visible: bool) -> None:
        self.orb.setProperty("keyboardFocus", visible)
        self.orb.style().unpolish(self.orb)
        self.orb.style().polish(self.orb)

    def _update_accessibility(self) -> None:
        voice = "ouvindo a palavra Kiara" if self._listening else "microfone em espera"
        self.setAccessibleDescription(
            f"Estado: {self._state}. Processamento local do microfone; {voice}. "
            "Um clique para abrir ou fechar a conversa rápida; o botão de "
            "expandir abre a central completa. "
            f"Conversa rápida {'aberta' if self._expanded else 'fechada'}."
        )

    def _clamped_position(self, proposed: QPoint) -> QPoint:
        # Use the complete virtual desktop. Clamping to self.screen() trapped
        # the orb on the monitor where the drag began and left artificial
        # margins near other edges.
        screens = QApplication.screens()
        geometry = screens[0].geometry()
        for screen in screens[1:]:
            geometry = geometry.united(screen.geometry())
        x = min(max(proposed.x(), geometry.left()), geometry.right() - self.width() + 1)
        y = min(max(proposed.y(), geometry.top()), geometry.bottom() - self.height() + 1)
        return QPoint(x, y)

    def show_discreetly(self) -> None:
        self.set_expanded(False)
        geometry = (self.screen() or QApplication.primaryScreen()).geometry()
        self.layout().invalidate()
        self.layout().activate()
        self.resize(self.sizeHint())
        self.move(geometry.right() - self.width() + 1, geometry.bottom() - self.height() + 1)
        self.show()
        self.raise_()
