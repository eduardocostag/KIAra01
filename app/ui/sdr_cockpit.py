from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.dashboard_widgets import FunnelDonut, WeeklyPerformanceChart

_PIPELINE_STAGES = (
    ("descobertos", "Descobertos"),
    ("qualificados", "Qualificados"),
    ("contato", "Contato"),
    ("discovery", "Discovery"),
    ("proposta", "Proposta"),
    ("fechamento", "Fechamento"),
)


def _pipeline_stage(stage: str) -> str:
    """Map integration labels to one stable visual pipeline stage."""
    normalized = stage.strip().casefold()
    if any(term in normalized for term in ("contrato", "assinatura", "negocia", "convert", "won")):
        return "fechamento"
    if any(term in normalized for term in ("proposta", "proposal")):
        return "proposta"
    if any(term in normalized for term in ("discovery", "reuni", "meeting", "agenda")):
        return "discovery"
    if any(term in normalized for term in ("contat", "responde", "abord", "contact")):
        return "contato"
    if any(term in normalized for term in ("qualif", "qualified")):
        return "qualificados"
    return "descobertos"


@dataclass(frozen=True, slots=True)
class CockpitMetric:
    label: str
    value: str
    context: str = ""


@dataclass(frozen=True, slots=True)
class CockpitAction:
    identifier: str
    title: str
    context: str
    action_label: str
    urgency: str = "normal"


@dataclass(frozen=True, slots=True)
class OpportunitySummary:
    identifier: str
    company: str
    niche: str
    location: str
    score: int
    stage: str
    next_action: str = ""
    readiness_score: int | None = None
    readiness: str = ""


class PipelineOpportunityCard(QFrame):
    """Compact opportunity card that supports mouse and keyboard activation."""

    activated = Signal(str)
    MIME_TYPE = "application/x-kiara-lead-id"

    def __init__(self, opportunity: OpportunitySummary) -> None:
        super().__init__(objectName="cockpitPipelineCard")
        self._identifier = opportunity.identifier
        self._drag_start = QPoint()
        self._dragging = False
        self.setProperty("stage", _pipeline_stage(opportunity.stage))
        self.setAccessibleName(
            f"{opportunity.company}, score {opportunity.score}. "
            f"{opportunity.next_action or 'Próxima ação não definida'}"
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        heading = QHBoxLayout()
        company = QLabel(opportunity.company, objectName="cockpitCardTitle")
        company.setWordWrap(True)
        displayed_score = (
            opportunity.readiness_score
            if opportunity.readiness_score is not None
            else opportunity.score
        )
        score = QLabel(str(displayed_score), objectName="cockpitPipelineScore")
        score.setAccessibleName(f"Prontidão {displayed_score}")
        heading.addWidget(company, 1)
        heading.addWidget(score)
        meta = " · ".join(value for value in (opportunity.niche, opportunity.location) if value)
        meta_label = QLabel(meta or "Sem segmento informado", objectName="cockpitMuted")
        meta_label.setWordWrap(True)
        next_action = QLabel(
            opportunity.next_action or "Definir próxima ação",
            objectName="cockpitPipelineNextAction",
        )
        next_action.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(7)
        layout.addLayout(heading)
        layout.addWidget(meta_label)
        layout.addWidget(next_action)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if not event.buttons() & Qt.MouseButton.LeftButton:
            return super().mouseMoveEvent(event)
        if (event.position().toPoint() - self._drag_start).manhattanLength() < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)
        mime = QMimeData()
        mime.setData(self.MIME_TYPE, self._identifier.encode("utf-8"))
        drag = QDrag(self)
        self._dragging = True
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
            self.activated.emit(self._identifier)
        self._dragging = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit(self._identifier)
            event.accept()
            return
        super().keyPressEvent(event)


