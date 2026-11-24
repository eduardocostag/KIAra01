"""Several cities in one search, no repeated companies, and WhatsApp-reachable leads first."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api import hunter
from kiara_api.hunter import SearchCreate, execute_research
from kiara_api.hunter_research import (
    address_matches_location,
    lead_identities,
    maps_detail_result,
    national_phone,
    phone_kind,
    split_locations,
)


def maps_row(name, city, phone):
    return maps_detail_result(
        {"summary": "Dentista", "title": name, "url": f"https://www.google.com/maps/place/{name}/data=!1s{name}"},
        {"title": name, "category": "Dentista", "loaded": True, "website": None, "website_button": False,
         "phone": phone, "address": f"Rua das Flores, 10 - Centro, {city} - RS", "links": []})


def test_split_locations_reads_lists_of_cities_but_keeps_city_with_state():
    assert split_locations("Tabaí,Lajeado, Triunfo e Estrela") == ["Tabaí", "Lajeado", "Triunfo", "Estrela"]
    assert split_locations("Porto Alegre, RS") == ["Porto Alegre, RS"]
    assert split_locations("Centro, Curitiba, PR") == ["Centro, Curitiba, PR"]
    assert len(split_locations("Lajeado, lajeado")) == 1
    assert split_locations("") == []


def test_address_in_any_requested_city_matches():
    assert address_matches_location("Rua A, 1 - Centro, Lajeado - RS", "Tabaí, Lajeado, Triunfo")
    assert not address_matches_location("Rua A, 1 - Centro, Canoas - RS", "Tabaí, Lajeado, Triunfo")


def test_phone_formats():
    assert national_phone("051999887766") == "51999887766"
    assert national_phone("+55 51 3714-1234") == "5137141234"
    assert phone_kind("051999887766") == "celular" and phone_kind("05137141234") == "fixo" and phone_kind("") == ""


def test_same_business_has_shared_identity_across_formats():
    a = lead_identities({"public_data": {"phone": "051999887766", "website_url": "https://www.clinica.com.br/contato"}})
    b = lead_identities({"public_data": {"phone": "+5551999887766", "website_url": "https://instagram.com/clinica"}})
    assert "phone:51999887766" in a & b and "site:clinica.com.br" in a and not any(k.startswith("site:") for k in b)


def test_multi_city_search_runs_each_city_skips_known_and_puts_mobiles_first(monkeypatch):
    asked = []

    async def maps(query, limit):
        asked.append(query)
        city = "Lajeado" if "Lajeado" in query else "Estrela"
        return [maps_row(f"Fixo {city}", city, f"0513714{len(asked)}234"),
                maps_row(f"Celular {city}", city, f"05199988{len(asked)}766"),
                maps_row(f"Antigo {city}", city, "051988776655")]

    async def enrich(_rows):
        return None

    monkeypatch.setattr(hunter, "maps_search", maps)
    monkeypatch.setattr(hunter, "enrich_results", enrich)
    search = SearchCreate(market="b2b", query="dentista", location="Lajeado, Estrela", sources=["google_maps"],
                          result_limit=10).model_dump()
    outcome = asyncio.run(execute_research(search, known={"phone:51988776655"}))
    assert sorted("Lajeado" in q for q in asked) == [False, True] and all("," not in q for q in asked)
    titles = [row["title"] for row in outcome["results"]]
    assert not any(title.startswith("Antigo") for title in titles)
    assert {"Fixo Lajeado", "Fixo Estrela", "Celular Lajeado", "Celular Estrela"} <= set(titles)
    order = [({"confirmed": 0, "probable": 1, "to_review": 2}[row["public_data"]["lead_tier"]],
              {"celular": 0, "fixo": 1}.get(row["public_data"]["phone_kind"], 2)) for row in outcome["results"]]
    assert order == sorted(order) and any(kind == 0 for _tier, kind in order)
    assert all(row["public_data"]["phone"].startswith("+55") for row in outcome["results"])
    assert any("já tinha encontrado" in warning for warning in outcome["warnings"])
