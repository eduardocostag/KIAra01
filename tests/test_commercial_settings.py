from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_commercial_settings_is_guided_and_round_trips_profile() -> None:
    from PySide6.QtWidgets import QApplication

    from app.leads import CommercialProfile
    from app.ui.commercial_settings import CommercialSettingsDialog

    QApplication.instance() or QApplication([])
    original = CommercialProfile(
        business_name="Aurora",
        service="Consultoria",
        target_niches="clínicas",
        target_locations="Porto Alegre",
        ideal_customer="Clínicas em crescimento",
        value_proposition="Mais reuniões qualificadas",
        average_ticket=3500,
        daily_contact_limit=18,
        offers="Plano Premium",
        pricing_rules="Preço fixo",
        differentiators="Dados verificados",
        case_studies="Case Alfa",
        qualification_rules="Dor e prazo confirmados",
        disqualifiers="Sem consentimento",
        discount_policy="Até 5%",
        proposal_terms="Validade 7 dias",
        contract_template="Revisão humana obrigatória",
    )
    dialog = CommercialSettingsDialog(original)

    assert dialog.tabs.count() == 4
    assert [dialog.tabs.tabText(index) for index in range(4)] == [
        "1  Essencial", "2  Público ideal", "3  Oferta", "4  Avançado"
    ]
    assert dialog.business.accessibleName() == "Nome da empresa ou operação"
    assert dialog.qualification.accessibleName() == "Quando um lead está pronto?"
    assert dialog.commercial_profile() == original
