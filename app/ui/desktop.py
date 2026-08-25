from __future__ import annotations

import asyncio
import contextlib
import html
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core.agent_core import AgentCore
from app.security.kill_switch import KillSwitch
from app.ui.conversations import ConversationStore
from app.ui.overlay import MicrophoneButton, StatusOverlay
from app.ui.theme import apply_kiara_theme
from app.voice.service import VoiceService


def thinking_text(step: int) -> str:
    dots = "." * ((step % 3) + 1)
    return f"Pensando{dots}"


class RequestWorker(QObject):
    """Executa o núcleo assíncrono fora da thread da interface."""

    completed = Signal(str)
    delta_received = Signal(str)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, core: AgentCore) -> None:
        super().__init__()
        self._core = core
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="kiara-core", daemon=True)
        self._started = threading.Event()
        self._startup_error: BaseException | None = None
        self._thread.start()
        if not self._started.wait(5):
            raise RuntimeError("O runtime assíncrono não iniciou.")
        if self._startup_error is not None:
            raise RuntimeError("Falha ao iniciar o runtime assíncrono.") from self._startup_error

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            start = getattr(self._core, "astart", None)
            if start is not None:
                self._loop.run_until_complete(start())
            else:
                self._core.start_background()
        except Exception as exc:  # noqa: BLE001 - startup boundary
            self._startup_error = exc
            with contextlib.suppress(Exception):
                self._loop.run_until_complete(self._core.aclose())
            self._started.set()
            self._loop.close()
            return
        finally:
            self._started.set()
        self._loop.run_forever()

    @Slot(str)
    def handle(self, message: str) -> None:
        self.busy_changed.emit(True)

        async def run() -> str:
            stream = getattr(self._core, "handle_stream", None)
            if stream is None:
                return await self._core.handle(message)
            chunks: list[str] = []
            async for delta in stream(message):
                chunks.append(delta)
                self.delta_received.emit("".join(chunks))
            return "".join(chunks)

        future = asyncio.run_coroutine_threadsafe(run(), self._loop)

        def completed(done) -> None:
            self.busy_changed.emit(False)
            try:
                self.completed.emit(done.result())
            except Exception as exc:  # noqa: BLE001 - boundary keeps the UI alive
                self.failed.emit(str(exc))

        future.add_done_callback(completed)

    def shutdown(self) -> None:
        if not self._thread.is_alive():
            return
        close = getattr(self._core, "aclose", None)
        if close is not None:
            future = asyncio.run_coroutine_threadsafe(close(), self._loop)
        else:

            async def legacy_close() -> None:
                self._core.stop_background()

            future = asyncio.run_coroutine_threadsafe(legacy_close(), self._loop)
        try:
            future.result(timeout=8)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=8)
            if self._thread.is_alive():
                raise RuntimeError("O runtime assíncrono não encerrou no prazo.")

    def isRunning(self) -> bool:
        return self._thread.is_alive()


class VoiceWorker(QObject):
    transcript_ready = Signal(str)
    failed = Signal(str)
    state_changed = Signal(str)
    ready_for_turn = Signal()
    wake_retry = Signal()

    def __init__(self, voice: VoiceService, capture_seconds: float) -> None:
        super().__init__()
        self._voice = voice
        self._capture_seconds = capture_seconds

    @Slot()
    def listen(self) -> None:
        try:
            result = self._voice.listen(self._capture_seconds, self.state_changed.emit)
            if not result.text.strip():
                if self._voice.always_listen_for_wake_word:
                    self.wake_retry.emit()
                    return
                raise RuntimeError("nenhuma fala foi reconhecida")
            self.transcript_ready.emit(result.text)
        except Exception as exc:  # noqa: BLE001 - optional hardware boundary
            self.failed.emit(str(exc))
        finally:
            self.state_changed.emit("Pronta")

    @Slot(str)
    def speak(self, text: str) -> None:
        try:
            self.state_changed.emit("Falando…")
            self._voice.speak(text)
            self._voice.wait_until_spoken()
        except Exception as exc:  # noqa: BLE001 - optional backend boundary
            self.failed.emit(f"voz de saída indisponível: {exc}")
        finally:
            self.state_changed.emit("Pronta")
            self.ready_for_turn.emit()

    @Slot()
    def cancel(self) -> None:
        self._voice.cancel()


