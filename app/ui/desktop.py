from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
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
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.consumers import ConsumerIntelligenceService, ConsumerStatus
from app.core.agent_core import AgentCore
from app.leads import LeadCsvService, LeadStage
from app.security.kill_switch import KillSwitch
from app.ui.chat_widgets import ChatTranscript
from app.ui.commercial_settings import CommercialSettingsDialog
from app.ui.consumer_cockpit import ConsumerCockpit, ConsumerSummary, CustomerDetail
from app.ui.conversations import ConversationStore
from app.ui.overlay import MicrophoneButton, StatusOverlay
from app.ui.sdr_cockpit import (
    CockpitAction,
    CockpitMetric,
    LeadDetail,
    OpportunitySummary,
    SdrCockpit,
)
from app.ui.theme import apply_kiara_theme
from app.voice.service import VoiceService

logger = logging.getLogger(__name__)


def _ui_asset_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "app" / "ui" / "assets" / name


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
    wake_detected = Signal()

    def __init__(self, voice: VoiceService, capture_seconds: float) -> None:
        super().__init__()
        self._voice = voice
        self._capture_seconds = capture_seconds

    @Slot()
    def listen(self) -> None:
        try:
            result = self._voice.listen(self._capture_seconds, self.state_changed.emit)
            if not result.text.strip():
                if result.wake_detected:
                    self.wake_detected.emit()
                    return
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
        self._request_busy = False
        self._voice_active = False
        settings = getattr(core, "settings", None)
        data_root = getattr(settings, "root", Path.cwd())
        self._overlay_enabled = bool(settings and settings.get("ui.overlay_enabled", False))
        self._conversation_store = ConversationStore(
            Path(data_root) / "data" / "conversations.json"
        )
        self._active_conversation_id = self._conversation_store.list()[0]["id"]
        self._thinking_step = 0
        self._thinking_timer = QTimer(self)
        self._thinking_timer.setInterval(650)
        self._thinking_timer.timeout.connect(self._pulse_thinking)
        self.setWindowTitle("Kiara Lead Intelligence")
        self.setMinimumSize(900, 680)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is None:
            self.resize(1080, 720)
        else:
            self.resize(
                max(900, min(1440, available.width() - 80)),
                max(680, min(860, available.height() - 80)),
            )

        self.transcript = ChatTranscript()
        self._lead_store = getattr(core, "lead_store", None)
        self._consumer_store = getattr(core, "consumer_store", None)
        self._consumer_intelligence = ConsumerIntelligenceService()
        self.kpi_total = QLabel("0", objectName="kpiValue")
        self.kpi_qualified = QLabel("0", objectName="kpiValue")
        self.kpi_contacted = QLabel("0", objectName="kpiValue")
        self.kpi_meetings = QLabel("0", objectName="kpiValue")
        self.lead_filter = QComboBox(objectName="leadFilter")
        self.lead_filter.setAccessibleName("Filtrar pipeline por etapa")
        self.lead_filter.addItem("Todos os leads", "")
        for label, value in (
            ("Novos", "novo"), ("Qualificados", "qualificado"),
            ("Contatados", "contatado"), ("Responderam", "respondeu"),
            ("Reunião", "reuniao"), ("Discovery", "discovery"),
            ("Proposta", "proposta"), ("Negociação", "negociacao"),
            ("Contrato", "contrato"), ("Assinatura", "assinatura"),
            ("Convertidos", "convertido"), ("Perdidos", "perdido"),
        ):
            self.lead_filter.addItem(label, value)
        self.lead_table = QTableWidget(0, 7, objectName="leadTable")
        self.lead_table.setAccessibleName("Pipeline de leads")
        self.lead_table.setHorizontalHeaderLabels(
            ["Empresa", "Nicho", "Local", "WhatsApp", "Google", "Score", "Etapa"]
        )
        self.lead_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.lead_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lead_table.setAlternatingRowColors(True)
        self.lead_table.setShowGrid(False)
        self.lead_table.setMinimumHeight(270)
        self.lead_table.verticalHeader().hide()
        self.lead_table.horizontalHeader().setStretchLastSection(True)
        self.lead_detail = QLabel(
            "Selecione um lead para ver qualificação, origem e próxima ação.", objectName="leadDetail"
        )
        self.lead_detail.setAccessibleName("Detalhes do lead selecionado")
        self.lead_detail.setWordWrap(True)
        self.lead_detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lead_detail.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.stage_editor = QComboBox(objectName="stageEditor")
        self.stage_editor.setAccessibleName("Etapa comercial do lead")
        for label, value in (
            ("Novo", "novo"), ("Qualificado", "qualificado"), ("Contatado", "contatado"),
            ("Respondeu", "respondeu"), ("Reunião", "reuniao"),
            ("Discovery", "discovery"), ("Proposta", "proposta"),
            ("Negociação", "negociacao"), ("Contrato", "contrato"),
            ("Assinatura", "assinatura"),
            ("Convertido", "convertido"), ("Perdido", "perdido"),
        ):
            self.stage_editor.addItem(label, value)
        self.next_action_input = QLineEdit(objectName="nextActionInput")
        self.next_action_input.setAccessibleName("Próxima ação comercial")
        self.next_action_input.setPlaceholderText("Ex.: abordar no WhatsApp amanhã")
        self.save_lead_button = QPushButton("Atualizar lead", objectName="saveLeadButton")
        self.save_lead_button.setAccessibleName("Salvar etapa e próxima ação")
        self.save_lead_button.setEnabled(False)
        self.interaction_outcome = QComboBox(objectName="interactionOutcome")
        self.interaction_outcome.setAccessibleName("Resultado do contato")
        for label, value in (
            ("Contato realizado", "contato_realizado"), ("Sem resposta", "sem_resposta"),
            ("Respondeu", "respondeu"), ("Reunião marcada", "reuniao_marcada"),
            ("Não tem interesse", "sem_interesse"),
        ):
            self.interaction_outcome.addItem(label, value)
        self.log_interaction_button = QPushButton("Registrar interação", objectName="saveLeadButton")
        self.log_interaction_button.setEnabled(False)
        self.outreach_button = QPushButton("Gerar kit de abordagem", objectName="sendButton")
        self.outreach_button.setAccessibleName("Gerar abordagem personalizada para o lead")
        self.outreach_button.setEnabled(False)
        self.status = QLabel(
            "A Kiara pode cometer erros. Valide informações importantes.", objectName="status"
        )
        self.status.setAccessibleName("Estado da Kiara")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(False)
        self.status.setFixedHeight(34)
        self.input = QLineEdit(objectName="messageInput")
        self.input.setPlaceholderText("Digite sua mensagem…")
        self.input.setAccessibleName("Mensagem para a Kiara")
        self.send = QPushButton("➤", objectName="sendButton")
        self.send.setAccessibleName("Enviar mensagem para a Kiara")
        self.send.setShortcut(QKeySequence("Alt+E"))
        self.send.setFixedSize(38, 38)
        self.talk = MicrophoneButton("", objectName="talkButton")
        self.talk.setFixedSize(40, 40)
        self.talk.setAccessibleName("Pressione para falar com a Kiara")
        self.talk.setShortcut(QKeySequence("Alt+F"))
        self.conversation = QCheckBox("Modo voz: desativado", objectName="conversationMode")
        self.conversation.setAccessibleName("Modo voz desativado")
        self.stop = QPushButton("Parar ações", objectName="stopButton")
        self.stop.setAccessibleName("Interromper todas as ações")
        self.stop.setAccessibleDescription("Ativa o bloqueio de emergência")
        self.stop.setShortcut(QKeySequence("Escape"))
        self.conversation.setVisible(False)
        self.stop.setVisible(False)

        composer = QFrame(objectName="copilotComposer")
        row = QHBoxLayout(composer)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)
        attach = QPushButton("+", objectName="attachButton")
        attach.setAccessibleName("Adicionar contexto ou anexo")
        attach.setToolTip("Adicionar contexto ou anexo")
        # Anexos ainda não possuem fluxo implementado; não exponha um controle inerte.
        attach.setVisible(False)
        row.addWidget(attach)
        row.addWidget(self.input, 1)
        row.addWidget(self.talk)
        row.addWidget(self.send)

        chat_main = QFrame(objectName="copilotMain")
        chat_layout = QVBoxLayout(chat_main)
        chat_layout.setContentsMargins(20, 0, 16, 12)
        chat_layout.setSpacing(8)
        chat_header = QFrame(objectName="chatHeader")
        chat_header_layout = QHBoxLayout(chat_header)
        chat_header_layout.setContentsMargins(0, 10, 0, 10)
        avatar = QLabel("K", objectName="chatAvatar")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFixedSize(32, 32)
        identity = QVBoxLayout()
        identity.setSpacing(0)
        identity.addWidget(QLabel("Conversa com Kiara", objectName="chatTitle"))
        identity.addWidget(QLabel("Online", objectName="chatOnline"))
        chat_header_layout.addWidget(avatar)
        chat_header_layout.addLayout(identity)
        chat_header_layout.addStretch(1)
        self.conversation_picker = QComboBox(objectName="conversationPicker")
        self.conversation_picker.setAccessibleName("Selecionar conversa salva")
        self.conversation_picker.setMinimumWidth(150)
        chat_header_layout.addWidget(self.conversation_picker)
        new_button = QPushButton("+ Nova", objectName="chatHeaderAction")
        new_button.setAccessibleName("Nova conversa")
        new_button.clicked.connect(self._new_conversation)
        chat_header_layout.addWidget(new_button)
        self.delete_conversation_button = QPushButton("Excluir", objectName="deleteConversationButton")
        self.delete_conversation_button.setAccessibleName("Excluir conversa selecionada")
        self.delete_conversation_button.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_conversation_button.clicked.connect(self._delete_selected_conversation)
        chat_header_layout.addWidget(self.delete_conversation_button)
        chat_layout.addWidget(chat_header)
        chat_layout.addWidget(self.transcript, 1)
        chat_layout.addWidget(composer)
        chat_layout.addWidget(self.status)
        safety_row = QHBoxLayout()
        safety_row.addWidget(self.conversation, 1)
        safety_row.addWidget(self.stop)
        chat_layout.addLayout(safety_row)

        self.context_panel = QFrame(objectName="copilotContext")
        self.context_panel.setAccessibleName("Contexto comercial da conversa")
        self.context_panel.setMinimumWidth(310)
        self.context_panel.setMaximumWidth(380)
        context_layout = QVBoxLayout(self.context_panel)
        context_layout.setContentsMargins(18, 20, 18, 16)
        context_layout.setSpacing(12)
        context_layout.addWidget(QLabel("CAMPANHA ATIVA", objectName="contextEyebrow"))
        context_layout.addWidget(QLabel("Operação comercial", objectName="contextTitle"))
        context_layout.addWidget(
            QLabel("A Kiara usa seu ICP, pipeline e fontes verificadas.", objectName="contextMuted")
        )
        metrics_card = QFrame(objectName="contextCard")
        metrics_layout = QHBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(12, 12, 12, 12)
        metric = QVBoxLayout()
        metric.addWidget(self.kpi_total)
        metric.addWidget(QLabel("TOTAL DE LEADS", objectName="contextMetricLabel"))
        metrics_layout.addLayout(metric, 1)
        self.kpi_qualified.hide()
        self.kpi_contacted.hide()
        self.kpi_meetings.hide()
        context_layout.addWidget(metrics_card)
        context_layout.addWidget(QLabel("PLANO DE PESQUISA", objectName="contextEyebrow"))
        plan_card = QFrame(objectName="contextCard")
        plan_layout = QVBoxLayout(plan_card)
        plan_layout.setContentsMargins(12, 10, 12, 10)
        plan_layout.setSpacing(7)
        for step, state in (
            ("Definir critérios", "Pronto"),
            ("Pesquisar empresas", "Pronto"),
            ("Enriquecer e qualificar", "Em espera"),
            ("Priorizar próxima ação", "Em espera"),
        ):
            plan_row = QHBoxLayout()
            plan_row.addWidget(QLabel(step, objectName="contextRow"), 1)
            plan_row.addWidget(QLabel(state, objectName="contextState"))
            plan_layout.addLayout(plan_row)
        context_layout.addWidget(plan_card)
        context_layout.addWidget(QLabel("FONTES DISPONÍVEIS", objectName="contextEyebrow"))
        source_card = QFrame(objectName="contextCard")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(12, 9, 12, 9)
        source_tiles = QHBoxLayout()
        for symbol, name in (("●", "Google Maps"), ("◎", "Web"), ("in", "LinkedIn"), ("C", "CRM")):
            tile = QLabel(symbol, objectName="sourceTile")
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setFixedSize(34, 34)
            tile.setAccessibleName(name)
            source_tiles.addWidget(tile)
        source_tiles.addStretch(1)
        source_layout.addLayout(source_tiles)
        context_layout.addWidget(source_card)
        tip_card = QFrame(objectName="kiaraTipCard")
        tip_layout = QVBoxLayout(tip_card)
        tip_layout.setContentsMargins(12, 10, 12, 10)
        tip_layout.addWidget(QLabel("Dica da Kiara", objectName="contextTitle"))
        tip = QLabel(
            "Leads com resposta em até 5 minutos têm mais chance de conversão.",
            objectName="contextMuted",
        )
        tip.setWordWrap(True)
        tip_layout.addWidget(tip)
        context_layout.addWidget(tip_card)
        context_layout.addWidget(QLabel("LEAD SELECIONADO", objectName="contextEyebrow"))
        detail_scroll = QScrollArea(objectName="leadDetailScroll")
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        detail_content = QWidget(objectName="leadDetailContent")
        detail_content_layout = QVBoxLayout(detail_content)
        detail_content_layout.setContentsMargins(0, 0, 4, 0)
        detail_content_layout.setSpacing(8)
        detail_content_layout.addWidget(self.lead_detail)
        self.lead_editor = QWidget(objectName="leadEditor")
        editor_layout = QVBoxLayout(self.lead_editor)
        editor_layout.setContentsMargins(0, 4, 0, 0)
        editor_layout.setSpacing(8)
        editor_layout.addWidget(QLabel("ETAPA", objectName="contextEyebrow"))
        editor_layout.addWidget(self.stage_editor)
        editor_layout.addWidget(self.next_action_input)
        editor_layout.addWidget(self.save_lead_button)
        editor_layout.addWidget(QLabel("INTERAÇÃO", objectName="contextEyebrow"))
        editor_layout.addWidget(self.interaction_outcome)
        editor_layout.addWidget(self.log_interaction_button)
        editor_layout.addWidget(self.outreach_button)
        self.lead_editor.setVisible(False)
        detail_content_layout.addWidget(self.lead_editor)
        detail_content_layout.addStretch(1)
        detail_scroll.setWidget(detail_content)
        context_layout.addWidget(detail_scroll, 1)
        approval = QLabel(
            "Ações externas sempre exigem sua aprovação.", objectName="approvalNotice"
        )
        approval.setWordWrap(True)
        context_layout.addWidget(approval)

        # The complete table remains the source for selection and automation,
        # while its visual presentation lives in the dedicated cockpit pages.
        self.lead_table.setVisible(False)
        self.lead_filter.setVisible(False)
        conversation_layout = QHBoxLayout()
        conversation_layout.setContentsMargins(0, 0, 0, 0)
        conversation_layout.setSpacing(0)
        conversation_layout.addWidget(chat_main, 1)
        conversation_layout.addWidget(self.context_panel)
        conversation = QWidget(objectName="copilotWorkspace")
        conversation.setLayout(conversation_layout)
        self.cockpit = SdrCockpit()
        self.cockpit.opportunity_selected.connect(self._show_cockpit_lead)
        self.cockpit.action_requested.connect(self._run_cockpit_action)
        self.cockpit.stage_change_requested.connect(self._move_pipeline_lead)
        self.cockpit.filters_changed.connect(lambda _days, _stage: self._refresh_leads())
        self.cockpit.import_requested.connect(self._import_leads_csv)
        self.cockpit.export_requested.connect(self._export_visible_leads_csv)
        cockpit_navigation = self.cockpit.findChild(QFrame, "cockpitNavigation")
        if cockpit_navigation is not None:
            cockpit_navigation.hide()
        self.consumer_cockpit = ConsumerCockpit()
        self.consumer_cockpit.consumer_selected.connect(self._show_consumer)
        self.consumer_cockpit.action_requested.connect(self._run_consumer_action)
        self.workspace_stack = QStackedWidget(objectName="workspaceStack")
        self.workspace_stack.setAccessibleName("Áreas de trabalho da Kiara")
        self.workspace_stack.addWidget(self.cockpit)
        self.workspace_stack.addWidget(conversation)
        self.workspace_stack.addWidget(self.consumer_cockpit)
        self.workspace_stack.setCurrentIndex(1)
        self.workspace_stack.currentChanged.connect(self._update_sidebar_visibility)
        # Transitional controller alias used by business actions while the UI
        # now renders through a tabless workspace stack.
        self.tabs = self.workspace_stack

        self.header_status = QLabel("●  Pronta para leads", objectName="headerStatus")
        self.header_status.setAccessibleName("Estado da pesquisa comercial")
        self.rail = self._build_navigation_rail()
        self.sidebar = self._build_navigation_sidebar()
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.rail)
        body.addWidget(self.sidebar)
        content_shell = QFrame(objectName="contentShell")
        content_layout = QVBoxLayout(content_shell)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.workspace_stack)
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
            self.talk.setVisible(False)
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
                self._voice_worker.wake_detected.connect(self._on_wake_detected)
                self._voice_thread.start()

        self.send.clicked.connect(self.submit_message)
        self.input.returnPressed.connect(self.submit_message)
        self.stop.clicked.connect(self.stop_actions)
        self.talk.clicked.connect(self.start_listening)
        self.conversation.toggled.connect(self._toggle_conversation)
        self.lead_filter.currentIndexChanged.connect(self._refresh_leads)
        self.lead_table.itemSelectionChanged.connect(self._show_selected_lead)
        self.save_lead_button.clicked.connect(self._save_selected_lead)
        self.log_interaction_button.clicked.connect(self._log_selected_interaction)
        self.outreach_button.clicked.connect(self._prepare_selected_outreach)
        self.conversation_picker.currentIndexChanged.connect(
            self._select_conversation_from_picker
        )
        self._refresh_leads()
        self._refresh_consumers()
        self._create_tray()
        if voice is not None and voice.conversation_mode and self._voice_worker is not None:
            self.conversation.setChecked(True)
        elif (
            voice is not None
            and voice.always_listen_for_wake_word
            and self._voice_worker is not None
        ):
            QTimer.singleShot(250, self.start_listening)
        if self._overlay_enabled:
            self.show_overlay()

    def _build_navigation_rail(self) -> QWidget:
        rail = QFrame(objectName="navigationRail")
        rail.setAccessibleName("Navegação principal da Kiara")
        rail.setFixedWidth(72)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(10)
        mark = QLabel("K", objectName="railBrand")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setAccessibleName("Kiara")
        layout.addWidget(mark)
        layout.addSpacing(16)
        self.nav_overview = QPushButton("01", objectName="railButton")
        self.nav_overview.setToolTip("Visão geral")
        self.nav_overview.setAccessibleName("Abrir visão geral executiva")
        self.nav_overview.setCheckable(True)
        self.nav_overview.clicked.connect(lambda: self._open_workspace("hoje"))
        self.nav_pipeline = QPushButton("02", objectName="railButton")
        self.nav_pipeline.setToolTip("Pipeline comercial")
        self.nav_pipeline.setAccessibleName("Abrir pipeline comercial")
        self.nav_pipeline.setCheckable(True)
        self.nav_pipeline.clicked.connect(lambda: self._open_workspace("pipeline"))
        self.nav_copilot = QPushButton("AI", objectName="railButton")
        self.nav_copilot.setToolTip("Kiara Copiloto")
        self.nav_copilot.setAccessibleName("Abrir Kiara Copiloto")
        self.nav_copilot.setCheckable(True)
        self.nav_copilot.setChecked(True)
        self.nav_copilot.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.nav_consumers = QPushButton("B2C", objectName="railButton")
        self.nav_consumers.setToolTip("Consumidores qualificados")
        self.nav_consumers.setAccessibleName("Abrir inteligência de consumidores")
        self.nav_consumers.setCheckable(True)
        self.nav_consumers.clicked.connect(self._open_consumers)
        nav_campaigns = QPushButton("03", objectName="railButton")
        nav_campaigns.setToolTip("Campanhas e resultados")
        nav_campaigns.setAccessibleName("Abrir campanhas e resultados")
        nav_campaigns.setCheckable(True)
        nav_campaigns.clicked.connect(lambda: self._open_workspace("resultados"))
        for button in (
            self.nav_overview,
            self.nav_pipeline,
            nav_campaigns,
            self.nav_consumers,
            self.nav_copilot,
        ):
            button.setFixedSize(48, 48)
            layout.addWidget(button)
        layout.addStretch(1)
        settings_button = QPushButton("CFG", objectName="railButton")
        settings_button.setToolTip("Configurar operação comercial")
        settings_button.setAccessibleName("Configurar perfil comercial e ICP")
        settings_button.setFixedSize(48, 48)
        settings_button.clicked.connect(self._configure_commercial_profile)
        layout.addWidget(settings_button)
        return rail

    def _build_navigation_sidebar(self) -> QWidget:
        sidebar = QFrame(objectName="conversationSidebar")
        sidebar.setAccessibleName("Navegação principal da Kiara")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 14)
        layout.setSpacing(6)
        brand = QLabel("K   Kiara Copiloto", objectName="sideBrand")
        brand.setAccessibleName("Kiara Copiloto")
        layout.addWidget(brand)
        layout.addWidget(self.header_status)
        layout.addSpacing(18)
        self.nav_overview = self._side_nav("⌂", "Visão geral", lambda: self._open_workspace("hoje"))
        self.nav_pipeline = self._side_nav("▽", "Pipeline", lambda: self._open_workspace("pipeline"))
        self.nav_consumers = self._side_nav("♙", "Consumidores", self._open_consumers)
        self.nav_consumers.setAccessibleName("Abrir inteligência de consumidores")
        self.nav_campaigns = self._side_nav("⌁", "Campanhas", lambda: self._open_workspace("resultados"))
        self.nav_copilot = self._side_nav("▣", "Conversas", lambda: self.tabs.setCurrentIndex(1))
        for button in (
            self.nav_overview, self.nav_pipeline, self.nav_consumers,
            self.nav_campaigns, self.nav_copilot,
        ):
            layout.addWidget(button)
        settings_button = self._side_nav("⚙", "Configurações", self._configure_commercial_profile)
        layout.addWidget(settings_button)
        self.nav_copilot.setChecked(True)
        layout.addStretch(1)
        self.conversation_list = QListWidget(objectName="conversationList")
        self.conversation_list.setAccessibleName("Lista de conversas salvas")
        self.conversation_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.conversation_list.currentItemChanged.connect(self._select_conversation)
        self.conversation_list.hide()
        profile = QFrame(objectName="profileCard")
        profile_layout = QVBoxLayout(profile)
        profile_layout.setContentsMargins(10, 9, 10, 9)
        profile_layout.addWidget(QLabel("Você", objectName="cardTitle"))
        profile_layout.addWidget(QLabel("Operação comercial", objectName="muted"))
        layout.addWidget(profile)
        self._refresh_conversation_list()
        return sidebar

    @staticmethod
    def _side_nav(icon: str, label: str, callback) -> QPushButton:
        button = QPushButton(f"{icon}   {label}", objectName="sideNavButton")
        button.setCheckable(True)
        button.setAccessibleName(f"Abrir {label}")
        button.setMinimumHeight(42)
        button.clicked.connect(callback)
        return button

    def _open_workspace(self, section: str) -> None:
        self.cockpit.set_current_section(section)
        self.tabs.setCurrentIndex(0)
        self.nav_overview.setChecked(section == "hoje")
        self.nav_pipeline.setChecked(section == "pipeline")
        self.nav_campaigns.setChecked(section == "resultados")
        self.nav_copilot.setChecked(False)
        self.nav_consumers.setChecked(False)

    @Slot()
    def _open_consumers(self) -> None:
        self._refresh_consumers()
        self.tabs.setCurrentIndex(2)
        self.nav_overview.setChecked(False)
        self.nav_pipeline.setChecked(False)
        self.nav_copilot.setChecked(False)
        self.nav_consumers.setChecked(True)
        self.nav_campaigns.setChecked(False)

    @Slot()
    def _refresh_consumers(self) -> None:
        if self._consumer_store is None:
            self.consumer_cockpit.set_consumers(())
            return
        summaries = []
        for person in self._consumer_store.list_people(limit=1000):
            room = self._consumer_room(person)
            summaries.append(ConsumerSummary(
                person.id,
                person.display_name or "Pessoa",
                room.source_platform or person.source or "Não informada",
                room.qualification.readiness,
                person.stage.value.replace("_", " ").title(),
                "Válido" if room.consent.can_contact else "Bloqueado",
                room.next_action,
            ))
        for opportunity in self._consumer_store.list_organic_opportunities(limit=300):
            summaries.append(ConsumerSummary(
                f"organic:{opportunity['id']}",
                str(opportunity["title"] or "Sinal público"),
                str(opportunity["platform"]).title(),
                int(opportunity["intent_score"]),
                "Oportunidade pública",
                "Aguardando opt-in",
                "Revisar publicação e preparar resposta pública",
            ))
        self.consumer_cockpit.set_consumers(summaries)

    def _consumer_room(self, person):
        identities = self._consumer_store.identities(person.id)
        touchpoints = self._consumer_store.touchpoints(person.id)
        consents = self._consumer_store.consents(person.id)
        suppressed = any(
            value and self._consumer_store.is_suppressed(kind, value)
            for kind, value in (("email", person.email), ("phone", person.phone))
        )
        active = next((item for item in consents if item.status == "granted" and
                       self._consumer_store.has_active_consent(
                           person.id, channel=item.channel, purpose=item.purpose
                       )), None)
        return self._consumer_intelligence.generate(
            {
                "id": person.id,
                "display_name": person.display_name,
                "platform": identities[0].platform if identities else person.source,
                "signals": [item.kind for item in touchpoints],
                "opted_out": suppressed,
            },
            consent=(
                {
                    "granted": True, "channel": active.channel,
                    "purpose": active.purpose, "source": active.source,
                    "recorded_at": active.captured_at,
                }
                if active else None
            ),
        )

    @Slot(str)
    def _show_consumer(self, identifier: str) -> None:
        if self._consumer_store is None:
            return
        if identifier.startswith("organic:"):
            opportunity = self._consumer_store.get_organic_opportunity(
                int(identifier.partition(":")[2])
            )
            if opportunity is None:
                return
            self.consumer_cockpit.set_customer_detail(CustomerDetail(
                identifier=identifier,
                name=str(opportunity["title"] or "Sinal público"),
                readiness="Oportunidade pública",
                readiness_score=int(opportunity["intent_score"]),
                origin=f"{str(opportunity['platform']).title()} · {opportunity['source_url']}",
                declared_need=str(opportunity["excerpt"]),
                intent_signals=tuple(opportunity["intent_signals"]),
                consent="Sem opt-in para mensagem privada",
                allowed_channels=(),
                unknowns=("identidade confirmada", "necessidade", "prazo", "capacidade"),
                suggested_message="Prepare uma resposta pública útil e convide para o canal oficial.",
                next_action="Revisar a publicação; não enviar mensagem privada sem opt-in.",
            ))
            return
        person = self._consumer_store.get_person(identifier)
        if person is None:
            return
        room = self._consumer_room(person)
        status_labels = {
            ConsumerStatus.SQL: "Pronto para comprar",
            ConsumerStatus.NURTURE: "Nutrição",
            ConsumerStatus.RESEARCH: "Precisa qualificar",
            ConsumerStatus.BLOCKED: "Contato bloqueado",
            ConsumerStatus.DISQUALIFIED: "Desqualificado",
        }
        touchpoints = self._consumer_store.touchpoints(identifier)
        channels = (room.consent.channel,) if room.consent.can_contact else ()
        self.consumer_cockpit.set_customer_detail(CustomerDetail(
            identifier=person.id,
            name=person.display_name or "Pessoa",
            readiness=status_labels[room.qualification.status],
            readiness_score=room.qualification.readiness,
            origin=room.source_platform or person.source,
            declared_need=person.notes,
            intent_signals=tuple(item.kind.replace("_", " ") for item in touchpoints),
            consent=("Consentimento válido" if room.consent.can_contact
                     else "Sem consentimento válido"),
            allowed_channels=channels,
            unknowns=tuple(item.field for item in room.unknowns),
            recommended_offer=room.handoff.recommended_offer,
            next_action=room.next_action,
        ))

    @Slot(str)
    def _run_consumer_action(self, identifier: str) -> None:
        self._show_consumer(identifier)
        self.tabs.setCurrentIndex(1)
        self.input.setText(
            "Prepare a próxima melhor ação para o consumidor selecionado. Use somente "
            "dados confirmados, respeite o consentimento e entregue mensagem, oferta e "
            "perguntas de qualificação prontas para aprovação."
        )
        self.input.setFocus()

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

    @Slot()
    def _refresh_leads(self) -> None:
        if self._lead_store is None:
            self._visible_leads = []
            return
        period_days = int(self.cockpit.period_filter.currentData() or 0)
        selected_group = str(self.cockpit.stage_filter.currentData() or "")
        cutoff = datetime.now(UTC) - timedelta(days=period_days) if period_days else None
        self._visible_leads = []
        for lead in self._lead_store.list(limit=1000):
            try:
                activity_at = self._utc_datetime(lead.updated_at)
            except (TypeError, ValueError, OverflowError):
                activity_at = datetime.min.replace(tzinfo=UTC)
            if cutoff is not None and activity_at < cutoff:
                continue
            if selected_group and self._visual_pipeline_stage(lead.stage.value) != selected_group:
                continue
            self._visible_leads.append(lead)
        self.lead_table.setRowCount(len(self._visible_leads))
        for row, lead in enumerate(self._visible_leads):
            reputation = (
                f"{lead.rating:.1f} ({lead.review_count})" if lead.rating else "Não coletado"
            )
            values = (lead.company, lead.niche, lead.location, lead.whatsapp, reputation,
                      str(lead.score), lead.stage.value.replace("_", " ").title())
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, lead.id)
                self.lead_table.setItem(row, column, item)
        metrics = {stage.value: 0 for stage in LeadStage}
        for lead in self._visible_leads:
            metrics[lead.stage.value] += 1
        metrics["total"] = len(self._visible_leads)
        self.kpi_total.setText(str(metrics["total"]))
        qualified_total = sum(
            metrics[key] for key in (
                "qualificado", "respondeu", "reuniao", "discovery", "proposta",
                "negociacao", "contrato", "assinatura", "convertido",
            )
        )
        contacted_total = sum(
            metrics[key] for key in (
                "contatado", "respondeu", "reuniao", "discovery", "proposta",
                "negociacao", "contrato", "assinatura", "convertido",
            )
        )
        meeting_total = sum(
            metrics[key] for key in (
                "reuniao", "discovery", "proposta", "negociacao", "contrato",
                "assinatura", "convertido",
            )
        )
        self.kpi_qualified.setText(str(qualified_total))
        self.kpi_contacted.setText(str(contacted_total))
        self.kpi_meetings.setText(str(meeting_total))
        contact_rate = contacted_total / max(metrics["total"], 1) * 100
        replied_total = sum(metrics[key] for key in (
            "respondeu", "reuniao", "discovery", "proposta", "negociacao",
            "contrato", "assinatura", "convertido",
        ))
        reply_rate = replied_total / max(contacted_total, 1) * 100
        meeting_rate = meeting_total / max(contacted_total, 1) * 100
        visible_ids = {lead.id for lead in self._visible_leads}
        due = [lead for lead in self._lead_store.due_actions(
            through=datetime.now(UTC).isoformat(), limit=100
        ) if lead.id in visible_ids][:20]
        period_label = self.cockpit.period_filter.currentText().casefold()
        self.cockpit.set_metrics((
            CockpitMetric("Leads gerais", str(metrics["total"]), period_label),
            CockpitMetric("Qualificados", str(qualified_total), period_label),
            CockpitMetric("Reuniões", str(meeting_total), period_label),
            CockpitMetric("Taxa de resposta", f"{reply_rate:.1f}%", period_label),
        ))
        self.cockpit.set_actions(
            CockpitAction(
                lead.id, lead.company, lead.next_action or "Revisar oportunidade",
                "Abrir oportunidade", "high",
            )
            for lead in due
        )
        self.cockpit.set_opportunities(
            OpportunitySummary(
                lead.id, lead.company, lead.niche, lead.location, lead.score,
                lead.stage.value.replace("_", " ").title(), lead.next_action,
                readiness_score=self._readiness_score(lead.qualification_data),
                readiness=str(lead.qualification_data.get("status", "")),
            )
            for lead in self._visible_leads
        )
        self.cockpit.set_dashboard_data(
            performance=self._performance_buckets(self._visible_leads, period_days),
            sources=self._source_breakdown(self._visible_leads),
            funnel=self._funnel_breakdown(self._visible_leads),
        )
        self.cockpit.set_results_summary(
            f"Contatados: {metrics['contatado']}\nRespostas: {metrics['respondeu']}\n"
            f"Reuniões: {metrics['reuniao']}\nConversões: {metrics['convertido']}\n\n"
            f"Taxa de contato: {contact_rate:.1f}%\n"
            f"Taxa de resposta: {reply_rate:.1f}%\n"
            f"Avanço para reunião: {meeting_rate:.1f}%\n\n"
            f"Filtro: {self.cockpit.period_filter.currentText()} · "
            f"{self.cockpit.stage_filter.currentText()}"
        )

    @staticmethod
    def _visual_pipeline_stage(stage: str) -> str:
        stage = stage.casefold()
        if stage in {"negociacao", "contrato", "assinatura", "convertido"}:
            return "fechamento"
        if stage == "proposta":
            return "proposta"
        if stage in {"reuniao", "discovery"}:
            return "discovery"
        if stage in {"contatado", "respondeu"}:
            return "contato"
        if stage == "qualificado":
            return "qualificados"
        return "descobertos"

    @classmethod
    def _funnel_breakdown(cls, leads) -> tuple[tuple[str, int], ...]:
        counts = Counter(cls._visual_pipeline_stage(lead.stage.value) for lead in leads)
        return tuple((label, counts[key]) for key, label in (
            ("descobertos", "Descobertos"), ("qualificados", "Qualificados"),
            ("contato", "Contato"), ("discovery", "Discovery"),
            ("proposta", "Proposta"), ("fechamento", "Fechamento"),
        ))

    @staticmethod
    def _source_breakdown(leads) -> tuple[tuple[str, int], ...]:
        counts: Counter[str] = Counter()
        for lead in leads:
            host = (urlparse(lead.source_url).hostname or "").casefold()
            if "google." in host or "goo.gl" in host:
                label = "Google Maps"
            elif "instagram." in host:
                label = "Instagram"
            elif "facebook." in host:
                label = "Facebook"
            elif "linkedin." in host:
                label = "LinkedIn"
            elif "tiktok." in host:
                label = "TikTok"
            elif host:
                label = "Site / web"
            else:
                label = "Não informada"
            counts[label] += 1
        return tuple(counts.most_common(5))

    def _performance_buckets(self, leads, period_days: int) -> tuple[tuple[str, int], ...]:
        days = period_days or 90
        now = datetime.now(UTC)
        bucket_days = max(1, (days + 6) // 7)
        values = [0] * 7
        timestamps = []
        for lead in leads:
            try:
                timestamps.append(self._utc_datetime(lead.created_at))
            except (TypeError, ValueError, OverflowError):
                continue
            for interaction in self._lead_store.interactions(lead.id):
                try:
                    timestamps.append(self._utc_datetime(interaction.occurred_at))
                except (TypeError, ValueError, OverflowError):
                    continue
        for occurred_at in timestamps:
            age = max(0, (now - occurred_at).days)
            if period_days and age >= period_days:
                continue
            values[6 - min(6, age // bucket_days)] += 1
        labels = []
        for index in range(7):
            days_ago = (6 - index) * bucket_days
            labels.append((now - timedelta(days=days_ago)).strftime("%d/%m"))
        return tuple(zip(labels, values, strict=True))

    @staticmethod
    def _utc_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @Slot(str)
    def _show_cockpit_lead(self, identifier: str) -> None:
        if self._lead_store is None:
            return
        lead = next((item for item in self._lead_store.list(limit=1000) if item.id == identifier), None)
        if lead is None:
            return
        evidence = self._lead_store.observations(identifier)
        evidence_lines = tuple(
            f"{item.field_name}: {item.raw_value} · {item.status} ({item.confidence:.0%})"
            for item in evidence[:8]
        )
        score_context = (
            f"Confiança {lead.confidence_score} · ICP {lead.fit_score} · "
            f"Oportunidade {lead.opportunity_score} · Engajamento {lead.engagement_score}"
        )
        qualification_data = lead.qualification_data or {}
        dossier_data = lead.dossier_data or {}
        sales_artifacts = lead.sales_artifacts or {}
        readiness_status = str(qualification_data.get("status", "precisa_pesquisar"))
        readiness_labels = {
            "sql": "SQL pronto", "sql_pronto": "SQL pronto",
            "nurture": "Nutrição", "nutricao": "Nutrição",
            "research": "Precisa pesquisar", "precisa_pesquisar": "Precisa pesquisar",
            "disqualified": "Desqualificado", "desqualificado": "Desqualificado",
        }
        facts = dossier_data.get("verified_facts", [])
        fact_lines = tuple(
            f"{item.get('field', 'fato')}: {item.get('value', '')}"
            for item in facts if isinstance(item, dict)
        )
        hypotheses = dossier_data.get("hypotheses", [])
        decision_makers = dossier_data.get("decision_makers", [])
        decision_maker = ", ".join(
            str(item.get("value", "")) for item in decision_makers if isinstance(item, dict)
        )
        meeting_questions = tuple(dossier_data.get("discovery_questions", ()))
        proposal = sales_artifacts.get("proposal", {})
        proposal_text = ""
        if (
            isinstance(proposal, dict)
            and bool(sales_artifacts.get("grounded", False))
            and bool(proposal.get("is_ready_for_review", False))
        ):
            scope = ", ".join(str(item) for item in proposal.get("recommended_scope", ()))
            proposal_text = " · ".join(
                item for item in (scope, str(proposal.get("investment", ""))) if item
            )
        contract = sales_artifacts.get("contract_draft", {})
        if (
            isinstance(contract, dict)
            and bool(sales_artifacts.get("grounded", False))
            and bool(contract.get("is_ready_for_review", False))
        ):
            proposal_text = "\n".join(
                item for item in (
                    proposal_text,
                    f"Contrato preparado: {contract.get('template_reference', '')}",
                ) if item
            )
        gaps = tuple(str(item) for item in qualification_data.get("missing_information", ()))
        risks = tuple(str(item) for item in dossier_data.get("risks", ()))
        objections = tuple(str(item) for item in dossier_data.get("likely_objections", ()))
        triggers = dossier_data.get("triggers", ())
        pain_trigger = "\n".join(
            str(item.get("value", "")) for item in triggers if isinstance(item, dict)
        )
        readiness_score = self._readiness_score(qualification_data)
        self.cockpit.set_lead_detail(LeadDetail(
            lead.id, lead.company,
            f"Prioridade {lead.score}/100 · {score_context} · etapa {lead.stage.value}",
            lead.qualification or "Revisão comercial necessária", fact_lines or evidence_lines,
            "\n".join(str(item) for item in hypotheses) or lead.dossier,
            lead.next_action or "Revisar evidências e preparar abordagem",
            readiness=readiness_labels.get(readiness_status, readiness_status),
            readiness_score=readiness_score,
            gaps=gaps,
            decision_maker=decision_maker,
            pain_trigger=pain_trigger,
            meeting_script=meeting_questions,
            objections=objections,
            offer=self._lead_store.profile().offers,
            proposal=proposal_text,
            risks=risks,
        ))
        self._populate_context_lead(lead)

    @staticmethod
    def _readiness_score(payload: object) -> int | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get("readiness_score")
        if value is None or value == "":
            return None
        try:
            return max(0, min(100, int(float(value))))
        except (TypeError, ValueError):
            return None

    @Slot(str)
    def _run_cockpit_action(self, identifier: str) -> None:
        self._show_cockpit_lead(identifier)
        self._selected_lead_id = identifier
        self.tabs.setCurrentIndex(1)
        self.input.setText(
            "Prepare a próxima melhor ação para a oportunidade selecionada, distinguindo "
            "fatos observados, hipóteses e dados desconhecidos."
        )
        self.input.setFocus()

    @Slot(str, str)
    def _move_pipeline_lead(self, identifier: str, visual_stage: str) -> None:
        if self._lead_store is None:
            return
        stage = {
            "descobertos": LeadStage.NEW,
            "qualificados": LeadStage.QUALIFIED,
            "contato": LeadStage.CONTACTED,
            "discovery": LeadStage.DISCOVERY,
            "proposta": LeadStage.PROPOSAL,
            "fechamento": LeadStage.NEGOTIATION,
        }.get(visual_stage)
        if stage is None:
            return
        lead = self._lead_store.get(identifier)
        if lead is None:
            self.header_status.setText("●  Não foi possível localizar o lead")
            return
        if self._visual_pipeline_stage(lead.stage.value) == visual_stage:
            return
        if not self._lead_store.update(identifier, stage=stage):
            self.header_status.setText("●  Não foi possível persistir a movimentação")
            return
        self.header_status.setText(f"●  Lead movido para {stage.value.replace('_', ' ').title()}")
        self._refresh_leads()

    @Slot()
    def _show_selected_lead(self) -> None:
        row = self.lead_table.currentRow()
        if row < 0 or row >= len(getattr(self, "_visible_leads", [])):
            return
        lead = self._visible_leads[row]
        self._populate_context_lead(lead)

    def _populate_context_lead(self, lead) -> None:
        self.lead_editor.setVisible(True)
        self._selected_lead_id = lead.id
        stage_index = self.stage_editor.findData(lead.stage.value)
        self.stage_editor.setCurrentIndex(max(0, stage_index))
        self.next_action_input.setText(lead.next_action)
        self.save_lead_button.setEnabled(True)
        self.log_interaction_button.setEnabled(True)
        self.outreach_button.setEnabled(True)
        next_action = lead.next_action or "Preparar abordagem personalizada"
        self.lead_detail.setText(
            f"{lead.company}\n\nQualificação: {lead.qualification or 'Pendente'}\n"
            f"Etapa: {lead.stage.value.title()}\nScore: {lead.score}/100\n\n"
            f"Por que: {lead.score_explanation or 'Sem explicação'}\n\n"
            f"Dossiê: {lead.dossier or 'Pendente'}\n\n"
            f"Próxima ação: {next_action}\n"
            f"Prazo: {lead.next_action_at or 'Definir'}\n\nOrigem: {lead.source_url or 'Manual'}"
        )

    @Slot()
    def _save_selected_lead(self) -> None:
        identifier = getattr(self, "_selected_lead_id", "")
        if not identifier or self._lead_store is None:
            return
        stage = LeadStage(str(self.stage_editor.currentData()))
        self._lead_store.update(
            identifier, stage=stage, next_action=self.next_action_input.text()
        )
        self.header_status.setText("●  Pipeline atualizado")
        self._refresh_leads()

    @Slot()
    def _prepare_selected_outreach(self) -> None:
        identifier = getattr(self, "_selected_lead_id", "")
        lead = next(
            (item for item in getattr(self, "_visible_leads", []) if item.id == identifier),
            None,
        )
        if lead is None:
            return
        self.input.setText(
            "Crie um kit de abordagem individual para este lead usando somente os dados "
            f"verificados: empresa={lead.company}; nicho={lead.niche}; local={lead.location}; "
            f"Google={lead.rating:.1f} com {lead.review_count} avaliações; dossiê={lead.dossier}; "
            f"qualificação={lead.qualification}; motivos={lead.score_explanation}. "
            "Entregue: hipótese comercial sem tratá-la como fato, primeira mensagem curta, "
            "resposta caso aceite conversar, 4 perguntas de diagnóstico, oferta coerente com "
            "meu perfil comercial, dois follow-ups respeitosos e critérios para interromper. "
            "Não invente Instagram, decisor, faturamento, tratamento ou necessidade."
        )
        self.submit_message()

    @Slot()
    def _log_selected_interaction(self) -> None:
        identifier = getattr(self, "_selected_lead_id", "")
        if not identifier or self._lead_store is None:
            return
        outcome = str(self.interaction_outcome.currentData())
        stage = {
            "contato_realizado": LeadStage.CONTACTED,
            "sem_resposta": LeadStage.CONTACTED,
            "respondeu": LeadStage.REPLIED,
            "reuniao_marcada": LeadStage.MEETING,
            "sem_interesse": LeadStage.LOST,
        }[outcome]
        self._lead_store.record_interaction_and_transition(
            identifier, channel="WhatsApp", outcome=outcome, stage=stage
        )
        self.header_status.setText("●  Interação registrada")
        self._refresh_leads()

    @Slot()
    def _configure_commercial_profile(self) -> None:
        if self._lead_store is None:
            return
        profile = self._lead_store.profile()
        dialog = CommercialSettingsDialog(profile, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._lead_store.save_profile(dialog.commercial_profile())
            self.header_status.setText("●  Configuração atualizada")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self._update_sidebar_visibility()

    @Slot()
    def _update_sidebar_visibility(self) -> None:
        """Keep one usable primary navigation visible at every supported width."""
        if hasattr(self, "sidebar"):
            copilot_active = (
                hasattr(self, "workspace_stack") and self.workspace_stack.currentIndex() == 1
            )
            expanded = self.width() >= 1020
            self.sidebar.setVisible(expanded)
            self.rail.setVisible(not expanded)
            if hasattr(self, "nav_copilot"):
                self.nav_copilot.setChecked(copilot_active)
            if hasattr(self, "nav_consumers"):
                self.nav_consumers.setChecked(self.workspace_stack.currentIndex() == 2)
            if copilot_active:
                self.nav_overview.setChecked(False)
                self.nav_pipeline.setChecked(False)
                self.nav_campaigns.setChecked(False)
                self.nav_consumers.setChecked(False)
        if hasattr(self, "context_panel"):
            self.context_panel.setVisible(
                hasattr(self, "workspace_stack")
                and self.workspace_stack.currentIndex() == 1
                and self.width() >= 1180
            )

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
        if hasattr(self, "conversation_picker"):
            self.conversation_picker.blockSignals(True)
            self.conversation_picker.clear()
            for conversation in self._conversation_store.list():
                self.conversation_picker.addItem(
                    str(conversation.get("title", "Conversa")), conversation["id"]
                )
            picker_row = self.conversation_picker.findData(current_id)
            self.conversation_picker.setCurrentIndex(max(0, picker_row))
            self.conversation_picker.blockSignals(False)
            if hasattr(self, "nav_copilot"):
                self.nav_copilot.setText(f"▣   Conversas   {self.conversation_picker.count()}")

    @Slot(int)
    def _select_conversation_from_picker(self, index: int) -> None:
        if index < 0:
            return
        conversation_id = str(self.conversation_picker.itemData(index) or "")
        for row in range(self.conversation_list.count()):
            item = self.conversation_list.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole)) == conversation_id:
                self.conversation_list.setCurrentRow(row)
                break

    @Slot()
    def _new_conversation(self) -> None:
        conversation = self._conversation_store.create()
        self._active_conversation_id = conversation["id"]
        self._refresh_conversation_list()
        self.transcript.clear()
        self.input.setFocus()

    @Slot()
    def _delete_selected_conversation(self) -> None:
        item = self.conversation_list.currentItem()
        if item is None:
            return
        conversation_id = str(item.data(Qt.ItemDataRole.UserRole))
        conversation = self._conversation_store.get(conversation_id)
        if conversation is None:
            return
        title = str(conversation.get("title", "Conversa"))
        answer = QMessageBox.question(
            self,
            "Excluir conversa",
            f'Excluir permanentemente a conversa "{title}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not self._conversation_store.delete(conversation_id):
            return
        remaining = self._conversation_store.list()
        if not remaining:
            remaining = [self._conversation_store.create()]
        self._active_conversation_id = str(remaining[0]["id"])
        self._refresh_conversation_list()
        self._load_conversation(self._active_conversation_id)
        self.input.setFocus()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _select_conversation(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        conversation_id = str(current.data(Qt.ItemDataRole.UserRole))
        if conversation_id == self._active_conversation_id and self.transcript.is_empty():
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
        self.transcript.append_message(author, message, kind=kind)

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
        overlay_action.setChecked(self._overlay_enabled)
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
        self._set_busy(True)
        self.submit_requested.emit(message)

    @Slot(str)
    def _submit_quick_message(self, message: str) -> None:
        if not self.send.isEnabled():
            self.overlay.show_error("Aguarde a resposta atual antes de enviar outra mensagem.")
            return
        self._append_message("Você", message)
        self._request_origin = "overlay"
        self._set_busy(True)
        self.submit_requested.emit(message)

    @Slot(str)
    def _on_delta(self, response: str) -> None:
        # Never resize the main layout for every streamed token.
        self._thinking_timer.stop()
        self.status.setText("Gerando resposta…")

    @Slot(str)
    def _on_completed(self, response: str) -> None:
        self._refresh_leads()
        self._append_message("Kiara", response)
        if self._request_origin == "overlay":
            self.overlay.show_response(response)
        self._request_origin = "main"
        if self._voice_worker is not None:
            self.speak_requested.emit(response)

    @Slot()
    def _import_leads_csv(self) -> None:
        if self._lead_store is None:
            return
        path, _selected = QFileDialog.getOpenFileName(
            self, "Importar leads", "", "Arquivos CSV (*.csv)"
        )
        if not path:
            return
        try:
            imported, errors = LeadCsvService().import_file(self._lead_store, path)
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.critical(self, "Não foi possível importar", str(exc))
            return
        self._refresh_leads()
        detail = f"{imported} lead(s) importado(s)."
        if errors:
            detail += f"\n{len(errors)} linha(s) ignorada(s):\n" + "\n".join(errors[:8])
        QMessageBox.information(self, "Importação concluída", detail)

    @Slot()
    def _export_visible_leads_csv(self) -> None:
        if self._lead_store is None:
            return
        path, _selected = QFileDialog.getSaveFileName(
            self, "Exportar visão do pipeline", "leads-kiara.csv", "Arquivos CSV (*.csv)"
        )
        if not path:
            return
        if not path.casefold().endswith(".csv"):
            path += ".csv"
        try:
            count = LeadCsvService().export_file(
                self._lead_store, path, leads=self._visible_leads
            )
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível exportar", str(exc))
            return
        QMessageBox.information(
            self, "Exportação concluída", f"{count} lead(s) visível(is) exportado(s)."
        )

    def _receive_proactive_notice(self, notice: dict[str, object]) -> None:
        offer = notice.get("offer_text")
        if isinstance(offer, str) and offer.strip():
            self.proactive_received.emit(offer.strip())
            return
        payload = notice.get("payload", {})
        if isinstance(payload, dict):
            message = str(payload.get("title") or payload.get("message") or notice.get("source"))
        else:
            message = str(notice.get("source"))
        self.proactive_received.emit(message)

    @Slot(str)
    def _show_proactive_notice(self, message: str) -> None:
        self._append_message("Kiara", message, kind="notice")
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
        self._voice_active = True
        self._update_stop_visibility()
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
        self._set_busy(True)
        self.submit_requested.emit(message)

    @Slot()
    def _on_wake_detected(self) -> None:
        """Acknowledge a bare wake word, then listen once for the actual command."""
        if self._voice_worker is None or self._quitting:
            return
        self.status.setText("Ativada — aguardando comando")
        self.speak_requested.emit("Sim?")

    @Slot(str)
    def _set_voice_state(self, state: str) -> None:
        self.status.setText(state)
        normalized = state.casefold()
        self._voice_active = normalized != "pronta"
        self._update_stop_visibility()
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
        self._voice_active = False
        self._update_stop_visibility()
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
        self.status.setText("Analisando solicitação…")

    @Slot(bool)
    def _set_busy(self, busy: bool) -> None:
        self._request_busy = busy
        self._update_stop_visibility()
        self.send.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.delete_conversation_button.setEnabled(not busy)
        self.status.setProperty("busy", busy)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        if busy:
            self._thinking_step = 0
            self.status.setText("Analisando solicitação…")
            self._thinking_timer.start()
        else:
            self._thinking_timer.stop()
            self.status.setText(
                "A Kiara pode cometer erros. Valide informações importantes."
            )
        self.tray.setToolTip(f"Kiara — {'ocupada' if busy else 'pronta'}")
        self.overlay.set_state("ocupada" if busy else "pronta")
        if not busy and self.isActiveWindow():
            self.input.setFocus()

    def _update_stop_visibility(self) -> None:
        """Expose the emergency stop whenever work or voice activity is live."""
        self.stop.setVisible(self._request_busy or self._voice_active)

    @Slot()
    def stop_actions(self) -> None:
        if self._voice is not None:
            self._voice.cancel()
        self._kill_switch.trigger()
        self._voice_listen_pending = False
        self._voice_active = False
        self._update_stop_visibility()
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
            if not self._voice_thread.wait(15_000):
                logger.error("A thread de voz não encerrou no prazo; saída continuará sem exceção.")


def run_desktop(
    factory: Callable[[Callable[[str], bool]], tuple[AgentCore, KillSwitch]],
    argv: list[str] | None = None,
    voice: VoiceService | None = None,
    capture_seconds: float = 5.0,
) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Kiara")
    lock_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
    instance_lock = QLockFile(str(lock_path / "kiara-assistant.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(0):
        _activate_existing_kiara_window()
        return 0
    apply_kiara_theme(app)
    app.setWindowIcon(QIcon(str(_ui_asset_path("kiara-app-icon-v3.png"))))
    app.setQuitOnLastWindowClosed(False)
    confirmation = ConfirmationBridge()
    core, kill_switch = factory(confirmation.confirm)
    window = KiaraWindow(core, kill_switch, voice, capture_seconds)
    window.show()
    window.showNormal()
    window.raise_()
    window.activateWindow()
    app.aboutToQuit.connect(window.shutdown)
    try:
        return app.exec()
    finally:
        instance_lock.unlock()


def _activate_existing_kiara_window() -> None:
    """Bring the installed instance forward when the launcher is opened twice."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def activate(hwnd, _context):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            normalized = title.value.strip().casefold()
            if "kiara" in normalized:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return False
            return True

        user32.EnumWindows(callback_type(activate), 0)
    except Exception as exc:  # noqa: BLE001 - second-launch activation is best effort
        logger.warning("Não foi possível ativar a janela existente da Kiara: %s", exc)
