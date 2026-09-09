"""Small reviewed constraint judgment set, not an online ranking experiment.

The real reported query is included alongside different niches and long-tail
constraints. Labels judge evidence satisfaction, not an unsupported claim that
the source covers every business or that a website can never exist elsewhere.
"""
import asyncio
from copy import deepcopy
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api import hunter
from kiara_api.hunter import SearchCreate, execute_research, research_query
from kiara_api.hunter_research import (clean_summary, extract_contacts, filter_results,
    maps_detail_result, normalize_result, research_options, whatsapp_link)


def search(query="psicólogos sem site", **options):
    return SearchCreate(market="b2b", query=query, sources=["web", "google_maps"], **options).model_dump()


def maps_result(name, *, loaded=True, website=None, phone="+55 (11) 91234-5678", whatsapp=False, website_button=False):
    return maps_detail_result({"title": name, "url": f"https://www.google.com/maps/place/{name}/data=!1s{name}"},
        {"title": name, "loaded": loaded, "website": website, "website_button": website_button or bool(website),
         "phone": phone, "address": "São Paulo", "links": ["https://wa.me/5511912345678"] if whatsapp else []})


@pytest.mark.parametrize("query,expected", [
    ("psicólogos sem site", "psicólogos"),
    ("dentistas que não tenham site", "dentistas"),
    ("padarias que não possuem um website", "padarias"),
    ("salões SEM SITE PRÓPRIO", "salões"),
    ("academias sem página web", "academias"),
])
def test_negative_website_intent_is_a_filter_not_search_words(query, expected):
    request = search(query)
    assert research_options(request)["website_filter"] == "without_website"
    assert research_query(request) == expected


def test_explicit_filters_validate_and_broad_does_not_keep_old_focus():
    with pytest.raises(ValidationError):
        search(website_filter="maybe")
    with pytest.raises(ValidationError):
        search(contact_filter="sms")
    options = research_options(search("padarias", objective="sem site", research_mode="broad"))
    assert options["website_filter"] == "any"
    assert not options["unsupported_criterion"]


def test_exact_reported_query_excludes_own_website_and_requires_public_whatsapp():
    items = [
        {"source": "web", "title": "Juliana — Psicóloga", "url": "https://julianatelles.com.br/", "summary": "Psicoterapia"},
        maps_result("has-site", website="https://clinica.example", whatsapp=True),
        maps_result("no-site-phone-only"),
        maps_result("not-inspected", loaded=False, whatsapp=True),
        maps_result("accepted", whatsapp=True),
    ]
    kept, stats = filter_results(items, search(contact_filter="whatsapp"))
    assert [item["title"] for item in kept] == ["accepted"]
    assert kept[0]["public_data"]["criterion_status"] == "verified"
    assert kept[0]["public_data"]["whatsapp_url"] == "https://wa.me/5511912345678"
    assert kept[0]["public_data"]["website_status"] == "not_listed"
    assert stats == {"checked": 5, "accepted": 1, "excluded": 4, "unknown": 2, "source_failures": 0}


def test_absent_or_unreadable_detail_is_unknown_never_no_website():
    for item in [maps_result("empty", loaded=False), maps_result("unreadable", website_button=True),
                 maps_result("unsafe", website="javascript:alert(1)")]:
        assert item["public_data"]["website_status"] == "unknown"
        assert filter_results([item], search())[0] == []


def test_wrong_business_detail_does_not_qualify_a_missing_website():
    item = maps_detail_result({"title": "Expected business", "url": "https://google.com/maps/place/expected"},
                              {"title": "Different business", "loaded": True, "phone": "11912345678"})
    assert item["public_data"]["detail_inspected"] is False
    assert filter_results([item], search())[0] == []


def test_whatsapp_in_maps_site_field_is_contact_not_an_owned_website():
    item = maps_result("whatsapp-field", website="https://api.whatsapp.com/send?phone=5511912345678")
    kept, _ = filter_results([item], search(contact_filter="whatsapp"))
    assert len(kept) == 1
    assert kept[0]["public_data"]["website_status"] == "not_listed"
    assert kept[0]["public_data"]["website_url"] is None
    assert kept[0]["public_data"]["whatsapp_url"] == "https://wa.me/5511912345678"
    assert "aponta para WhatsApp" in kept[0]["public_data"]["website_evidence"]


def test_other_social_link_in_maps_site_field_is_explicitly_unknown():
    item = maps_result("social-field", website="https://instagram.com/public-business")
    assert item["public_data"]["website_status"] == "unknown"
    assert item["public_data"]["website_url"] is None
    assert filter_results([item], search())[0] == []


@pytest.mark.parametrize("link,expected", [
    ("https://wa.me/5511912345678?text=oi", "https://wa.me/5511912345678"),
    ("https://api.whatsapp.com/send?phone=5511912345678", "https://wa.me/5511912345678"),
    ("https://web.whatsapp.com/send?phone=5511912345678", "https://wa.me/5511912345678"),
    ("https://wa.me.evil.test/5511912345678", None),
    ("https://wa.me/123", None),
    ("https://wa.me/message/ABCD", None),
    ("https://whatsapp.com/channel/example", None),
    ("javascript:alert(1)", None),
])
def test_whatsapp_only_from_valid_explicit_contact_link(link, expected):
    assert whatsapp_link(link) == expected


