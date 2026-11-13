import pytest


@pytest.fixture(autouse=True)
def _no_live_discovery_providers(monkeypatch):
    """Discovery providers run together, so tests must never reach the real web by accident.

    Each provider fails fast here, as an unconfigured one does in production; a test that needs a
    provider replaces it with its own fake (a later monkeypatch wins).
    """
    from kiara_api import hunter

    async def offline(*_args, **_kwargs):
        raise RuntimeError("public_index_unavailable")

    monkeypatch.setattr(hunter, "indexed_search", offline)
    for name in ("EXA_API_KEY", "FIRECRAWL_API_KEY", "GOOGLE_PLACES_API_KEY", "KIARA_MAPS_SCRAPER_EXECUTABLE",
                 "OBSCURA_CDP_URL", "BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID", "KIARA_SCRAPEGRAPH_MODEL"):
        monkeypatch.delenv(name, raising=False)
