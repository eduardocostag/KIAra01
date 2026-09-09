from services.api.kiara_api.hunter_research import filter_results, research_options, website_opportunity


def test_free_text_understands_missing_email_and_weak_site() -> None:
    options = research_options({"query": "dentistas sem email com site desatualizado", "research_mode": "broad"})
    assert options["email_filter"] == "without_email"
    assert options["website_quality_filter"] == "opportunity"
    assert options["provider_query"] == "dentistas"
    assert options["unsupported_criterion"] is False


def test_website_opportunity_uses_observable_signals() -> None:
    score, signals = website_opportunity("http://example.com", "Bem-vindo", [])
    assert score <= 25
    assert "Site sem HTTPS" in signals
    assert len(signals) >= 3


def test_missing_email_requires_inspection_and_rejects_observed_email() -> None:
    search = {"query": "clínicas sem email", "research_mode": "broad", "website_filter": "any", "contact_filter": "any"}
    rows = [
        {"source": "web", "title": "Sem email", "url": "https://one.example", "public_data": {"enrichment": "completed"}},
        {"source": "web", "title": "Com email", "url": "https://two.example", "public_data": {"enrichment": "completed", "email": "oi@two.example"}},
        {"source": "web", "title": "Não inspecionado", "url": "https://three.example"},
    ]
    accepted, counts = filter_results(rows, search)
    assert [row["title"] for row in accepted] == ["Sem email"]
    assert accepted[0]["public_data"]["criterion_status"] == "verified"
    assert counts["excluded"] == 2


def test_weak_site_filter_preserves_evidence_reasons() -> None:
    search = {"query": "lojas com site ruim", "research_mode": "broad", "website_filter": "any", "contact_filter": "any"}
    rows = [{"source": "web", "title": "Loja", "url": "https://loja.example", "public_data": {
        "enrichment": "completed", "website_quality_score": 35,
        "website_quality_signals": ["Pouco conteúdo público na página analisada"],
    }}]
    accepted, _ = filter_results(rows, search)
    assert len(accepted) == 1
    assert accepted[0]["public_data"]["match_reasons"]