def test_phone_is_never_guessed_to_have_whatsapp_or_country_code():
    contacts = extract_contacts("Telefone: (11) 91234-5678")
    assert contacts == {"phone": "11912345678", "whatsapp_url": None}
    assert extract_contacts("Protocolo 11912345678")["phone"] is None


def test_raw_markdown_is_not_exposed_even_in_legacy_enrichment():
    raw = "[Ir para o conteúdo](https://clinic.example/#content)\n![logo](https://clinic.example/logo.png)\n# PSICOTERAPIA\n**Cuidado emocional.** [Contato](https://wa.me/5511912345678)"
    item = normalize_result({"title": "Clínica", "url": "https://clinic.example", "source": "web", "summary": raw,
                             "public_data": {"content": raw, "provider": "firecrawl"}})
    assert "content" not in item["public_data"]
    assert "https://" not in item["summary"] and "![" not in item["summary"] and "#" not in item["summary"]
    assert item["public_data"]["whatsapp_url"] == "https://wa.me/5511912345678"
    assert len(clean_summary("word " * 1000)) <= 501


def test_arbitrary_criteria_stay_unverified_for_any_niche():
    for request in [search("restaurantes com estacionamento"),
                    search("lojas de roupas", research_mode="focused", objective="que vendem no Instagram")]:
        kept, _ = filter_results([maps_result("candidate")], request)
        assert kept[0]["public_data"]["criterion_status"] == "not_verified"
    kept, _ = filter_results([maps_result("candidate")], search("restaurantes"))
    assert kept[0]["public_data"]["criterion_status"] == "not_requested"


def test_golden_constraint_judgments_improve_precision_without_losing_eligible_candidates():
    """Before accepted all candidates. After excludes every judged violation."""
    fixtures = [
        (search("psicólogos sem site"), [maps_result("a"), maps_result("b", website="https://b.example"), maps_result("c", loaded=False)], {"a"}),
        (search("oficinas sem site", contact_filter="whatsapp"), [maps_result("d", whatsapp=True), maps_result("e"), maps_result("f", website="https://f.example", whatsapp=True)], {"d"}),
        (search("dentistas com site"), [maps_result("g", website="https://g.example"), maps_result("h"), maps_result("i", loaded=False)], {"g"}),
        (search("padarias", contact_filter="phone"), [maps_result("j"), maps_result("k", phone=None)], {"j"}),
        (search("lojas de roupas"), [maps_result("l"), maps_result("m", loaded=False)], {"l", "m"}),
    ]
    total = eligible = returned = correct = 0
    for request, candidates, labels in fixtures:
        kept, _ = filter_results(deepcopy(candidates), request)
        titles = {item["title"] for item in kept}
        assert titles == labels
        total += len(candidates)
        eligible += len(labels)
        returned += len(kept)
        correct += len(titles & labels)
    assert (total, eligible, returned, correct) == (13, 6, 6, 6)
    assert eligible / total < correct / returned  # 46.2% -> 100% precision, recall 100% on these 13 fixtures.


def test_partial_provider_failure_keeps_results_and_reports_warning(monkeypatch):
    async def exa(*args):
        raise RuntimeError("exa_not_configured")
    async def maps(query, limit):
        assert query == "psicólogos"
        return [maps_result("accepted", whatsapp=True)]
    monkeypatch.setattr(hunter, "exa_search", exa)
    monkeypatch.setattr(hunter, "maps_search", maps)
    outcome = asyncio.run(execute_research(search(contact_filter="whatsapp")))
    assert outcome["error"] is None
    assert len(outcome["results"]) == 1
    assert outcome["validation"]["source_failures"] == 1
    assert any("Web pública não concluiu" in message for message in outcome["warnings"])


def test_provider_timeout_is_bounded_and_persistable_failed_job(monkeypatch):
    async def never(*args):
        await asyncio.sleep(10)
    monkeypatch.setattr(hunter, "exa_search", never)
    monkeypatch.setattr(hunter, "maps_search", never)
    monkeypatch.setattr(hunter, "SOURCE_TIMEOUT_SECONDS", 0.01)
    outcome = asyncio.run(execute_research(search()))
    assert outcome["error"] == "provider_error"
    assert outcome["results"] == []
    assert outcome["validation"]["source_failures"] == 2


def test_filter_applied_before_result_limit_and_web_crawl_skipped_for_no_site(monkeypatch):
    async def maps(*args):
        return [maps_result("reject", website="https://site.example"), maps_result("accept")]
    async def forbidden(*args):
        raise AssertionError("No-site searches must not pay to scrape sites known to fail.")
    monkeypatch.setattr(hunter, "maps_search", maps)
    monkeypatch.setattr(hunter, "enrich_results", forbidden)
    request = SearchCreate(market="b2b", query="oficinas sem site", sources=["google_maps"], result_limit=1)
    outcome = asyncio.run(execute_research(request.model_dump()))
    assert [row["title"] for row in outcome["results"]] == ["accept"]
    assert outcome["validation"]["excluded"] == 1
