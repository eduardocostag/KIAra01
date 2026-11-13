import asyncio

from kiara_api import hunter
from kiara_api.hunter import combine_same_business, merge_maps_rows, public_search


def _row(source, title, url, **data):
    return {"source": source, "title": title, "url": url, "summary": "", "public_data": data}


def test_web_discovery_asks_every_provider_and_interleaves(monkeypatch):
    async def exa(*_):
        return [_row("web", "A1", "https://a1.example"), _row("web", "A2", "https://a2.example")]

    async def firecrawl(*_):
        return [_row("web", "B1", "https://b1.example"), _row("web", "A1 de novo", "https://a1.example")]

    async def index(*_):
        return [_row("web", "C1", "https://c1.example")]

    monkeypatch.setattr(hunter, "exa_search", exa)
    monkeypatch.setattr(hunter, "firecrawl_search", firecrawl)
    monkeypatch.setattr(hunter, "indexed_search", index)
    rows = asyncio.run(public_search("padaria", "web", 10))
    assert [row["title"] for row in rows] == ["A1", "B1", "C1", "A2"]
    assert [row["discovered_by"] for row in rows] == ["exa", "firecrawl", "index", "exa"]


def test_maps_sources_merge_into_one_business_with_all_fields():
    places = _row("google_maps", "Padaria Lua", "https://maps.google.com/?cid=1", place_id="ChIJ1", detail_inspected=True,
                  phone="+55 19 3633-6019", provider="google_places", rating=4.7, user_rating_count=210)
    browser = _row("google_maps", "Padaria Lua", "https://www.google.com/maps/place/Padaria+Lua/data=!4m7!3m6!1sChIJ1!8m2",
                   detail_inspected=True, website_url="https://padarialua.com.br", provider="browserbase")
    other = _row("google_maps", "Padaria Sol", "https://www.google.com/maps/place/Sol/data=!1sChIJ2", detail_inspected=True)
    rows = merge_maps_rows([places, browser, other])
    assert len(rows) == 2
    lua = rows[0]["public_data"]
    assert lua["rating"] == 4.7 and lua["website_url"] == "https://padarialua.com.br" and lua["website_status"] == "present"
    assert rows[0]["providers"] == ["google_places", "browserbase"]


def test_same_business_from_maps_and_website_becomes_one_lead_with_whatsapp():
    maps = _row("google_maps", "Padaria Santuário", "https://www.google.com/maps/place/x/data=!1sA", detail_inspected=True,
                place_id="A", phone="+55 27 3322-3093", website_url="https://padariasantuario.com.br/")
    site = _row("web", "Padaria Santuário - Pães e Doces", "https://padariasantuario.com.br/contato",
                whatsapp_url="https://wa.me/5527999990000", email="contato@padariasantuario.com.br")
    stranger = _row("web", "Outra Empresa", "https://outra.example", phone="+55 27 3322-3093")
    combined, merged = combine_same_business([site, stranger, maps])
    assert merged == 1 and len(combined) == 2
    lead = next(row for row in combined if row["source"] == "google_maps")
    assert lead["public_data"]["whatsapp_url"] == "https://wa.me/5527999990000"
    assert lead["public_data"]["email"] == "contato@padariasantuario.com.br"
    assert lead["public_data"]["also_found_on"] == ["https://padariasantuario.com.br/contato"]


def test_shared_platforms_never_merge_different_businesses():
    one = _row("web", "Padaria Um", "https://www.ifood.com.br/delivery/um", website_url="https://www.ifood.com.br/delivery/um")
    two = _row("web", "Padaria Dois", "https://www.ifood.com.br/delivery/dois", website_url="https://www.ifood.com.br/delivery/dois")
    combined, merged = combine_same_business([one, two])
    assert merged == 0 and len(combined) == 2


def test_enrichment_uses_firecrawl_only_for_leads_the_native_collector_left_incomplete(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    scraped = []

    async def native(results):
        for item in results:
            if item["title"] == "Completo":
                item["public_data"].update({"enrichment": "completed", "phone": "+5511999990000"})

    async def firecrawl(results, key):
        scraped.extend(item["title"] for item in results)

    async def obscura(results):
        return None

    monkeypatch.setattr(hunter, "native_enrich_results", native)
    monkeypatch.setattr(hunter, "_firecrawl_enrich", firecrawl)
    monkeypatch.setattr(hunter, "obscura_enrich_results", obscura)
    rows = [_row("google_maps", "Completo", "https://maps.google.com/1", detail_inspected=True),
            _row("google_maps", "Bloqueado", "https://maps.google.com/2", detail_inspected=True, website_url="https://b.example")]
    asyncio.run(hunter.enrich_results(rows))
    assert scraped == ["Bloqueado"]


def test_browserbase_busy_session_is_retried(monkeypatch):
    class Busy(Exception):
        status_code = 429

    calls = []

    class Sessions:
        def create(self, **_):
            calls.append(1)
            if len(calls) < 2:
                raise Busy()
            return "session"

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(hunter.asyncio, "sleep", no_wait)
    client = type("Client", (), {"sessions": Sessions()})()
    assert asyncio.run(hunter._create_browserbase_session(client, "project")) == "session"
    assert len(calls) == 2
