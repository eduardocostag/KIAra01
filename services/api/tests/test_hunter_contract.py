import sys
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.hunter import (
    SearchCreate,
    _assert_public_destination,
    _PublicHtmlParser,
    native_enrich_results,
    semantic_enrich_results,
)
from kiara_api.scraping_adapters import fetch_public_with_scrapling


def test_hunter_requires_supported_sources_and_bounded_limit() -> None:
    with pytest.raises(ValidationError):
        SearchCreate(market="b2c", query="academia", sources=["private_instagram"], result_limit=10)
    with pytest.raises(ValidationError):
        SearchCreate(market="b2b", query="clinicas", sources=["web"], result_limit=101)
    assert SearchCreate(market="b2b", query="clinicas", sources=["web"], result_limit=100).result_limit == 100


def test_hunter_accepts_all_public_sources_together() -> None:
    request = SearchCreate(
        market="b2b",
        query="clínicas odontológicas",
        location="Porto Alegre - RS",
        sources=["web", "google_maps", "instagram", "facebook"],
        result_limit=30,
    )
    assert request.sources == ["web", "google_maps", "instagram", "facebook"]


def test_hunter_accepts_every_non_empty_source_combination() -> None:
    from itertools import combinations

    available = ["web", "google_maps", "instagram", "facebook"]
    accepted = 0
    for size in range(1, len(available) + 1):
        for selected in combinations(available, size):
            assert SearchCreate(market="b2b", query="teste", sources=list(selected)).sources == list(selected)
            accepted += 1
    assert accepted == 15


def test_hunter_schema_requires_confirmation_and_tenant_rls() -> None:
    migration = (Path(__file__).parents[1] / "migrations" / "0002_hunter.sql").read_text(encoding="utf-8")
    assert "pending_confirmation" in migration
    assert "confirmed_by" in migration
    assert "confirmed_at" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "kiara.current_organization_id()" in migration


def test_confirmation_is_a_separate_endpoint() -> None:
    source = (Path(__file__).parents[1] / "kiara_api" / "hunter.py").read_text(encoding="utf-8")
    assert '@router.post("/searches", status_code=201)' in source
    assert '@router.post("/searches/{search_id}/confirm")' in source
    assert "claim_confirmation" in source


def test_hunter_uses_a_durable_tenant_queue_and_recoverable_leases() -> None:
    root = Path(__file__).parents[1]
    source = (root / "kiara_api" / "hunter.py").read_text(encoding="utf-8")
    migration = (root / "migrations" / "0007_hunter_durable_queue.sql").read_text(encoding="utf-8")
    assert "'hunter.search','queued'" in source
    assert "attempts=attempts+1" in source
    assert "lease_expires_at<now()" in source
    assert "FOR UPDATE SKIP LOCKED" in source
    assert '@router.get("/internal/drain")' in source
    assert "organization_id uuid NOT NULL" in migration
    assert "REFERENCES hunter_searches (organization_id, id)" in migration


def test_hunter_history_can_be_cleared_without_deleting_pipeline() -> None:
    source = (Path(__file__).parents[1] / "kiara_api" / "hunter.py").read_text(encoding="utf-8")
    assert '@router.delete("/searches")' in source
    assert "DELETE FROM hunter_searches WHERE organization_id=%s" in source
    assert "DELETE FROM pipeline_entries" not in source
    assert '"pipeline_preserved": True' in source


def test_obscura_is_optional_and_browserbase_remains_fallback() -> None:
    source = (Path(__file__).parents[1] / "kiara_api" / "hunter.py").read_text(encoding="utf-8")
    assert 'os.getenv("OBSCURA_CDP_URL"' in source
    assert 'os.getenv("OBSCURA_AUTH_TOKEN"' in source
    assert "rows = await _read_maps_cdp(endpoint, query, limit, headers=headers)" in source
    assert "return await supplement(rows)" in source
    assert "Browserbase(api_key=key" in source
    assert '"provider": "obscura"' in source


def test_native_parser_extracts_visible_text_and_absolute_links() -> None:
    parser = _PublicHtmlParser("https://example.com/team/")
    parser.feed('<style>hidden</style><h1>Clínica Aurora</h1><a href="/contato">WhatsApp</a>')
    assert parser.text == ["Clínica Aurora", "WhatsApp"]
    assert parser.links == ["https://example.com/contato"]


