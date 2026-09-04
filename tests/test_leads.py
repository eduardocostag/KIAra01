from concurrent.futures import ThreadPoolExecutor

from app.leads import CommercialProfile, LeadScoringPolicy, LeadStage, LeadStore


def test_lead_store_upserts_pipeline_and_metrics(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    identifier = store.upsert(company="Clínica Sol", niche="odontologia", location="Canoas",
                              whatsapp="51999999999", score=82, qualification="fit digital")
    same = store.upsert(company="Clínica Sol", niche="odontologia", location="Canoas",
                        whatsapp="51999999999", score=90, qualification="sem site")
    assert same == identifier
    assert store.list()[0].score == 90
    assert store.update(identifier, stage=LeadStage.QUALIFIED, next_action="Fazer contato")
    assert store.metrics()["oportunidades"] == 1
    assert store.list(stage=LeadStage.QUALIFIED)[0].next_action == "Fazer contato"
    store.close()


def test_store_serializes_concurrent_upserts_and_atomic_interaction(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    with ThreadPoolExecutor(max_workers=6) as pool:
        identifiers = list(pool.map(
            lambda index: store.upsert(
                company=f"Empresa {index}", whatsapp=f"5199999{index:04d}", location="Canoas"
            ),
            range(30),
        ))
    assert len(set(identifiers)) == 30
    identifier = identifiers[0]
    store.record_interaction_and_transition(
        identifier, channel="WhatsApp", outcome="respondeu", stage=LeadStage.REPLIED
    )
    assert store.list(stage=LeadStage.REPLIED)[0].id == identifier
    assert store.interactions(identifier)[0].outcome == "respondeu"
    assert store._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 5
    store.close()


def test_store_preserves_field_evidence_and_due_actions(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    identifier = store.upsert(company="Clinica Aurora", whatsapp="5551999999999")
    store.add_observation(
        identifier, field_name="whatsapp", value="+55 51 99999-9999",
        raw_value="(51) 99999-9999", source_url="https://example.test/maps/aurora",
        source_type="google_maps", status="VERIFIED", confidence=0.99,
    )
    store.update(
        identifier, next_action="Enviar abordagem revisada",
        next_action_at="2026-09-02T12:00:00+00:00",
    )
    evidence = store.observations(identifier)
    assert evidence[0].status == "VERIFIED"
    assert evidence[0].confidence == 0.99
    assert store.due_actions(through="2026-09-03T00:00:00+00:00")[0].id == identifier
    store.close()


def test_profile_explainable_score_interactions_and_funnel(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    profile = CommercialProfile(
        business_name="Studio Web", service="Criação de sites",
        target_niches="odontologia, estética", target_locations="Canoas, Porto Alegre",
        value_proposition="Mais agendamentos vindos do Google", average_ticket=3500,
    )
    store.save_profile(profile)
    assert store.profile().average_ticket == 3500
    score = LeadScoringPolicy().evaluate(
        {"name": "Clínica Sol", "niche": "odontologia", "address": "Canoas, RS",
         "whatsapp": "51999999999", "website": "", "maps_url": "https://maps.test/sol",
         "rating": 5.0, "review_count": 150},
        profile,
    )
    assert score.total == 100
    assert "nicho aderente" in score.explanation
    identifier = store.upsert(
        company="Clínica Sol", niche="odontologia", location="Canoas, RS",
        whatsapp="51999999999", score=score.total, qualification=score.qualification,
        score_explanation=score.explanation, dossier="Oportunidade verificada",
    )
    store.add_interaction(identifier, channel="WhatsApp", outcome="respondeu")
    store.update(identifier, stage=LeadStage.REPLIED)
    assert store.interactions(identifier)[0].outcome == "respondeu"
    assert store.funnel_metrics()["reply_rate"] == 100.0
    assert "lacuna digital" in store.list()[0].score_explanation
    store.close()
