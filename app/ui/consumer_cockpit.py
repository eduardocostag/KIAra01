from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class ConsumerSummary:
    identifier: str
    name: str
    platform: str
    intent_score: int
    stage: str
    consent: str
    next_action: str = ""


@dataclass(frozen=True, slots=True)
class CustomerDetail:
    identifier: str
    name: str
    readiness: str = "Precisa qualificar"
    readiness_score: int = 0
    origin: str = ""
    declared_need: str = ""
    intent_signals: tuple[str, ...] = ()
    consent: str = "Não confirmado"
    allowed_channels: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    objections: tuple[str, ...] = ()
    recommended_offer: str = ""
    suggested_message: str = ""
    next_action: str = ""


class CustomerRoom(QFrame):
    action_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__(objectName="customerRoom")
        self._identifier = ""
        self._sections: list[QFrame] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        self.name = QLabel("Selecione um consumidor", objectName="customerRoomTitle")
        self.name.setWordWrap(True)
        layout.addWidget(self.name)
        readiness_row = QHBoxLayout()
        self.readiness = QLabel("PRECISA QUALIFICAR", objectName="consumerReadinessBadge")
        self.readiness_score = QLabel("—", objectName="dealReadinessScore")
        readiness_row.addWidget(self.readiness)
        readiness_row.addStretch(1)
        readiness_row.addWidget(self.readiness_score)
        layout.addLayout(readiness_row)
        self.origin = self._section(layout, "ORIGEM E JORNADA", "cobalt")
        self.need = self._section(layout, "NECESSIDADE DECLARADA", "violet")
        self.signals = self._section(layout, "SINAIS DE INTENÇÃO", "emerald")
        self.consent = self._section(layout, "CONSENTIMENTO E CANAIS", "cyan")
        self.unknowns = self._section(layout, "LACUNAS A CONFIRMAR", "amber")
        self.objections = self._section(layout, "OBJEÇÕES", "violet")
        self.offer = self._section(layout, "OFERTA RECOMENDADA", "emerald")
        self.message = self._section(layout, "MENSAGEM PREPARADA", "cobalt")
        self.next_action = self._section(layout, "PRÓXIMA AÇÃO", "cyan")
        layout.addStretch(1)

    def _section(self, layout: QVBoxLayout, title: str, tone: str) -> QLabel:
        card = QFrame(objectName="customerRoomSection")
        card.setProperty("tone", tone)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 9, 12, 10)
        card_layout.addWidget(QLabel(title, objectName="dealRoomSectionLabel"))
        body = QLabel("—", objectName="cockpitDetailBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(body)
        layout.addWidget(card)
        self._sections.append(card)
        card.hide()
        return body

    @staticmethod
    def _bullets(values: Iterable[str], fallback: str) -> str:
        items = tuple(str(value).strip() for value in values if str(value).strip())
        return "\n".join(f"• {item}" for item in items) or fallback

    def show_detail(self, detail: CustomerDetail) -> None:
        self._identifier = detail.identifier
        self.name.setText(detail.name)
        self.readiness.setText(detail.readiness.upper())
        state = detail.readiness.casefold().replace(" ", "_")
        self.readiness.setProperty("state", state)
        self.readiness.style().unpolish(self.readiness)
        self.readiness.style().polish(self.readiness)
        self.readiness_score.setText(f"{max(0, min(100, detail.readiness_score))}/100")
        self.origin.setText(detail.origin or "Origem ainda não registrada.")
        self.need.setText(detail.declared_need or "Necessidade ainda não declarada.")
        self.signals.setText(self._bullets(detail.intent_signals, "Nenhum sinal forte de intenção."))
        channels = ", ".join(detail.allowed_channels) or "nenhum canal autorizado"
        self.consent.setText(f"{detail.consent} · {channels}")
        self.unknowns.setText(self._bullets(detail.unknowns, "Sem lacunas críticas registradas."))
        self.objections.setText(self._bullets(detail.objections, "Nenhuma objeção registrada."))
        self.offer.setText(detail.recommended_offer or "Oferta depende da qualificação.")
        self.message.setText(
            detail.suggested_message or "Mensagem indisponível até existir canal autorizado."
        )
        self.next_action.setText(detail.next_action or "Continuar qualificação.")
        for section in self._sections:
            section.show()


class ConsumerCockpit(QWidget):
    consumer_selected = Signal(str)
    action_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__(objectName="consumerCockpit")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(QLabel("CONSUMER INTELLIGENCE", objectName="cockpitEyebrow"))
        layout.addWidget(QLabel("Consumidores", objectName="cockpitPageTitle"))
        subtitle = QLabel(
            "Sinais orgânicos para revisão e pessoas consentidas para reunião ou checkout.",
            objectName="cockpitMuted",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        body = QHBoxLayout()
        body.setSpacing(12)
        self.table = QTableWidget(0, 6, objectName="consumerTable")
        self.table.setAccessibleName("Consumidores captados com consentimento")
        self.table.setHorizontalHeaderLabels(
            ["Pessoa", "Origem", "Intenção", "Etapa", "Consentimento", "Próxima ação"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._emit_selection)
        empty = QFrame(objectName="consumerEmptyState")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(34, 34, 34, 34)
        empty_layout.addStretch(1)
        empty_layout.addWidget(QLabel("Sua fila B2C começa aqui", objectName="consumerEmptyTitle"))
        empty_copy = QLabel(
            "Conecte formulários oficiais do Instagram, Facebook, LinkedIn ou TikTok. "
            "A Kiara só exibirá pessoas identificadas com consentimento e separará "
            "interesse casual de intenção real de compra.",
            objectName="cockpitMuted",
        )
        empty_copy.setWordWrap(True)
        empty_layout.addWidget(empty_copy)
        empty_rules = QLabel(
            "✓ origem verificável   ✓ consentimento registrado\n"
            "✓ sinais de intenção   ✓ próxima ação recomendada",
            objectName="consumerEmptyRules",
        )
        empty_rules.setWordWrap(True)
        empty_layout.addWidget(empty_rules)
        empty_layout.addStretch(1)
        self.list_stack = QStackedWidget(objectName="consumerListStack")
        self.list_stack.addWidget(empty)
        self.list_stack.addWidget(self.table)
        self.room = CustomerRoom()
        self.room.setMinimumWidth(330)
        self.room_scroll = QScrollArea(objectName="customerRoomScroll")
        self.room_scroll.setAccessibleName("Dossiê do consumidor selecionado")
        self.room_scroll.setWidgetResizable(True)
        self.room_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.room_scroll.setWidget(self.room)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, objectName="consumerSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.list_stack)
        self.splitter.addWidget(self.room_scroll)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        body.addWidget(self.splitter)
        layout.addLayout(body, 1)
        self.action = QPushButton("Preparar próxima ação", objectName="cockpitPrimaryAction")
        self.action.setEnabled(False)
        self.action.clicked.connect(self._request_action)
        layout.addWidget(self.action)
        self._items: tuple[ConsumerSummary, ...] = ()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        compact = self.width() < 980
        orientation = Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal
        if self.splitter.orientation() != orientation:
            self.splitter.setOrientation(orientation)
        self.table.setMinimumHeight(220 if compact else 0)
        self.table.setMaximumHeight(280 if compact else 16_777_215)

    def set_consumers(self, consumers: Iterable[ConsumerSummary]) -> None:
        self._items = tuple(consumers)
        self.list_stack.setCurrentIndex(1 if self._items else 0)
        self.table.setRowCount(len(self._items))
        for row, consumer in enumerate(self._items):
            values = (
                consumer.name, consumer.platform, str(consumer.intent_score), consumer.stage,
                consumer.consent, consumer.next_action or "Qualificar consumidor",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, consumer.identifier)
                self.table.setItem(row, column, item)

    def set_customer_detail(self, detail: CustomerDetail) -> None:
        self.room.show_detail(detail)
        self.action.setEnabled(bool(detail.next_action and detail.allowed_channels))
        self.action.setText(
            "Preparar checkout" if detail.readiness.casefold() == "pronto para comprar"
            else "Preparar próxima ação"
        )

    def _emit_selection(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self._items):
            self.consumer_selected.emit(self._items[row].identifier)

    def _request_action(self) -> None:
        if self.room._identifier:
            self.action_requested.emit(self.room._identifier)