class ConfirmationBridge(QObject):
    """Encaminha confirmações síncronas do núcleo para a thread Qt."""

    requested = Signal(str, object)

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        super().__init__()
        self.timeout_seconds = timeout_seconds
        self.requested.connect(self._show, Qt.ConnectionType.QueuedConnection)

    def confirm(self, summary: str) -> bool:
        if QThread.currentThread() == QApplication.instance().thread():
            return self._ask(summary)
        result: dict[str, bool] = {"accepted": False}
        ready = threading.Event()
        self.requested.emit(summary, (result, ready))
        if not ready.wait(timeout=self.timeout_seconds):
            return False
        return result["accepted"]

    @Slot(str, object)
    def _show(self, summary: str, state: object) -> None:
        result, ready = state
        result["accepted"] = self._ask(summary)
        ready.set()

    @staticmethod
    def _ask(summary: str) -> bool:
        answer = QMessageBox.question(
            None,
            "Confirmar ação",
            f"A Kiara solicita autorização para:\n\n{summary}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


class KiaraWindow(QMainWindow):
    submit_requested = Signal(str)
    listen_requested = Signal()
    speak_requested = Signal(str)
    voice_cancel_requested = Signal()
    proactive_received = Signal(str)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # A displayed main window should own focus; the idle tool overlay must
        # not retain it from a previous quick-chat interaction.
        self._update_sidebar_visibility()
        self.input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        # Some window managers finalize the available geometry only after the
        # show event; reconcile the responsive navigation on the next Qt turn.
        QTimer.singleShot(0, self._update_sidebar_visibility)
        QTimer.singleShot(
            0,
            lambda: self.input.setFocus(Qt.FocusReason.ActiveWindowFocusReason),
        )

    def __init__(
        self,
        core: AgentCore,
        kill_switch: KillSwitch,
        voice: VoiceService | None = None,
        capture_seconds: float = 5.0,
    ) -> None:
        super().__init__()
        self._kill_switch = kill_switch
        self._core = core
        self.proactive_received.connect(self._show_proactive_notice)
        if hasattr(self._core, "set_proactive_notifier"):
            self._core.set_proactive_notifier(self._receive_proactive_notice)
        self._voice = voice
        self._quitting = False
        self._shutdown_complete = False
        self._request_origin = "main"
        self._voice_listen_pending = False
        settings = getattr(core, "settings", None)
        data_root = getattr(settings, "root", Path.cwd())
        self._conversation_store = ConversationStore(
            Path(data_root) / "data" / "conversations.json"
        )
        self._active_conversation_id = self._conversation_store.list()[0]["id"]
        self._thinking_step = 0
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(350)
        self._thinking_timer.timeout.connect(self._pulse_thinking)
        self.setWindowTitle("Kiara")
        self.setMinimumSize(440, 420)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is None:
            self.resize(1080, 720)
        else:
            self.resize(
                max(440, min(1080, available.width() - 80)),
                max(420, min(720, available.height() - 80)),
            )

        self.transcript = QTextBrowser(objectName="transcript")
        self.transcript.setAccessibleName("Histórico da conversa")
        self.transcript.setAccessibleDescription("Mensagens recentes entre você e a Kiara")
        self.transcript.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.transcript.document().setMaximumBlockCount(500)
        self.status = QLabel("Pronta", objectName="status")
        self.status.setAccessibleName("Estado da Kiara")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setVisible(False)
        self.input = QLineEdit(objectName="messageInput")
        self.input.setPlaceholderText("Converse com a Kiara…")
        self.input.setAccessibleName("Mensagem para a Kiara")
        self.send = QPushButton("Enviar", objectName="sendButton")
        self.send.setAccessibleName("Enviar mensagem")
        self.send.setShortcut(QKeySequence("Alt+E"))
        self.talk = MicrophoneButton("", objectName="talkButton")
        self.talk.setFixedSize(40, 40)
        self.talk.setAccessibleName("Pressione para falar com a Kiara")
        self.talk.setShortcut(QKeySequence("Alt+F"))
        self.conversation = QCheckBox("Modo conversa: desativado", objectName="conversationMode")
        self.conversation.setAccessibleName("Modo conversa contínua desativado")
        self.stop = QPushButton("Parar ações", objectName="stopButton")
        self.stop.setAccessibleName("Interromper todas as ações")
        self.stop.setAccessibleDescription("Ativa o bloqueio de emergência")
        self.stop.setShortcut(QKeySequence("Escape"))

        row = QHBoxLayout()
        row.setSpacing(6)
        attach = QPushButton("＋", objectName="attachButton")
        attach.setAccessibleName("Adicionar contexto ou anexo")
        attach.setToolTip("Adicionar contexto ou anexo")
        row.addWidget(attach)
        row.addWidget(self.input, 1)
        row.addWidget(self.talk)
        row.addWidget(self.send)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 8, 20, 16)
        layout.setSpacing(8)
        layout.addWidget(self.transcript, 1)
        layout.addLayout(row)
        layout.addWidget(self.status)
        safety_row = QHBoxLayout()
        safety_row.addWidget(self.conversation, 1)
        safety_row.addWidget(self.stop)
        layout.addLayout(safety_row)
        conversation = QWidget()
        conversation.setLayout(layout)
        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Painéis da Kiara")
        self.tabs.addTab(conversation, "Conversa")
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().hide()
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.currentChanged.connect(self._update_sidebar_visibility)

        self.sidebar = self._build_navigation_sidebar()
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        content_shell = QFrame(objectName="contentShell")
        content_layout = QVBoxLayout(content_shell)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        conversation_header = QFrame(objectName="conversationHeader")
        header_layout = QHBoxLayout(conversation_header)
        header_layout.setContentsMargins(4, 2, 4, 6)
        header_layout.setSpacing(8)
        header_copy = QVBoxLayout()
        header_copy.setSpacing(1)
        header_title = QLabel("Conversa com a Kiara", objectName="conversationTitle")
        header_title.setAccessibleName("Conversa com a Kiara")
        header_copy.addWidget(header_title)
        self.header_status = QLabel("●  Online", objectName="headerStatus")
        self.header_status.setAccessibleName("Estado online")
        header_copy.addWidget(self.header_status)
        header_layout.addLayout(header_copy)
        header_layout.addStretch(1)
        content_layout.addWidget(conversation_header)
        content_layout.addWidget(self.tabs)
        body.addWidget(self.sidebar, 0)
        body.addWidget(content_shell, 1)

        root = QWidget(objectName="kiaraRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addLayout(body, 1)
        self.setCentralWidget(root)
        self.overlay = StatusOverlay()
        self.overlay.main_window_requested.connect(self.show_normal)
        self.overlay.quick_message_submitted.connect(self._submit_quick_message)
        self.overlay.voice_requested.connect(self.start_listening)

        self._worker = RequestWorker(core)
        self._thread = self._worker
        self.submit_requested.connect(self._worker.handle)
        self._worker.completed.connect(self._on_completed)
        self._worker.delta_received.connect(self._on_delta)
        self._worker.failed.connect(self._on_failed)
        self._worker.busy_changed.connect(self._set_busy)

        self._voice_thread: QThread | None = None
        self._voice_worker: VoiceWorker | None = None
        if voice is None:
            self.talk.setEnabled(False)
            self.overlay.voice_button.setEnabled(False)
            self.conversation.setEnabled(False)
            self.talk.setToolTip("Voz desativada na configuração")
        else:
            mic = voice.microphone.availability()
            stt = voice.recognizer.availability()
            if not mic.available or not stt.available:
                self.talk.setEnabled(False)
                self.overlay.voice_button.setEnabled(False)
                self.conversation.setEnabled(False)
                self.talk.setToolTip(f"Voz indisponível: {mic.detail}; {stt.detail}")
            else:
                self._voice_thread = QThread(self)
                self._voice_worker = VoiceWorker(voice, capture_seconds)
                self._voice_worker.moveToThread(self._voice_thread)
                self.listen_requested.connect(self._voice_worker.listen)
                self.speak_requested.connect(self._voice_worker.speak)
                self.voice_cancel_requested.connect(self._voice_worker.cancel)
                self._voice_worker.transcript_ready.connect(self._submit_voice_text)
                self._voice_worker.failed.connect(self._on_voice_failed)
                self._voice_worker.state_changed.connect(self._set_voice_state)
                self._voice_worker.ready_for_turn.connect(self._continue_conversation)
                self._voice_worker.wake_retry.connect(self._continue_wake_monitor)
                self._voice_thread.start()

        self.send.clicked.connect(self.submit_message)
        self.input.returnPressed.connect(self.submit_message)
        self.stop.clicked.connect(self.stop_actions)
        self.talk.clicked.connect(self.start_listening)
        self.conversation.toggled.connect(self._toggle_conversation)
        self._create_tray()
        self.input.setFocus()
        if voice is not None and voice.conversation_mode and self._voice_worker is not None:
            self.conversation.setChecked(True)
        elif (
            voice is not None
            and voice.always_listen_for_wake_word
            and self._voice_worker is not None
        ):
            QTimer.singleShot(250, self.start_listening)
        self.show_overlay()

    def _build_navigation_sidebar(self) -> QWidget:
        sidebar = QFrame(objectName="conversationSidebar")
        sidebar.setAccessibleName("Conversas salvas da Kiara")
        sidebar.setFixedWidth(270)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(8)
        brand = QLabel("◉  Kiara", objectName="sideBrand")
        brand.setAccessibleName("Kiara")
        layout.addWidget(brand)
        layout.addSpacing(12)
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Conversas", objectName="conversationListTitle"))
        title_row.addStretch(1)
        new_button = QPushButton("+", objectName="newConversationButton")
        new_button.setFixedSize(30, 30)
        new_button.setAccessibleName("Nova conversa")
        new_button.setToolTip("Nova conversa")
        new_button.clicked.connect(self._new_conversation)
        title_row.addWidget(new_button)
        layout.addLayout(title_row)
        self.conversation_list = QListWidget(objectName="conversationList")
        self.conversation_list.setAccessibleName("Lista de conversas salvas")
        self.conversation_list.currentItemChanged.connect(self._select_conversation)
        layout.addWidget(self.conversation_list, 1)
        layout.addStretch(1)
        profile = QFrame(objectName="profileCard")
        profile_layout = QVBoxLayout(profile)
        profile_layout.setContentsMargins(10, 9, 10, 9)
        profile_layout.addWidget(QLabel("Você", objectName="cardTitle"))
        profile_layout.addWidget(QLabel("Conta pessoal", objectName="muted"))
        layout.addWidget(profile)
        self._refresh_conversation_list()
        return sidebar

    @staticmethod
    def _sidebar_card(title: str, rows: tuple[tuple[str, str], ...]) -> QFrame:
        card = QFrame(objectName="sideCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 11, 12, 11)
        card_layout.addWidget(QLabel(title, objectName="cardTitle"))
        for label, value in rows:
            row = QHBoxLayout()
            row.addWidget(QLabel(label, objectName="muted"), 1)
            row.addWidget(QLabel(value, objectName="success"))
            card_layout.addLayout(row)
        return card

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self._update_sidebar_visibility()

    @Slot()
    def _update_sidebar_visibility(self) -> None:
        """Keep the saved-conversations rail visible only on wide windows."""
        wide_layout = self.width() >= 720
        if hasattr(self, "sidebar"):
            self.sidebar.setVisible(wide_layout)
        if hasattr(self, "tabs"):
            self.tabs.tabBar().setVisible(not wide_layout)

    def _refresh_conversation_list(self) -> None:
        current_id = self._active_conversation_id
        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()
        selected_row = 0
        for row, conversation in enumerate(self._conversation_store.list()):
            messages = conversation.get("messages", [])
            preview = (
                messages[-1].get("text", "Sem mensagens ainda")
                if messages
                else "Sem mensagens ainda"
            )
            item = QListWidgetItem(f"{conversation.get('title', 'Conversa')}\n{preview[:46]}")
            item.setData(Qt.ItemDataRole.UserRole, conversation["id"])
            item.setToolTip(preview)
            self.conversation_list.addItem(item)
            if conversation["id"] == current_id:
                selected_row = row
        self.conversation_list.setCurrentRow(selected_row)
        self.conversation_list.blockSignals(False)

    @Slot()
    def _new_conversation(self) -> None:
        conversation = self._conversation_store.create()
        self._active_conversation_id = conversation["id"]
        self._refresh_conversation_list()
        self.transcript.clear()
        self.input.setFocus()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _select_conversation(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        conversation_id = str(current.data(Qt.ItemDataRole.UserRole))
        if conversation_id == self._active_conversation_id and self.transcript.document().isEmpty():
            self._load_conversation(conversation_id)
            return
        self._active_conversation_id = conversation_id
        self._load_conversation(conversation_id)

    def _load_conversation(self, conversation_id: str) -> None:
        conversation = self._conversation_store.get(conversation_id)
        if conversation is None:
            return
        self.transcript.clear()
        self._active_conversation_id = conversation_id
        for message in conversation.get("messages", []):
            self._append_message(
                str(message.get("author", "Kiara")),
                str(message.get("text", "")),
                persist=False,
            )

    def _append_message(
        self,
        author: str,
        message: str,
        *,
        kind: str = "message",
        persist: bool = True,
    ) -> None:
        if persist and kind == "message":
            self._conversation_store.add_message(self._active_conversation_id, author, message)
            self._refresh_conversation_list()
        safe = html.escape(message).replace("\n", "<br>")
        if kind == "notice":
            self.transcript.append(f'<div style="color:#8ea4b1;margin:8px 4px">◇ {safe}</div>')
            return
        is_kiara = author == "Kiara"
        accent = "#55edf7" if is_kiara else "#87f3da"
        initial = "◉" if is_kiara else "◎"
        if is_kiara:
            bubble = (
                '<table width="76%" align="left" cellspacing="0" cellpadding="11" '
                'style="background:#101a22;border:1px solid #22323a;margin:8px 0">'
                f'<tr><td width="25" valign="top"><span style="color:{accent};font-size:18px">{initial}</span></td>'
                f'<td><b style="color:{accent}">{author}</b><br><span style="color:#d8e4e7">{safe}</span></td>'
                '<td width="38" valign="bottom"><span style="color:#637781;font-size:10px">agora</span></td></tr></table>'
            )
        else:
            bubble = (
                '<table width="55%" align="right" cellspacing="0" cellpadding="11" '
                'style="background:#0c3938;border:1px solid #17534f;margin:8px 0">'
                f'<tr><td><b style="color:{accent}">{author}</b><br><span style="color:#ecffff">{safe}</span></td>'
                '<td width="38" valign="bottom"><span style="color:#8fb8b4;font-size:10px">agora</span></td></tr></table>'
            )
        self.transcript.append(bubble + '<div style="clear:both"></div>')

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon.fromTheme("applications-system"), self)
        self.tray.setToolTip("Kiara — pronta")
        menu = QMenu()
        show_action = QAction("Abrir Kiara", self)
        show_action.triggered.connect(self.show_normal)
        stop_action = QAction("Parar ações", self)
        stop_action.triggered.connect(self.stop_actions)
        quit_action = QAction("Sair", self)
        quit_action.triggered.connect(self.quit_app)
        overlay_action = QAction("Mostrar orbe", self)
        overlay_action.setCheckable(True)
        overlay_action.setChecked(True)
        overlay_action.toggled.connect(self._toggle_overlay)
        menu.addAction(show_action)
        menu.addAction(stop_action)
        menu.addAction(overlay_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    @Slot()
    def submit_message(self) -> None:
        message = self.input.text().strip()
        if not message or not self.send.isEnabled():
            return
        self._append_message("Você", message)
        self.input.clear()
        self._request_origin = "main"
        self.submit_requested.emit(message)

    @Slot(str)
    def _submit_quick_message(self, message: str) -> None:
        if not self.send.isEnabled():
            self.overlay.show_error("Aguarde a resposta atual antes de enviar outra mensagem.")
            return
        self._append_message("Você", message)
        self._request_origin = "overlay"
        self.submit_requested.emit(message)

    @Slot(str)
    def _on_delta(self, response: str) -> None:
        self._thinking_timer.stop()
        self.status.setVisible(True)
        self.status.setText(response[-600:])
        if self._request_origin == "overlay":
            self.overlay.show_response(response)

    @Slot(str)
    def _on_completed(self, response: str) -> None:
        self._append_message("Kiara", response)
        if self._request_origin == "overlay":
            self.overlay.show_response(response)
        self._request_origin = "main"
        if self._voice_worker is not None:
            self.speak_requested.emit(response)

    def _receive_proactive_notice(self, notice: dict[str, object]) -> None:
        payload = notice.get("payload", {})
        if isinstance(payload, dict):
            message = str(payload.get("title") or payload.get("message") or notice.get("source"))
        else:
            message = str(notice.get("source"))
        self.proactive_received.emit(message)

    @Slot(str)
    def _show_proactive_notice(self, message: str) -> None:
        self._append_message("Kiara", f"Percebi: {message}", kind="notice")
        self.tray.showMessage("Kiara", message)
        if self._voice_worker is not None:
            self.speak_requested.emit(message)

    @Slot()
    def start_listening(self) -> None:
        if (
            self._voice_worker is None
            or self._quitting
            or self._voice_listen_pending
            or not self.send.isEnabled()
        ):
            return
        self._voice_listen_pending = True
        self.talk.setEnabled(False)
        self._voice.cancel()
        self.listen_requested.emit()

    @Slot(str)
    def _submit_voice_text(self, message: str) -> None:
        # Voice and quick-chat can complete at nearly the same time. Never run
        # an ambient command concurrently with an already active request.
        if self._quitting or not self.send.isEnabled():
            self._append_message(
                "Kiara",
                "Comando de voz ignorado porque outra solicitação está em andamento.",
                kind="notice",
            )
            return
        self._append_message("Você", message)
        self._request_origin = "voice"
        self.submit_requested.emit(message)

    @Slot(str)
    def _set_voice_state(self, state: str) -> None:
        self.status.setText(state)
        normalized = state.casefold()
        # Transcription processes an already captured buffer; it is not live
        # microphone recording and must not be represented as such.
        self.overlay.set_listening(normalized.startswith("ouvindo"))
        if normalized.startswith("falando"):
            self.overlay.set_state("falando")
        elif normalized.startswith("transcrevendo"):
            self.overlay.set_state("pensando")
        elif normalized == "pronta":
            self.overlay.set_state("pronta")
        if state == "Pronta":
            self._voice_listen_pending = False
            self.talk.setEnabled(self._voice_worker is not None)

    @Slot(str)
    def _on_voice_failed(self, error: str) -> None:
        # Falhas técnicas do dispositivo ficam nos logs/estado interno; não
        # devem ocupar o histórico da conversa nem se repetir na tela.
        self.status.setText("Pronta")
        self.overlay.set_listening(False)
        self._voice_listen_pending = False
        self.talk.setEnabled(self._voice_worker is not None)
        if (
            self._voice is not None
            and self._voice.always_listen_for_wake_word
            and not self._quitting
        ):
            QTimer.singleShot(15_000, self._continue_wake_monitor)

    @Slot(bool)
    def _toggle_conversation(self, enabled: bool) -> None:
        state = "ativado" if enabled else "desativado"
        self.conversation.setText(f"Modo conversa: {state}")
        self.conversation.setAccessibleName(f"Modo conversa contínua {state}")
        if self._voice is None:
            self.conversation.setChecked(False)
            return
        if enabled:
            self._voice.start_conversation()
            self.start_listening()
        else:
            self._voice.stop_conversation()
            self._voice.cancel()

    @Slot()
    def _continue_conversation(self) -> None:
        wake_monitoring = bool(self._voice is not None and self._voice.always_listen_for_wake_word)
        if (self.conversation.isChecked() or wake_monitoring) and self.send.isEnabled():
            self.start_listening()

    @Slot()
    def _continue_wake_monitor(self) -> None:
        if (
            self._voice is not None
            and self._voice.always_listen_for_wake_word
            and not self._quitting
            and self.send.isEnabled()
        ):
            QTimer.singleShot(250, self.start_listening)

    @Slot(str)
    def _on_failed(self, error: str) -> None:
        self._append_message("Kiara", f"Não consegui concluir: {error}")
        if self._request_origin == "overlay":
            self.overlay.show_error(error)
        self._request_origin = "main"
        self.status.setText("Erro — pronta para tentar novamente")

    @Slot()
    def _pulse_thinking(self) -> None:
        self._thinking_step += 1
        self.status.setText(thinking_text(self._thinking_step))

    @Slot(bool)
    def _set_busy(self, busy: bool) -> None:
        self.send.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.status.setVisible(busy)
        if busy:
            self._thinking_step = 0
            self.status.setText(thinking_text(self._thinking_step))
            self._thinking_timer.start()
        else:
            self._thinking_timer.stop()
            self.status.setText("Pronta")
            self.status.setVisible(False)
        self.tray.setToolTip(f"Kiara — {'ocupada' if busy else 'pronta'}")
        self.overlay.set_state("ocupada" if busy else "pronta")
        if not busy:
            self.input.setFocus()

    @Slot()
    def stop_actions(self) -> None:
        if self._voice is not None:
            self._voice.cancel()
        self._kill_switch.trigger()
        self.status.setText("Ações interrompidas")
        self._append_message("Kiara", "Todas as novas ações foram bloqueadas.", kind="notice")
        self.overlay.set_state("ações interrompidas")

    @Slot(bool)
    def _toggle_overlay(self, visible: bool) -> None:
        if visible:
            self.show_overlay()
        else:
            self.overlay.hide()

    @Slot()
    def show_overlay(self) -> None:
        if self._quitting:
            return
        self.overlay.show_discreetly()
        self.overlay.raise_()

    @Slot()
    def show_normal(self) -> None:
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    @Slot(QSystemTrayIcon.ActivationReason)
    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_normal()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting or not self.tray.isVisible():
            self.shutdown()
            event.accept()
            return
        self.hide()
        event.ignore()
        self.tray.showMessage("Kiara", "Continuo disponível na bandeja do sistema.")

    @Slot()
    def quit_app(self) -> None:
        self._quitting = True
        self.shutdown()
        QApplication.instance().quit()

    def shutdown(self) -> None:
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        self._quitting = True
        if self._voice is not None:
            self._voice.shutdown()
        if hasattr(self._core, "set_proactive_notifier"):
            self._core.set_proactive_notifier(None)
        self._kill_switch.trigger()
        self.tray.hide()
        self.overlay.close()
        self._worker.shutdown()
        if self._voice_thread is not None:
            self._voice_thread.quit()
            if not self._voice_thread.wait(8000):
                raise RuntimeError("A thread de voz não encerrou no prazo.")


def run_desktop(
    factory: Callable[[Callable[[str], bool]], tuple[AgentCore, KillSwitch]],
    argv: list[str] | None = None,
    voice: VoiceService | None = None,
    capture_seconds: float = 5.0,
) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Kiara")
    apply_kiara_theme(app)
    app.setQuitOnLastWindowClosed(False)
    confirmation = ConfirmationBridge()
    core, kill_switch = factory(confirmation.confirm)
    window = KiaraWindow(core, kill_switch, voice, capture_seconds)
    window.show()
    app.aboutToQuit.connect(window.shutdown)
    return app.exec()
