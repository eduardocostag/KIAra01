from app.privacy import HunterPrivacyPolicy, HunterResearchRequest


def request(**changes):
    values = {
        "subject_kind": "business",
        "source_is_public": True,
        "source_url": "https://instagram.com/example",
        "purpose": "commercial_research",
        "fields": frozenset({"business_handle", "public_business_signal", "source_url"}),
        "has_need_signal": True,
        "signal_age_days": 2,
    }
    values.update(changes)
    return HunterResearchRequest(**values)


def test_allows_minimal_signal_led_business_research_but_never_automatic_dm():
    decision = HunterPrivacyPolicy().evaluate(request())

    assert decision.research_allowed
    assert decision.assisted_contact_allowed
    assert not decision.automatic_dm_allowed
    assert decision.retention_days == 30
    assert decision.legal_basis == "legitimate_interest_assessment_required"


def test_blocks_arbitrary_personal_and_sensitive_enrichment():
    for field in ("personal_phone", "religion"):
        decision = HunterPrivacyPolicy().evaluate(request(fields=frozenset({field, "source_url"})))
        assert not decision.research_allowed
        assert not decision.assisted_contact_allowed


def test_public_consumer_profile_is_not_permission_for_cold_prospecting():
    decision = HunterPrivacyPolicy().evaluate(request(subject_kind="consumer"))
    assert not decision.research_allowed
    assert decision.legal_basis == "cold_b2c"


def test_inbound_consumer_can_be_researched_but_contact_requires_channel_consent():
    inbound = HunterPrivacyPolicy().evaluate(
        request(subject_kind="consumer", inbound_interaction=True)
    )
    consented = HunterPrivacyPolicy().evaluate(
        request(subject_kind="consumer", inbound_interaction=True, channel_consent=True)
    )
    assert inbound.research_allowed and not inbound.assisted_contact_allowed
    assert consented.assisted_contact_allowed
    assert not consented.automatic_dm_allowed


def test_opt_out_is_global_fail_closed_and_dsar_covers_every_store():
    decision = HunterPrivacyPolicy().evaluate(request(opted_out=True, channel_consent=True))
    plan = HunterPrivacyPolicy.rights_plan()

    assert not decision.research_allowed
    assert not decision.automatic_dm_allowed
    assert "meta_platform" in plan.delete_locations
    assert "application_logs" in plan.delete_locations
    assert plan.preserve_suppression_hash
    assert plan.backup_treatment == "tombstone_and_delete_on_restore"
