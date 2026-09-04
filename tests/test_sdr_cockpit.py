from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_cockpit_navigation_and_accessibility():
    _app()
    from app.ui.sdr_cockpit import SdrCockpit

    cockpit = SdrCockpit()
    assert cockpit.accessibleName() == "Cockpit de prospecção da Kiara"
    assert tuple(cockpit._nav_buttons) == ("hoje", "oportunidades", "pipeline", "resultados")
    assert all(button.accessibleName() for button in cockpit._nav_buttons.values())
    cockpit.set_current_section("resultados")
    assert cockpit.stack.currentWidget().accessibleName() == "Campanhas"
    with pytest.raises(ValueError, match="Seção desconhecida"):
        cockpit.set_current_section("chat")


def test_cockpit_presents_actions_opportunities_and_detail():
    _app()
    from PySide6.QtWidgets import QPushButton

    from app.ui.sdr_cockpit import (
        CockpitAction,
        CockpitMetric,
        LeadDetail,
        OpportunitySummary,
        SdrCockpit,
    )

    cockpit = SdrCockpit()
    cockpit.set_metrics([CockpitMetric("Follow-ups hoje", "3", "1 atrasado")])
    cockpit.set_actions([CockpitAction("lead-1", "Retomar Clínica Alfa", "Respondeu ontem", "Responder")])
    cockpit.set_opportunities(
        [OpportunitySummary("lead-1", "Clínica Alfa", "Odontologia", "Canoas", 84, "Respondeu")]
    )
    requested: list[str] = []
    cockpit.action_requested.connect(requested.append)
    action_button = cockpit.actions_host.findChild(QPushButton, "cockpitPrimaryAction")
    assert action_button is not None
    action_button.click()
    assert requested == ["lead-1"]

    selected: list[str] = []
    cockpit.opportunity_selected.connect(selected.append)
    cockpit.opportunity_table.selectRow(0)
    assert selected[-1] == "lead-1"
    cockpit.set_lead_detail(
        LeadDetail(
            "lead-1",
            "Clínica Alfa",
            "Boa reputação e canal próprio ausente",
            "Alta aderência",
            ("4,9 com 120 avaliações", "WhatsApp verificado"),
            "Pode depender de plataformas terceiras.",
            "Preparar abordagem personalizada",
        )
    )
    assert "120 avaliações" in cockpit.detail_panel.evidence.text()
    assert cockpit.detail_panel.action_button.isEnabled()
    assert cockpit.detail_panel.widgetResizable()
    assert "sem próxima ação" in cockpit.pipeline_summary.text().casefold()


def test_pipeline_renders_accessible_kanban_and_emits_selection():
    _app()
    from app.ui.sdr_cockpit import OpportunitySummary, PipelineOpportunityCard, SdrCockpit

    cockpit = SdrCockpit()
    cockpit.set_opportunities(
        [
            OpportunitySummary("new", "Aurora", "SaaS", "São Paulo", 62, "Descoberto"),
            OpportunitySummary("fit", "Nexo", "Saúde", "Recife", 81, "Qualificado"),
            OpportunitySummary("talk", "Atlas", "Varejo", "Curitiba", 74, "Respondeu"),
            OpportunitySummary("meet", "Lumina", "Tech", "Rio", 92, "Reunião agendada"),
        ]
    )
    assert {key: label.text() for key, label in cockpit.pipeline_counts.items()} == {
        "descobertos": "1",
        "qualificados": "1",
        "contato": "1",
        "discovery": "1",
        "proposta": "0",
        "fechamento": "0",
    }
    cards = cockpit.findChildren(PipelineOpportunityCard)
    assert len(cards) == 4
    assert all(card.accessibleName() and card.focusPolicy() for card in cards)
    selected: list[str] = []
    cockpit.opportunity_selected.connect(selected.append)
    cards[0].activated.emit("new")
    assert selected == ["new"]


def test_pipeline_has_empty_state_per_stage():
    _app()
    from PySide6.QtWidgets import QLabel

    from app.ui.sdr_cockpit import SdrCockpit

    cockpit = SdrCockpit()
    empty_states = cockpit.findChildren(QLabel, "cockpitKanbanEmpty")
    assert len(empty_states) == 6
    assert all(label.accessibleName().startswith("Nenhuma oportunidade") for label in empty_states)


