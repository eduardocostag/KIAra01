from app.leads import CommercialProfile, LeadScoringPolicy


def _verified_lead(**changes: object) -> dict[str, object]:
    lead: dict[str, object] = {
        "name": "Clínica Sol",
        "niche": "odontologia",
        "address": "Canoas, RS",
        "whatsapp": "5551999999999",
        "website": "",
        "maps_url": "https://maps.example/sol",
        "rating": 5.0,
        "review_count": 150,
    }
    lead.update(changes)
    return lead


def _profile(**changes: object) -> CommercialProfile:
    values: dict[str, object] = {
        "target_niches": "odontologia",
        "target_locations": "Canoas",
    }
    values.update(changes)
    return CommercialProfile(**values)


def test_score_exposes_versioned_dimensions_and_structured_reasons() -> None:
    score = LeadScoringPolicy().evaluate(_verified_lead(), _profile())

    assert score.total == score.priority == 100
    assert (score.confidence, score.fit, score.opportunity, score.engagement) == (100, 100, 100, 0)
    assert score.model_version == "sdr-multidimensional-v1"
    assert {reason.dimension for reason in score.breakdown} >= {
        "confidence",
        "fit",
        "opportunity",
    }
    assert isinstance(score.as_dict()["breakdown"], list)


def test_seller_offer_configuration_does_not_change_intrinsic_lead_score() -> None:
    policy = LeadScoringPolicy()
    plain = policy.evaluate(_verified_lead(), _profile())
    configured = policy.evaluate(
        _verified_lead(),
        _profile(
            service="Sites premium",
            value_proposition="Mais agendamentos",
            average_ticket=9000,
        ),
    )

    assert configured.as_dict() == plain.as_dict()


def test_low_data_confidence_caps_priority_even_with_apparent_opportunity() -> None:
    score = LeadScoringPolicy().evaluate(
        {"name": "Negócio", "website": "", "review_count": 500, "rating": 5.0},
        CommercialProfile(),
    )

    assert score.confidence < 60
    assert score.priority <= 59
    assert any(reason.dimension == "priority" for reason in score.breakdown)


def test_engagement_is_ignored_before_contact_and_used_after_real_signal() -> None:
    policy = LeadScoringPolicy()
    new = policy.evaluate(_verified_lead(), _profile())
    replied = policy.evaluate(_verified_lead(stage="respondeu"), _profile())

    assert new.engagement == 0
    assert not any(reason.dimension == "engagement" for reason in new.breakdown)
    assert replied.engagement == 60
    assert any(reason.dimension == "engagement" for reason in replied.breakdown)


def test_explicit_external_site_check_is_stronger_than_maps_absence() -> None:
    policy = LeadScoringPolicy()
    maps_only = policy.evaluate(
        _verified_lead(website_status="NOT_LISTED_ON_MAPS", rating=0, review_count=0),
        _profile(),
    )
    external = policy.evaluate(
        _verified_lead(website_status="NOT_FOUND_IN_EXTERNAL_SEARCH", rating=0, review_count=0),
        _profile(),
    )

    assert external.opportunity > maps_only.opportunity
