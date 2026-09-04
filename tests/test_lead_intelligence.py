from app.leads.intelligence import (
    ClaimKind,
    CommercialIntelligenceService,
    QualificationStatus,
)


def test_artifacts_keep_verified_facts_inferences_and_unknowns_separate() -> None:
    service = CommercialIntelligenceService()
    artifacts = service.generate(
        {
            "id": "lead-1",
            "company": "Clínica Aurora",
            "niche": "Psicologia",
            "source_url": "https://example.test/maps/aurora",
            "website_status": "NOT_FOUND_IN_EXTERNAL_SEARCH",
            "confidence_score": 90,
            "fit_score": 85,
        },
        {"service": "Site de alta conversão", "target_niches": "Psicologia"},
    )

    assert all(claim.kind == ClaimKind.FACT for claim in artifacts.qualification.facts)
    assert all(claim.source_url for claim in artifacts.qualification.facts)
    assert any(claim.field == "need" for claim in artifacts.qualification.inferences)
    assert any(claim.field == "decision_maker" for claim in artifacts.qualification.unknowns)
    assert artifacts.qualification.status == QualificationStatus.NURTURE
    assert artifacts.is_grounded


def test_verified_critical_evidence_can_produce_sql_and_proposal_review() -> None:
    service = CommercialIntelligenceService()
    evidence = [
        {
            "field_name": field,
            "normalized_value": value,
            "status": "VERIFIED",
            "confidence": 0.95,
            "source_url": f"https://crm.test/{field}",
        }
        for field, value in (
            ("decision_maker", "Ana, sócia"),
            ("need", "Baixa conversão de contatos"),
            ("timing", "Resolver neste trimestre"),
            ("budget", "R$ 10 mil aprovados"),
            ("decision_process", "Sócias decidem juntas"),
        )
    ]
    artifacts = service.generate(
        {"id": "lead-2", "company": "Aurora", "confidence_score": 90, "fit_score": 90},
        {"service": "Aceleração comercial", "average_ticket": 7500},
        evidence,
    )

    assert artifacts.qualification.status == QualificationStatus.SQL
    assert not artifacts.qualification.unknowns
    assert artifacts.proposal.is_ready_for_review
    assert artifacts.proposal.investment.startswith("R$")
    assert {gate.action for gate in artifacts.proposal.approval_gates} == {
        "pricing", "legal", "send"
    }
    assert artifacts.contract.is_ready_for_review is False
    assert {gate.action for gate in artifacts.contract.approval_gates} == {
        "legal", "send", "signature"
    }


def test_observed_or_low_confidence_data_is_not_promoted_to_verified_fact() -> None:
    lead = {"id": "lead-unsafe", "company": "Empresa observada"}
    evidence = (
        {"field_name": "decision_maker", "normalized_value": "Ana", "status": "OBSERVED",
         "confidence": 0.99, "source_url": "https://example.test/maps"},
        {"field_name": "need", "normalized_value": "Baixa conversão", "status": "VERIFIED",
         "confidence": 0.4, "source_url": "https://example.test/site"},
    )

    artifacts = CommercialIntelligenceService().generate(lead, {}, evidence)

    assert artifacts.qualification.facts == ()
    assert artifacts.qualification.status == QualificationStatus.RESEARCH
    assert artifacts.outreach.approval.required
    assert not artifacts.outreach.approval.approved


def test_unverified_observation_never_becomes_fact() -> None:
    artifacts = CommercialIntelligenceService().generate(
        {"id": "lead-3", "company": "Empresa sem fonte"},
        {},
        [{
            "field_name": "budget",
            "normalized_value": "R$ 50 mil",
            "status": "INFERRED",
            "confidence": 0.9,
            "source_url": "https://example.test",
        }],
    )

    assert not any(claim.field == "budget" for claim in artifacts.qualification.facts)
    assert any(claim.field == "budget" for claim in artifacts.qualification.unknowns)
    assert artifacts.qualification.status == QualificationStatus.RESEARCH


def test_external_actions_always_have_human_approval_gates() -> None:
    artifacts = CommercialIntelligenceService().generate(
        {"company": "Acme", "source_url": "https://example.test/acme"}, {},
    )

    assert artifacts.outreach.approval.action == "send_outreach"
    assert artifacts.outreach.approval.required
    assert all(gate.required and not gate.approved for gate in artifacts.proposal.approval_gates)


def test_approved_template_prepares_contract_but_never_signs_it() -> None:
    evidence = [
        {"field_name": field, "normalized_value": value, "status": "VERIFIED",
         "confidence": 0.95, "source_url": f"https://crm.test/{field}"}
        for field, value in (
            ("decision_maker", "Ana"), ("need", "Baixa conversão"),
            ("timing", "Neste trimestre"), ("budget", "R$ 10 mil"),
            ("decision_process", "Sócias aprovam"),
        )
    ]
    artifacts = CommercialIntelligenceService().generate(
        {"id": "lead-contract", "company": "Aurora", "confidence_score": 90,
         "fit_score": 90},
        {"service": "Aceleração comercial", "average_ticket": 7500,
         "contract_template": "Modelo jurídico v3"},
        evidence,
    )

    assert artifacts.contract.is_ready_for_review
    assert artifacts.contract.fields["contratante"] == "Aurora"
    assert all(gate.required and not gate.approved for gate in artifacts.contract.approval_gates)