def test_native_fetch_rejects_private_destinations() -> None:
    with pytest.raises(ValueError, match="unsafe_destination"):
        _assert_public_destination("http://127.0.0.1/internal")


@pytest.mark.asyncio
async def test_native_enrichment_requires_no_external_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "kiara_api.hunter._fetch_public_page",
        lambda _url: ("Telefone: +55 11 99999-0000 contato@aurora.com.br", ["https://wa.me/5511999990000"], "scrapling_http"),
    )
    results = [{"source": "web", "url": "https://aurora.example", "title": "Aurora", "public_data": {}}]
    await native_enrich_results(results)
    assert results[0]["public_data"]["provider"] == "scrapling_http"
    assert results[0]["public_data"]["whatsapp_url"] == "https://wa.me/5511999990000"


@pytest.mark.asyncio
async def test_native_enrichment_inspects_relevant_internal_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        "https://aurora.example": ("Clínica Aurora", ["https://aurora.example/contato", "https://aurora.example/blog"], "scrapling_http"),
        "https://aurora.example/contato": ("Contato: +55 11 99999-0000 equipe@aurora.example", [], "scrapling_http"),
    }
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        return pages[url]

    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", fetch)
    results = [{"source": "web", "url": "https://aurora.example", "title": "Aurora", "public_data": {}}]
    await native_enrich_results(results)
    assert calls == ["https://aurora.example", "https://aurora.example/contato"]
    assert results[0]["public_data"]["pages_inspected"] == 2
    assert results[0]["public_data"]["email"] == "equipe@aurora.example"


@pytest.mark.asyncio
async def test_native_enrichment_never_fetches_meta_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(_url: str):
        raise AssertionError("Meta pages must not enter generic Scrapling enrichment")

    monkeypatch.setattr("kiara_api.hunter._fetch_public_page", forbidden)
    results = [
        {"source": "instagram", "url": "https://instagram.com/public.profile", "title": "Instagram", "public_data": {"website_url": "https://instagram.com/public.profile"}},
        {"source": "facebook", "url": "https://facebook.com/public.page", "title": "Facebook", "public_data": {"website_url": "https://facebook.com/public.page"}},
    ]
    await native_enrich_results(results)
    assert all("enrichment_url" not in row["public_data"] for row in results)


def test_scrapling_fetcher_is_bounded_and_uses_safe_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class Page:
        status = 200
        body = b'<html><body><h1>Clinica</h1><a href="/contato">Contato</a></body></html>'
        headers: ClassVar[dict[str, str]] = {"Content-Type": "text/html; charset=utf-8"}
        encoding = "utf-8"
        url = "https://clinic.example/home"

    class Fetcher:
        @staticmethod
        def get(url, **options):
            captured.update({"url": url, **options})
            return Page()

    import types
    fetchers = types.ModuleType("scrapling.fetchers")
    fetchers.Fetcher = Fetcher
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fetchers)
    monkeypatch.setattr(
        "kiara_api.scraping_adapters.parse_with_scrapling",
        lambda _html, _base_url: ("Clinica Contato", ["https://clinic.example/contato"]),
    )
    text, links, final_url = fetch_public_with_scrapling("https://clinic.example")
    assert text == "Clinica Contato"
    assert links == ["https://clinic.example/contato"]
    assert final_url == "https://clinic.example/home"
    assert captured["follow_redirects"] == "safe"
    assert captured["max_redirects"] == 5
    assert captured["retries"] == 1


@pytest.mark.asyncio
async def test_scrapegraph_path_adds_only_unverified_semantic_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIARA_SCRAPEGRAPH_MODEL", "ollama/test")
    monkeypatch.setattr("kiara_api.hunter._assert_public_destination", lambda _url: None)
    monkeypatch.setattr("kiara_api.hunter.analyze_with_scrapegraph", lambda _url, _prompt: {"activity": "Psicologia"})
    rows = [{"source": "web", "url": "https://clinic.example", "public_data": {
        "enrichment": "completed", "enrichment_url": "https://clinic.example", "phone": None,
    }}]
    await semantic_enrich_results(rows)
    assert rows[0]["public_data"]["semantic_hint"] == {
        "provider": "scrapegraphai", "verified": False, "data": {"activity": "Psicologia"},
    }
    assert rows[0]["public_data"]["phone"] is None
