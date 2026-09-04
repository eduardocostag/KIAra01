import sqlite3

from app.leads import (
    CommercialProfile,
    LeadDossier,
    LeadScoringPolicy,
    LeadStage,
    LeadStore,
    QualificationData,
    SalesArtifacts,
)


def test_closer_stages_are_persisted_and_counted_as_opportunities(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    lead_id = store.upsert(company="Empresa SQL")
    for stage in (
        LeadStage.DISCOVERY, LeadStage.PROPOSAL, LeadStage.NEGOTIATION,
        LeadStage.CONTRACT, LeadStage.SIGNATURE,
    ):
        assert store.update(lead_id, stage=stage)
        assert store.list(stage=stage)[0].id == lead_id
        assert store.metrics()["oportunidades"] == 1
    store.close()


def test_sales_intelligence_is_structured_merged_and_not_erased_by_upsert(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    lead_id = store.upsert(
        company="Clínica Aurora",
        qualification_data=QualificationData(
            status="sql_pronto", need="verified", missing_information=("budget",)
        ),
        dossier_data=LeadDossier(
            executive_summary="Expansão confirmada", hypotheses=("Pode precisar de CRM",)
        ),
        sales_artifacts=SalesArtifacts(opening_message="Olá, Ana"),
    )
    store.update_sales_intelligence(
        lead_id,
        qualification={"capacity": "verified", "missing_information": []},
        artifacts={"call_script": "Confirmar número de unidades"},
    )
    store.upsert(company="Clínica Aurora", score=80)

    lead = store.list()[0]
    assert lead.qualification_data["status"] == "sql_pronto"
    assert lead.qualification_data["capacity"] == "verified"
    assert lead.dossier_data["executive_summary"] == "Expansão confirmada"
    assert lead.sales_artifacts["opening_message"] == "Olá, Ana"
    assert lead.sales_artifacts["call_script"] == "Confirmar número de unidades"
    store.close()


def test_existing_database_is_migrated_without_losing_legacy_dossier(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE leads (
          id TEXT PRIMARY KEY, company TEXT NOT NULL, niche TEXT NOT NULL DEFAULT '',
          location TEXT NOT NULL DEFAULT '', whatsapp TEXT NOT NULL DEFAULT '',
          website TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
          score INTEGER NOT NULL DEFAULT 0, stage TEXT NOT NULL DEFAULT 'novo',
          qualification TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
          next_action TEXT NOT NULL DEFAULT '', next_action_at TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, dossier TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO leads(id,company,created_at,updated_at,dossier)
          VALUES('legacy','Empresa Antiga','now','now','Texto histórico');
        """
    )
    connection.close()

    store = LeadStore(path)
    lead = store.list()[0]
    assert lead.dossier == "Texto histórico"
    assert lead.qualification_data == {}
    columns = {row[1] for row in store._connection.execute("PRAGMA table_info(leads)")}
    assert {"qualification_data", "dossier_data", "sales_artifacts"} <= columns
    assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 5
    store.close()


def test_commercial_profile_supports_offer_pricing_and_approved_contract(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    profile = CommercialProfile(
        business_name="Kiara Growth", offers="Plano Scale", pricing_rules="R$ 9.000",
        discount_policy="Até 5% com aprovação", contract_template="Modelo jurídico v3",
        qualification_rules="Decisor e timing confirmados", disqualifiers="Sem orçamento",
    )
    store.save_profile(profile)
    loaded = store.profile()
    assert loaded.offers == "Plano Scale"
    assert loaded.discount_policy == "Até 5% com aprovação"
    assert loaded.contract_template == "Modelo jurídico v3"
    store.close()


def test_readiness_never_invents_missing_buying_signals() -> None:
    policy = LeadScoringPolicy()
    profile = CommercialProfile(target_niches="odontologia", target_locations="Canoas")
    base = {
        "name": "Clínica", "niche": "odontologia", "address": "Canoas",
        "whatsapp": "5551999999999", "maps_url": "https://maps.test/lead",
        "website_status": "NOT_FOUND_IN_EXTERNAL_SEARCH", "review_count": 100,
        "rating": 4.9,
    }
    incomplete = policy.evaluate(base, profile)
    assert incomplete.qualification_status != "sql_pronto"
    assert {"timing", "autoridade", "capacidade"} <= set(incomplete.missing_information)

    ready = policy.evaluate(
        {**base, "timing_score": 80, "authority_score": 90, "capacity_score": 75}, profile
    )
    assert ready.qualification_status == "sql_pronto"
    assert ready.readiness >= 65


def test_explicit_disqualifier_overrides_high_scores() -> None:
    score = LeadScoringPolicy().evaluate(
        {
            "name": "Empresa", "maps_url": "https://maps.test/x", "whatsapp": "55",
            "need_score": 100, "timing_score": 100, "authority_score": 100,
            "capacity_score": 100, "disqualifiers": ["conflito de território"],
        },
        CommercialProfile(),
    )
    assert score.qualification_status == "desqualificado"
    assert score.readiness == 0