def test_pipeline_forwards_stage_change_from_drop_column():
    from PySide6.QtWidgets import QApplication

    from app.ui.sdr_cockpit import PipelineDropColumn, SdrCockpit

    QApplication.instance() or QApplication([])
    cockpit = SdrCockpit()
    observed: list[tuple[str, str]] = []
    cockpit.stage_change_requested.connect(
        lambda lead_id, stage: observed.append((lead_id, stage))
    )
    proposal = next(
        column for column in cockpit.findChildren(PipelineDropColumn)
        if column.stage == "proposta"
    )

    proposal.stage_change_requested.emit("lead-42", proposal.stage)

    assert observed == [("lead-42", "proposta")]


def test_dashboard_filters_emit_and_charts_use_supplied_data():
    _app()
    from PySide6.QtWidgets import QLabel

    from app.ui.sdr_cockpit import SdrCockpit

    cockpit = SdrCockpit()
    observed: list[tuple[int, str]] = []
    cockpit.filters_changed.connect(lambda days, stage: observed.append((days, stage)))
    cockpit.period_filter.setCurrentIndex(1)
    cockpit.stage_filter.setCurrentIndex(2)
    assert observed[-1] == (30, "qualificados")

    cockpit.set_dashboard_data(
        performance=(("01/09", 1), ("02/09", 2), ("03/09", 3), ("04/09", 4),
                     ("05/09", 5), ("06/09", 6), ("07/09", 7)),
        sources=(("Google Maps", 3), ("Instagram", 1)),
        funnel=(("Descobertos", 2), ("Qualificados", 1)),
    )
    assert cockpit.performance_chart._values == (1, 2, 3, 4, 5, 6, 7)
    assert cockpit.performance_chart._labels[0] == "01/09"
    assert cockpit.funnel_donut._values == (2, 1)
    source_values = cockpit.findChildren(QLabel, "sourceValue")
    assert [label.text() for label in source_values] == ["3", "1"]
    assert "67%" in cockpit.funnel_legend.text()


def test_deal_room_presents_sales_ready_briefing():
    _app()
    from app.ui.sdr_cockpit import LeadDetail, SdrCockpit

    cockpit = SdrCockpit()
    cockpit.set_lead_detail(LeadDetail(
        identifier="sql-1",
        company="Clínica Aurora",
        headline="Expansão anunciada e baixa conversão digital",
        qualification="Fit alto; necessidade e timing confirmados",
        evidence=("Nova unidade anunciada no site", "Decisora confirmou o gargalo"),
        hypothesis="A captação atual pode não sustentar a expansão.",
        next_action="Realizar discovery com a diretora",
        readiness="Pronto para reunião",
        readiness_score=91,
        gaps=("Confirmar verba aprovada",),
        decision_maker="Marina Costa · Diretora · contato verificado",
        pain_trigger="Expansão em 60 dias; agenda com ociosidade",
        meeting_script=("Validar impacto da ociosidade", "Alinhar critérios de decisão"),
        objections=("Já usamos uma agência",),
        offer="Sprint de aquisição de 90 dias",
        proposal="Faixa aprovada: R$ 8–12 mil",
        risks=("Verba ainda não confirmada",),
    ))

    panel = cockpit.detail_panel
    assert panel.readiness.text() == "PRONTO PARA REUNIÃO"
    assert panel.readiness_score.text() == "91/100"
    assert "Marina Costa" in panel.decision_maker.text()
    assert "Validar impacto" in panel.meeting_script.text()
    assert "R$ 8–12 mil" in panel.offer.text()
    assert "Verba" in panel.risks.text()
    assert panel.action_button.isEnabled()


def test_deal_room_degrades_gracefully_for_legacy_detail():
    _app()
    from app.ui.sdr_cockpit import LeadDetail, SdrCockpit

    cockpit = SdrCockpit()
    cockpit.set_lead_detail(LeadDetail(
        "legacy-1", "Empresa Legada", "Cadastro antigo", "", (), "", ""
    ))

    panel = cockpit.detail_panel
    assert panel.readiness.text() == "EM ANÁLISE"
    assert panel.readiness_score.text() == "—"
    assert "ainda não identificado" in panel.decision_maker.text().casefold()
    assert "precisam ser confirmados" in panel.gaps.text().casefold()
    assert "não significa ausência" in panel.risks.text().casefold()
    assert not panel.action_button.isEnabled()