class PipelineDropColumn(QFrame):
    """Accessible Kanban stage accepting Kiara opportunity cards."""

    stage_change_requested = Signal(str, str)

    def __init__(self, stage: str, label: str) -> None:
        super().__init__(objectName="cockpitPipelineColumn")
        self.stage = stage
        self.setAcceptDrops(True)
        self.setAccessibleName(f"Etapa {label}; solte oportunidades aqui")

    def dragEnterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.mimeData().hasFormat(PipelineOpportunityCard.MIME_TYPE):
            self.setProperty("dropActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._clear_drop_state()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        payload = bytes(event.mimeData().data(PipelineOpportunityCard.MIME_TYPE))
        identifier = payload.decode("utf-8", errors="ignore").strip()
        self._clear_drop_state()
        if identifier:
            self.stage_change_requested.emit(identifier, self.stage)
            event.acceptProposedAction()

    def _clear_drop_state(self) -> None:
        self.setProperty("dropActive", False)
        self.style().unpolish(self)
        self.style().polish(self)


@dataclass(frozen=True, slots=True)
class LeadDetail:
    identifier: str
    company: str
    headline: str
    qualification: str
    evidence: tuple[str, ...] = ()
    hypothesis: str = ""
    next_action: str = ""
    readiness: str = ""
    readiness_score: int | None = None
    gaps: tuple[str, ...] = ()
    decision_maker: str = ""
    pain_trigger: str = ""
    meeting_script: tuple[str, ...] = ()
    objections: tuple[str, ...] = ()
    offer: str = ""
    proposal: str = ""
    risks: tuple[str, ...] = ()


class MetricCard(QFrame):
    def __init__(self, metric: CockpitMetric) -> None:
        super().__init__(objectName="cockpitMetricCard")
        label = metric.label.casefold()
        if "vencid" in label or "atras" in label:
            tone = "amber"
        elif "oportun" in label or "qualif" in label:
            tone = "violet"
        elif "resposta" in label or "convers" in label:
            tone = "cyan"
        elif "reuni" in label or "receita" in label:
            tone = "emerald"
        else:
            tone = "cobalt"
        self.setProperty("tone", tone)
        self.setAccessibleName(f"{metric.label}: {metric.value}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        layout.addWidget(QLabel(metric.label.upper(), objectName="cockpitMetricLabel"))
        layout.addWidget(QLabel(metric.value, objectName="cockpitMetricValue"))
        if metric.context:
            context = QLabel(metric.context, objectName="cockpitMuted")
            context.setWordWrap(True)
            layout.addWidget(context)


class ActionCard(QFrame):
    activated = Signal(str)

    def __init__(self, action: CockpitAction) -> None:
        super().__init__(objectName="cockpitActionCard")
        self.setProperty("urgency", action.urgency)
        self.setAccessibleName(f"{action.title}. {action.context}")
        copy = QVBoxLayout()
        copy.setSpacing(3)
        title = QLabel(action.title, objectName="cockpitCardTitle")
        title.setWordWrap(True)
        context = QLabel(action.context, objectName="cockpitMuted")
        context.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(context)
        button = QPushButton(action.action_label, objectName="cockpitPrimaryAction")
        button.setAccessibleName(f"{action.action_label}: {action.title}")
        button.clicked.connect(lambda: self.activated.emit(action.identifier))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 12, 12)
        layout.addLayout(copy, 1)
        layout.addWidget(button)


class LeadDetailPanel(QScrollArea):
    action_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__(objectName="cockpitDetailPanel")
        self.setAccessibleName("Detalhes da oportunidade selecionada")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._identifier = ""
        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(18, 18, 18, 18)
        self._layout.setSpacing(12)
        self.title = QLabel("Selecione uma oportunidade", objectName="cockpitDetailTitle")
        self.title.setWordWrap(True)
        self.headline = QLabel(
            "Os sinais, hipóteses e a próxima melhor ação aparecerão aqui.",
            objectName="cockpitMuted",
        )
        self.headline.setWordWrap(True)
        readiness_row = QHBoxLayout()
        readiness_row.setSpacing(8)
        self.readiness = QLabel("EM ANÁLISE", objectName="dealReadinessBadge")
        self.readiness.setAccessibleName("Prontidão comercial")
        self.readiness_score = QLabel("—", objectName="dealReadinessScore")
        self.readiness_score.setAccessibleName("Pontuação de prontidão")
        readiness_row.addWidget(self.readiness)
        readiness_row.addStretch(1)
        readiness_row.addWidget(self.readiness_score)
        self._layout.addLayout(readiness_row)

        self.qualification = self._section("QUALIFICAÇÃO", "violet")
        self.evidence = self._section("FATOS VERIFICADOS", "emerald")
        self.hypothesis = self._section("HIPÓTESES COMERCIAIS", "amber")
        self.gaps = self._section("LACUNAS A VALIDAR", "cyan")
        self.decision_maker = self._section("DECISOR E AUTORIDADE", "cobalt")
        self.pain_trigger = self._section("DOR, IMPACTO E GATILHO", "violet")
        self.meeting_script = self._section("ROTEIRO DA REUNIÃO", "cyan")
        self.objections = self._section("OBJEÇÕES PROVÁVEIS", "amber")
        self.offer = self._section("OFERTA E PROPOSTA-BASE", "emerald")
        self.risks = self._section("RISCOS E DESQUALIFICADORES", "danger")
        self.next_action = self._section("PRÓXIMA MELHOR AÇÃO", "cobalt")
        self.action_button = QPushButton("Preparar próxima ação", objectName="cockpitPrimaryAction")
        self.action_button.setAccessibleName("Executar a próxima ação da oportunidade")
        self.action_button.setEnabled(False)
        self.action_button.clicked.connect(self._request_action)
        self._layout.insertWidget(0, self.title)
        self._layout.insertWidget(1, self.headline)
        self.action_button.hide()
        self._layout.addStretch(1)
        self.setWidget(content)

    def _section(self, title: str, tone: str) -> QLabel:
        card = QFrame(objectName="dealRoomSection")
        card.setProperty("tone", tone)
        card.setAccessibleName(title.title())
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 11)
        card_layout.setSpacing(6)
        card_layout.addWidget(QLabel(title, objectName="dealRoomSectionLabel"))
        body = QLabel("—", objectName="cockpitDetailBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(body)
        self._layout.addWidget(card)
        return body

    @staticmethod
    def _bullets(items: Iterable[str], fallback: str) -> str:
        cleaned = tuple(str(item).strip() for item in items if str(item).strip())
        return "\n".join(f"• {item}" for item in cleaned) or fallback

    def show_detail(self, detail: LeadDetail) -> None:
        self._identifier = detail.identifier
        self.title.setText(detail.company)
        self.headline.setText(detail.headline or "Oportunidade em revisão")
        readiness = detail.readiness.strip() or "Em análise"
        self.readiness.setText(readiness.upper())
        self.readiness.setProperty("state", readiness.casefold().replace(" ", "_"))
        self.readiness.style().unpolish(self.readiness)
        self.readiness.style().polish(self.readiness)
        score = detail.readiness_score
        self.readiness_score.setText(f"{max(0, min(100, score))}/100" if score is not None else "—")
        self.qualification.setText(detail.qualification or "Ainda não qualificada")
        self.evidence.setText(self._bullets(
            detail.evidence, "Nenhum fato verificado registrado. Não usar como argumento ainda."
        ))
        self.hypothesis.setText(
            detail.hypothesis or "Nenhuma hipótese formulada. Validar antes de apresentar como fato."
        )
        self.gaps.setText(self._bullets(
            detail.gaps, "Decisor, necessidade, urgência e capacidade ainda precisam ser confirmados."
        ))
        self.decision_maker.setText(detail.decision_maker or "Decisor ainda não identificado.")
        self.pain_trigger.setText(detail.pain_trigger or "Dor e gatilho de compra ainda não comprovados.")
        self.meeting_script.setText(self._bullets(
            detail.meeting_script, "Roteiro ainda não preparado. Qualifique antes de agendar."
        ))
        self.objections.setText(self._bullets(
            detail.objections, "Nenhuma objeção mapeada; confirmar durante a discovery."
        ))
        offer_text = "\n\n".join(value for value in (detail.offer, detail.proposal) if value.strip())
        self.offer.setText(offer_text or "Oferta ainda não configurada para esta oportunidade.")
        self.risks.setText(self._bullets(
            detail.risks, "Nenhum risco registrado; isso não significa ausência de risco."
        ))
        self.next_action.setText(detail.next_action or "Defina uma próxima ação.")
        self.action_button.setEnabled(bool(detail.next_action))

    def clear_detail(self) -> None:
        self._identifier = ""
        self.title.setText("Selecione uma oportunidade")
        self.headline.setText("Os sinais, hipóteses e a próxima melhor ação aparecerão aqui.")
        self.readiness.setText("EM ANÁLISE")
        self.readiness.setProperty("state", "em_análise")
        self.readiness.style().unpolish(self.readiness)
        self.readiness.style().polish(self.readiness)
        self.readiness_score.setText("—")
        for label in (
            self.qualification, self.evidence, self.hypothesis, self.gaps,
            self.decision_maker, self.pain_trigger, self.meeting_script,
            self.objections, self.offer, self.risks, self.next_action,
        ):
            label.setText("—")
        self.action_button.setEnabled(False)

    def _request_action(self) -> None:
        if self._identifier:
            self.action_requested.emit(self._identifier)


class SdrCockpit(QWidget):
    """Cockpit SDR integrável; não conhece o desktop, o orbe ou a persistência."""

    navigation_changed = Signal(str)
    opportunity_selected = Signal(str)
    action_requested = Signal(str)
    stage_change_requested = Signal(str, str)
    filters_changed = Signal(int, str)
    import_requested = Signal()
    export_requested = Signal()

    _SECTIONS = (
        ("hoje", "Hoje"),
        ("oportunidades", "Oportunidades"),
        ("pipeline", "Pipeline"),
        ("resultados", "Resultados"),
    )

    def __init__(self) -> None:
        super().__init__(objectName="sdrCockpit")
        self.setAccessibleName("Cockpit de prospecção da Kiara")
        self._nav_buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self._actions: tuple[CockpitAction, ...] = ()
        self._opportunities: tuple[OpportunitySummary, ...] = ()
        self._build_ui()
        self.set_current_section("hoje")

    def _build_ui(self) -> None:
        navigation = QFrame(objectName="cockpitNavigation")
        nav_layout = QVBoxLayout(navigation)
        nav_layout.setContentsMargins(12, 16, 12, 16)
        nav_layout.setSpacing(6)
        brand = QLabel("KIARA SDR", objectName="cockpitBrand")
        brand.setAccessibleName("Kiara SDR")
        nav_layout.addWidget(brand)
        nav_layout.addSpacing(12)
        for key, label in self._SECTIONS:
            button = QPushButton(label, objectName="cockpitNavButton")
            button.setCheckable(True)
            button.setAccessibleName(f"Abrir {label}")
            button.clicked.connect(lambda _checked=False, section=key: self.set_current_section(section))
            nav_layout.addWidget(button)
            self._nav_buttons[key] = button
        nav_layout.addStretch(1)

        self.stack = QStackedWidget(objectName="cockpitPages")
        self.stack.setAccessibleName("Área de trabalho SDR")
        self._pages["hoje"] = self._build_today_page()
        self._pages["oportunidades"] = self._build_opportunities_page()
        self._pages["pipeline"] = self._build_pipeline_page()
        self._pages["resultados"] = self._build_results_page()
        for key, _label in self._SECTIONS:
            self.stack.addWidget(self._pages[key])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(navigation)
        layout.addWidget(self.stack, 1)

    @staticmethod
    def _page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setAccessibleName(title)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        heading = QLabel(title, objectName="cockpitPageTitle")
        heading.setAccessibleName(title)
        description = QLabel(subtitle, objectName="cockpitMuted")
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)
        return page, layout

    def _build_today_page(self) -> QWidget:
        page = QWidget(objectName="overviewPage")
        page.setAccessibleName("Visão geral")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        heading_copy = QVBoxLayout()
        heading_copy.setSpacing(2)
        heading = QLabel("Visão geral", objectName="cockpitPageTitle")
        heading.setAccessibleName("Visão geral")
        heading_copy.addWidget(heading)
        heading_copy.addWidget(QLabel(
            "Acompanhe o desempenho da sua operação comercial.", objectName="cockpitMuted"
        ))
        header.addLayout(heading_copy)
        header.addStretch(1)
        self.period_filter = QComboBox(objectName="periodFilter")
        self.period_filter.setAccessibleName("Selecionar período do resumo")
        for label, days in (("Últimos 7 dias", 7), ("Últimos 30 dias", 30),
                            ("Últimos 90 dias", 90), ("Todo o período", 0)):
            self.period_filter.addItem(label, days)
        self.stage_filter = QComboBox(objectName="stageFilter")
        self.stage_filter.setAccessibleName("Filtrar visão geral por etapa")
        for label, value in (("Todas as etapas", ""), ("Descobertos", "descobertos"),
                             ("Qualificados", "qualificados"), ("Contato", "contato"),
                             ("Discovery", "discovery"), ("Proposta", "proposta"),
                             ("Fechamento", "fechamento")):
            self.stage_filter.addItem(label, value)
        self.period_filter.currentIndexChanged.connect(self._emit_filters)
        self.stage_filter.currentIndexChanged.connect(self._emit_filters)
        header.addWidget(self.period_filter)
        header.addWidget(self.stage_filter)
        layout.addLayout(header)
        self.metrics_host = QWidget(objectName="cockpitMetrics")
        self.metrics_layout = QHBoxLayout(self.metrics_host)
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setSpacing(10)
        layout.addWidget(self.metrics_host)
        dashboard = QGridLayout()
        dashboard.setContentsMargins(0, 0, 0, 0)
        dashboard.setHorizontalSpacing(10)
        dashboard.setVerticalSpacing(10)

        actions_panel = QFrame(objectName="dashboardPanel")
        actions_panel_layout = QVBoxLayout(actions_panel)
        actions_panel_layout.addWidget(QLabel("Próximas ações", objectName="dashboardPanelTitle"))
        self.actions_host = QWidget(objectName="cockpitActions")
        self.actions_layout = QVBoxLayout(self.actions_host)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(5)
        actions_panel_layout.addWidget(self.actions_host, 1)

        performance = QFrame(objectName="dashboardPanel")
        performance_layout = QVBoxLayout(performance)
        performance_layout.addWidget(
            QLabel("Desempenho semanal", objectName="dashboardPanelTitle")
        )
        self.performance_chart = WeeklyPerformanceChart()
        performance_layout.addWidget(self.performance_chart, 1)

        sources = QFrame(objectName="dashboardPanel")
        sources_layout = QVBoxLayout(sources)
        sources_layout.addWidget(QLabel("Top fontes de leads", objectName="dashboardPanelTitle"))
        self.sources_layout = QVBoxLayout()
        self.sources_layout.setContentsMargins(0, 0, 0, 0)
        sources_layout.addLayout(self.sources_layout, 1)

        funnel = QFrame(objectName="dashboardPanel")
        funnel_layout = QVBoxLayout(funnel)
        funnel_layout.addWidget(QLabel("Status do funil", objectName="dashboardPanelTitle"))
        funnel_body = QHBoxLayout()
        self.funnel_donut = FunnelDonut()
        funnel_body.addWidget(self.funnel_donut, 1)
        self.funnel_legend = QLabel("Sem dados no período", objectName="funnelLegend")
        self.funnel_legend.setWordWrap(True)
        funnel_body.addWidget(self.funnel_legend, 1)
        funnel_layout.addLayout(funnel_body, 1)

        dashboard.addWidget(actions_panel, 0, 0)
        dashboard.addWidget(performance, 0, 1)
        dashboard.addWidget(sources, 1, 0)
        dashboard.addWidget(funnel, 1, 1)
        dashboard.setColumnStretch(0, 11)
        dashboard.setColumnStretch(1, 9)
        dashboard.setRowStretch(0, 6)
        dashboard.setRowStretch(1, 4)
        layout.addLayout(dashboard, 1)
        return page

    def _emit_filters(self) -> None:
        self.filters_changed.emit(
            int(self.period_filter.currentData() or 0),
            str(self.stage_filter.currentData() or ""),
        )

    def set_dashboard_data(
        self,
        *,
        performance: Iterable[tuple[str, int]],
        sources: Iterable[tuple[str, int]],
        funnel: Iterable[tuple[str, int]],
    ) -> None:
        performance_values = tuple(performance)
        self.performance_chart.set_series(
            (value for _label, value in performance_values),
            (label for label, _value in performance_values),
        )
        self._clear_layout(self.sources_layout)
        source_values = tuple(sources)
        maximum = max((value for _label, value in source_values), default=1)
        tones = ("violet", "cyan", "emerald", "amber")
        if not source_values:
            self.sources_layout.addWidget(QLabel("Sem fontes no período", objectName="cockpitMuted"))
        for index, (label, value) in enumerate(source_values):
            row = QHBoxLayout()
            row.addWidget(QLabel(label, objectName="sourceLabel"))
            bar = QFrame(objectName="sourceBar")
            bar.setProperty("tone", tones[index % len(tones)])
            bar.setFixedWidth(max(12, round(150 * value / maximum)))
            row.addWidget(bar)
            row.addStretch(1)
            row.addWidget(QLabel(str(value), objectName="sourceValue"))
            self.sources_layout.addLayout(row)
        funnel_values = tuple(funnel)
        self.funnel_donut.set_values(value for _label, value in funnel_values)
        total = sum(value for _label, value in funnel_values)
        self.funnel_legend.setText(
            "\n".join(
                f"●  {label}: {((value / total) * 100 if total else 0):.0f}% · {value}"
                for label, value in funnel_values
            ) or "Sem dados no período"
        )

    def _build_opportunities_page(self) -> QWidget:
        page, layout = self._page(
            "Oportunidades", "Compare sinais, confiança e próxima ação antes de abordar."
        )
        body = QHBoxLayout()
        self.opportunity_body = body
        self.opportunity_table = QTableWidget(0, 6, objectName="cockpitOpportunityTable")
        self.opportunity_table.setAccessibleName("Lista de oportunidades comerciais")
        self.opportunity_table.setHorizontalHeaderLabels(
            ["Empresa", "Nicho", "Local", "Prontidão", "Etapa", "Próxima ação"]
        )
        self.opportunity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.opportunity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.opportunity_table.verticalHeader().hide()
        header = self.opportunity_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.opportunity_table.setMinimumHeight(230)
        self.opportunity_table.itemSelectionChanged.connect(self._emit_selected_opportunity)
        self.detail_panel = LeadDetailPanel()
        self.detail_panel.action_requested.connect(self.action_requested)
        body.addWidget(self.opportunity_table, 3)
        body.addWidget(self.detail_panel, 2)
        layout.addLayout(body, 1)
        self.deal_action_button = QPushButton(
            "Preparar próxima ação", objectName="cockpitPrimaryAction"
        )
        self.deal_action_button.setAccessibleName(
            "Preparar a próxima ação da oportunidade no Copiloto"
        )
        self.deal_action_button.setEnabled(False)
        self.deal_action_button.clicked.connect(self.detail_panel._request_action)
        layout.addWidget(self.deal_action_button)
        return page

    def _build_pipeline_page(self) -> QWidget:
        page, layout = self._page(
            "Pipeline", "Acompanhe o avanço das oportunidades sem perder a próxima ação."
        )
        actions = QHBoxLayout()
        actions.addStretch(1)
        import_button = QPushButton("Importar CSV", objectName="cockpitSecondaryAction")
        import_button.setAccessibleName("Importar leads de um arquivo CSV")
        import_button.clicked.connect(self.import_requested)
        export_button = QPushButton("Exportar visão", objectName="cockpitSecondaryAction")
        export_button.setAccessibleName("Exportar os leads visíveis em CSV")
        export_button.clicked.connect(self.export_requested)
        actions.addWidget(import_button)
        actions.addWidget(export_button)
        layout.addLayout(actions)
        self.pipeline_summary = QLabel(
            "Nenhuma oportunidade no pipeline.", objectName="cockpitEmptyState"
        )
        self.pipeline_summary.setAccessibleName("Resumo do pipeline")
        self.pipeline_summary.setWordWrap(True)
        self.pipeline_summary.setAlignment(Qt.AlignmentFlag.AlignTop)

        pipeline_scroll = QScrollArea(objectName="cockpitPipelineScroll")
        pipeline_scroll.setAccessibleName("Quadro Kanban do pipeline")
        pipeline_scroll.setWidgetResizable(True)
        pipeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        pipeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pipeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        board = QWidget(objectName="cockpitPipelineBoard")
        board.setMinimumWidth(1380)
        board_layout = QHBoxLayout(board)
        board_layout.setContentsMargins(0, 4, 0, 4)
        board_layout.setSpacing(12)
        self.pipeline_columns: dict[str, QVBoxLayout] = {}
        self.pipeline_counts: dict[str, QLabel] = {}
        for key, label in _PIPELINE_STAGES:
            column = PipelineDropColumn(key, label)
            column.stage_change_requested.connect(self.stage_change_requested)
            column.setMinimumWidth(210)
            column.setAccessibleName(f"Etapa {label}")
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(12, 12, 12, 12)
            column_layout.setSpacing(9)
            header = QHBoxLayout()
            title = QLabel(label.upper(), objectName="cockpitSectionLabel")
            count = QLabel("0", objectName="cockpitPipelineCount")
            count.setAccessibleName(f"0 oportunidades em {label}")
            header.addWidget(title, 1)
            header.addWidget(count)
            cards = QVBoxLayout()
            cards.setSpacing(8)
            column_layout.addLayout(header)
            column_layout.addLayout(cards)
            column_layout.addStretch(1)
            board_layout.addWidget(column, 1)
            self.pipeline_columns[key] = cards
            self.pipeline_counts[key] = count
        pipeline_scroll.setWidget(board)
        layout.addWidget(self.pipeline_summary)
        layout.addWidget(pipeline_scroll, 1)
        self._refresh_pipeline_board()
        return page

    def _build_results_page(self) -> QWidget:
        page, layout = self._page(
            "Campanhas", "Acompanhe operações ativas, cadências, respostas e conversões."
        )
        active = QFrame(objectName="dashboardPanel")
        active_layout = QVBoxLayout(active)
        active_layout.addWidget(QLabel("CAMPANHA ATIVA", objectName="cockpitEyebrow"))
        active_layout.addWidget(QLabel("Operação comercial", objectName="dashboardPanelTitle"))
        active_layout.addWidget(QLabel(
            "Pesquisa, qualificação e abordagem assistida pela Kiara.", objectName="cockpitMuted"
        ))
        layout.addWidget(active)
        self.results_summary = QLabel(
            "Os resultados aparecerão após o registro das primeiras interações.",
            objectName="cockpitEmptyState",
        )
        self.results_summary.setAccessibleName("Resumo de resultados comerciais")
        self.results_summary.setWordWrap(True)
        self.results_summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.results_summary, 1)
        return page

    def set_current_section(self, section: str) -> None:
        if section not in self._pages:
            raise ValueError(f"Seção desconhecida: {section}")
        self.stack.setCurrentWidget(self._pages[section])
        for key, button in self._nav_buttons.items():
            button.setChecked(key == section)
        self.navigation_changed.emit(section)

    def set_metrics(self, metrics: Iterable[CockpitMetric]) -> None:
        self._clear_layout(self.metrics_layout)
        values = tuple(metrics)
        if not values:
            self.metrics_layout.addWidget(QLabel("Sem métricas disponíveis", objectName="cockpitMuted"))
            return
        for metric in values:
            self.metrics_layout.addWidget(MetricCard(metric), 1)

    def set_actions(self, actions: Iterable[CockpitAction]) -> None:
        self._clear_layout(self.actions_layout)
        self._actions = tuple(actions)
        if not self._actions:
            for title, detail in (
                ("Iniciar uma nova busca", "Defina nicho, cidade e critérios no Copiloto"),
                ("Revisar o perfil comercial", "Confirme ICP, oferta e regras de qualificação"),
                ("Importar ou conectar uma fonte", "Adicione leads sem alterar os dados originais"),
            ):
                row = QFrame(objectName="dashboardQuickAction")
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(10, 8, 10, 8)
                row_layout.setSpacing(2)
                row_layout.addWidget(QLabel(title, objectName="cockpitCardTitle"))
                row_layout.addWidget(QLabel(detail, objectName="cockpitMuted"))
                self.actions_layout.addWidget(row)
            self.actions_layout.addStretch(1)
            return
        for action in self._actions:
            card = ActionCard(action)
            card.activated.connect(self.action_requested)
            self.actions_layout.addWidget(card)
        self.actions_layout.addStretch(1)

    def set_opportunities(self, opportunities: Iterable[OpportunitySummary]) -> None:
        self._opportunities = tuple(opportunities)
        self.opportunity_table.setRowCount(len(self._opportunities))
        for row, opportunity in enumerate(self._opportunities):
            values = (
                opportunity.company,
                opportunity.niche,
                opportunity.location,
                str(
                    opportunity.readiness_score
                    if opportunity.readiness_score is not None
                    else opportunity.score
                ),
                opportunity.stage,
                opportunity.next_action or "Definir próxima ação",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, opportunity.identifier)
                self.opportunity_table.setItem(row, column, item)
        self._refresh_pipeline_summary()
        self._refresh_pipeline_board()
        if not self._opportunities:
            self.detail_panel.clear_detail()
            self.deal_action_button.setEnabled(False)

    def set_lead_detail(self, detail: LeadDetail) -> None:
        self.detail_panel.show_detail(detail)
        self.deal_action_button.setEnabled(bool(detail.next_action))
        if detail.readiness.strip().casefold() in {"sql", "sql pronto", "pronto para reunião"}:
            self.deal_action_button.setText("Preparar reunião")
        else:
            self.deal_action_button.setText("Completar qualificação")

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        if hasattr(self, "opportunity_body"):
            direction = (
                QBoxLayout.Direction.TopToBottom
                if self.width() < 1180
                else QBoxLayout.Direction.LeftToRight
            )
            self.opportunity_body.setDirection(direction)

    def set_results_summary(self, text: str) -> None:
        self.results_summary.setText(text or "Nenhum resultado disponível.")

    def _emit_selected_opportunity(self) -> None:
        row = self.opportunity_table.currentRow()
        if 0 <= row < len(self._opportunities):
            self.opportunity_selected.emit(self._opportunities[row].identifier)

    def _refresh_pipeline_summary(self) -> None:
        if not self._opportunities:
            self.pipeline_summary.setText("Nenhuma oportunidade no pipeline.")
            return
        stages: dict[str, int] = {}
        missing_action = 0
        for opportunity in self._opportunities:
            stages[opportunity.stage] = stages.get(opportunity.stage, 0) + 1
            missing_action += not bool(opportunity.next_action)
        lines = [f"{stage}: {count}" for stage, count in sorted(stages.items())]
        if missing_action:
            lines.append(f"Atenção: {missing_action} sem próxima ação definida")
        self.pipeline_summary.setText("\n".join(lines))

    def _refresh_pipeline_board(self) -> None:
        grouped: dict[str, list[OpportunitySummary]] = {key: [] for key, _ in _PIPELINE_STAGES}
        for opportunity in self._opportunities:
            grouped[_pipeline_stage(opportunity.stage)].append(opportunity)

        labels = dict(_PIPELINE_STAGES)
        for key, cards_layout in self.pipeline_columns.items():
            self._clear_layout(cards_layout)
            opportunities = grouped[key]
            count = self.pipeline_counts[key]
            count.setText(str(len(opportunities)))
            count.setAccessibleName(f"{len(opportunities)} oportunidades em {labels[key]}")
            if not opportunities:
                empty = QLabel("Nenhuma oportunidade nesta etapa", objectName="cockpitKanbanEmpty")
                empty.setAccessibleName(f"Nenhuma oportunidade em {labels[key]}")
                empty.setWordWrap(True)
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cards_layout.addWidget(empty)
                continue
            for opportunity in opportunities:
                card = PipelineOpportunityCard(opportunity)
                card.activated.connect(self.opportunity_selected)
                cards_layout.addWidget(card)

    @staticmethod
    def _clear_layout(layout: QHBoxLayout | QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
