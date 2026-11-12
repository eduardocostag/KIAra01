"""Regression checks for source-preserving contacts and inspected addresses."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.hunter import enrich_results, native_enrich_results
from kiara_api.hunter_research import (
    address_matches_location,
    extract_public_address,
    lead_requirement_gaps,
)


@pytest.mark.asyncio
async def test_native_enrichment_preserves_maps_contacts_without_contacts_on_site(monkeypatch):
    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", lambda url: ("Nossos serviços", [], "native"))
    data = {"website_url": "https://clinic.example", "phone": "+5511999990000",
            "whatsapp_url": "https://wa.me/5511999990000", "address": "Rua Flores, 100, Curitiba - PR",
            "detail_inspected": True}
    item = {"source": "google_maps", "title": "Clínica Aurora", "url": "https://maps.google.com/place/aurora", "public_data": data}
    await native_enrich_results([item])
    assert data["phone"] == "+5511999990000"
    assert data["whatsapp_url"] == "https://wa.me/5511999990000"
    assert lead_requirement_gaps(item, {}) == []


@pytest.mark.asyncio
async def test_completed_homepage_without_address_still_gets_contact_page_fallback(monkeypatch):
    pages = {
        "https://clinic.example": ("Clínica", ["https://clinic.example/contato"], "native"),
        "https://clinic.example/contato": ("Rua Flores, 100 - Curitiba - PR", [], "native"),
    }
    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", lambda url: pages[url])
    item = {"source": "web", "title": "Clínica", "url": "https://clinic.example", "public_data": {
        "enrichment": "completed", "phone": "+5541999990000", "provider": "firecrawl",
    }}
    await native_enrich_results([item])
    assert item["public_data"]["address_source_url"] == "https://clinic.example/contato"
    assert lead_requirement_gaps(item, {}) == []


@pytest.mark.asyncio
async def test_web_contact_page_supplies_observed_address_and_exact_provenance(monkeypatch):
    address = "Rua das Flores, 123, Centro, Curitiba - PR"
    pages = {
        "https://clinic.example": ("Clínica Aurora", ["https://clinic.example/contato"], "native"),
        "https://clinic.example/contato": (f"Endereço: {address} Telefone: +55 41 99999-0000", [], "native"),
    }
    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", lambda url: pages[url])
    item = {"source": "web", "title": "Clínica Aurora", "url": "https://clinic.example", "public_data": {}}
    await native_enrich_results([item])
    data = item["public_data"]
    assert data["address"] == address
    assert data["address_source_url"] == "https://clinic.example/contato"
    assert data["address_evidence_text"] == address
    assert lead_requirement_gaps(item, {}) == []


@pytest.mark.parametrize("text", [
    "Atendemos Curitiba e São Paulo. Telefone: +55 41 99999-0000",
    "Rua das Flores sem número. Curitiba - PR",
    "Rua das Flores, 123. Telefone: +55 41 99999-0000. Atendemos Curitiba - PR",
    "Rua das Flores, 123. Sem localização publicada.",
    "Rua das Flores, 123. Conheça as nossas unidades em Curitiba - PR",
])
def test_page_without_complete_observed_address_cannot_gain_location_evidence(text):
    assert extract_public_address(text, "https://clinic.example") == {}


@pytest.mark.parametrize("address", [
    "Avenida Paulista, 1000, São Paulo/SP",
    "Av. Brasil 200 - Centro - Porto Alegre - RS",
    "Rua das Flores, 123 CEP: 80000-123",
])
def test_address_extraction_preserves_observed_text(address):
    assert extract_public_address(address, "https://clinic.example")["address"] == address


@pytest.mark.asyncio
async def test_firecrawl_enrichment_keeps_existing_contacts_and_extracts_address(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-only-key")
    monkeypatch.delenv("KIARA_SCRAPEGRAPH_MODEL", raising=False)
    monkeypatch.setattr("kiara_api.hunter._post_json", lambda *args: {
        "success": True, "data": {"markdown": "Endereço: Rua Flores, 100 - Curitiba - PR", "links": []},
    })
    item = {"source": "web", "title": "Clínica", "url": "https://clinic.example",
            "public_data": {"phone": "+5541999990000", "whatsapp_url": "https://wa.me/5541999990000"}}
    await enrich_results([item])
    assert item["public_data"]["phone"] == "+5541999990000"
    assert item["public_data"]["whatsapp_url"] == "https://wa.me/5541999990000"
    assert lead_requirement_gaps(item, {}) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ImportError("missing optional browser"), RuntimeError("CDP unavailable"), TimeoutError("CDP timed out")])
async def test_optional_renderer_failure_cannot_block_native_contacts(monkeypatch, error):
    from unittest.mock import AsyncMock

    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.delenv("KIARA_SCRAPEGRAPH_MODEL", raising=False)
    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", lambda url: ("Telefone: +55 41 99999-0000", [], "native"))
    renderer = AsyncMock(side_effect=error)
    monkeypatch.setattr("kiara_api.hunter.obscura_enrich_results", renderer)
    item = {"source": "web", "title": "Clínica", "url": "https://clinic.example", "public_data": {}}
    await enrich_results([item])
    renderer.assert_awaited_once()
    assert item["public_data"]["phone"] == "+5541999990000"


@pytest.mark.asyncio
async def test_optional_semantic_failure_does_not_erase_native_evidence(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", lambda url: (
        "Rua Flores, 100 - Curitiba - PR Telefone: +55 41 99999-0000", [], "native",
    ))
    renderer = AsyncMock(side_effect=AssertionError("complete native results need no rendering"))
    monkeypatch.setattr("kiara_api.hunter.obscura_enrich_results", renderer)
    monkeypatch.setattr("kiara_api.hunter.semantic_enrich_results", AsyncMock(side_effect=AttributeError("optional SDK failed")))
    item = {"source": "web", "title": "Clínica", "url": "https://clinic.example", "public_data": {}}
    await enrich_results([item])
    renderer.assert_not_awaited()
    assert lead_requirement_gaps(item, {}) == []


@pytest.mark.parametrize("source", ["web", "google_maps"])
def test_verified_address_in_another_city_is_not_a_matching_lead(source):
    item = {"source": source, "title": "Clínica", "url": "https://clinic.example", "public_data": {
        "phone": "+5541999990000", "address": "Rua Flores, 123 - Curitiba - PR",
        "address_evidence": "verified_public_page", "detail_inspected": True,
    }}
    assert lead_requirement_gaps(item, {"location": "Porto Alegre - RS"}) == ["verified_location"]


@pytest.mark.parametrize(("address", "requested", "matches"), [
    ("Rua Flores, 123 - Curitiba - PR", "Curitiba, Paraná", True),
    ("Rua Flores, 123 - Porto Alegre - Rio Grande do Sul", "Pôrto Alegre RS", True),
    ("Rua Flores, 123 - Centro - São Paulo - SP", "Sao Paulo, SP", True),
    ("Rua Flores, 123 - Centro - Curitiba - PR", "Centro, Curitiba, PR", True),
    ("Rua Flores, 123 - Curitiba - PR", "Centro, Curitiba, PR", False),
    ("Rua Flores, 123 - Campinas - SP", "São Paulo", False),
    ("Rua Flores, 123 - São Paulo - SP", "São Paulo", True),
    ("Rua Flores, 123 - São Paulo de Olivença - AM", "São Paulo", False),
    ("Rua Flores, 123 - Santos Dumont - MG", "Santos", False),
    ("Rua Flores, 123 - Niterói - RJ", "Rio de Janeiro", False),
    ("Rua Flores, 123 - Curitiba - PR", "Curitiba - RS", False),
    ("Rua Flores, 123 - CEP 80000-123", "Curitiba - PR", False),
    ("Rua Flores, 123 - PR", "Curitiba", False),
    ("Rua Curitiba, 123 - Londrina - PR", "Curitiba", False),
    ("Rua Flores, 123 - Curitiba - PR", "PR", True),
])
def test_geographic_evidence_requires_observed_locality(address, requested, matches):
    assert address_matches_location(address, requested) is matches


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["obscura", "browserbase"])
async def test_unverified_remote_maps_details_use_local_browser_once(monkeypatch, provider):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from kiara_api import hunter

    pytest.importorskip("playwright.async_api")
    monkeypatch.delenv("KIARA_MAPS_SCRAPER_EXECUTABLE", raising=False)
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key" if provider == "browserbase" else "")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "test-project" if provider == "browserbase" else "")
    monkeypatch.setattr(hunter, "google_places_search", AsyncMock(side_effect=RuntimeError("not configured")))
    monkeypatch.setattr(hunter, "_browserbase_circuit_open", lambda: False)
    monkeypatch.setattr(hunter, "_obscura_connection", lambda: ("https://cdp.example", {}) if provider == "obscura" else None)
    unverified = {"source": "google_maps", "title": "Unverified", "url": "https://google.com/maps/place/unverified", "public_data": {"detail_inspected": False}}
    verified = {"source": "google_maps", "title": "Verified", "url": "https://google.com/maps/place/verified", "public_data": {"detail_inspected": True}}
    remote = AsyncMock(return_value=[unverified])
    local = AsyncMock(return_value=[verified])
    monkeypatch.setattr(hunter, "_read_maps_cdp", remote)
    monkeypatch.setattr(hunter, "_read_maps_local", local)
    monkeypatch.setattr(hunter, "maps_index_search", AsyncMock(return_value=[]))
    release = Mock()
    client = SimpleNamespace(sessions=SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(id="session", connect_url="https://cdp.example"),
        update=release,
    ), close=Mock())
    monkeypatch.setitem(sys.modules, "browserbase", SimpleNamespace(Browserbase=lambda **kwargs: client))
    rows = await hunter.maps_search("dentistas Curitiba", 1)
    assert rows == [verified]
    remote.assert_awaited_once()
    local.assert_awaited_once()
    if provider == "browserbase":
        release.assert_called_once()
        client.close.assert_called_once()


@pytest.mark.asyncio
async def test_unverified_maps_details_are_excluded_with_visible_warning(monkeypatch):
    from unittest.mock import AsyncMock

    from kiara_api import hunter

    monkeypatch.setattr(hunter, "maps_search", AsyncMock(return_value=[{
        "source": "google_maps", "title": "Unverified", "url": "https://google.com/maps/place/unverified",
        "public_data": {"detail_inspected": False, "provider": "browserbase"},
    }]))
    monkeypatch.setattr(hunter, "enrich_results", AsyncMock())
    result = await hunter.execute_research({"query": "dentistas", "sources": ["google_maps"], "result_limit": 1, "market": "b2b"})
    assert result["results"] == []
    assert any("ficha(s) do Google Maps" in warning and "excluídas" in warning for warning in result["warnings"])
