from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from kiara_api.adapters.postgres import PostgresRepository
from kiara_api.hunter import HunterRepository, SearchCreate
from kiara_api.hunter_research import filter_results, normalize_result, result_niche_matches


@pytest.mark.parametrize(("query", "title", "summary", "matches"), [
    ("psicologos", "O Gato da Praca Pub", "Bar e restaurante", False),
    ("psicologos", "Instituto IBET", "Instituto de educacao tributaria", False),
    ("psicologos", "Psicologa Samanta Wessel", "Psicologia clinica", True),
    ("pilates", "Martins Lanches", "Restaurante e lancheria", False),
    ("pilates", "Estudio Mateus Rupp", "Aulas de pilates", True),
    ("pilates", "Academia Geral", "Musculacao e fitness", False),
    ("clinicas odontologicas", "Clinica de Psicologia", "Psicoterapia", False),
    ("clinicas odontologicas", "Clinica Aurora", "Odontologia e implantes", True),
])
def test_business_must_match_requested_niche(query, title, summary, matches):
    assert result_niche_matches({"title": title, "summary": summary}, {"query": query}) is matches


def test_dictionary_is_rejected_even_if_contact_and_location_are_present():
    item = {"source": "web", "title": "Significado de telefone no Dicionario Estraviz",
            "url": "https://dictionary.example/telefone", "summary": "Telefone em Porto Alegre",
            "public_data": {"phone": "5132251122", "address": "Porto Alegre",
                            "address_evidence": "verified_public_page"}}
    assert filter_results([item], {"query": "telefone", "location": "Porto Alegre"})[0] == []


def test_directory_footer_contact_cannot_be_imported_as_a_listed_business():
    item = {"source": "web", "title": "Estudio de Pilates", "summary": "Pilates em Lajeado",
            "url": "https://www.locaisdobrasil.com.br/encontre/estudio-de-pilates/lajeado-rs/studio/123",
            "public_data": {"phone": "5132251122", "address": "Lajeado RS",
                            "address_evidence": "verified_public_page"}}
    assert filter_results([item], {"query": "pilates", "location": "Lajeado RS"})[0] == []


def test_seo_heading_is_not_used_when_source_title_contains_its_domain_brand():
    title = "Da descoberta a decisao: encontre o psicologo ideal - CENTRAL TERAPIA"
    result = normalize_result({"source": "web", "title": title, "url": "https://centralterapia.example/"})
    assert result["public_data"]["display_name"] == "CENTRAL TERAPIA"
    assert result["public_data"]["source_title"] == title
    assert result["public_data"]["name_status"] == "source_title"


@pytest.mark.parametrize("query", ["telefone", "leads quentes", "whatsapp", "contatos"])
def test_contact_filter_without_business_niche_is_not_a_valid_search(query):
    with pytest.raises(ValueError, match="tipo de neg"):
        SearchCreate(market="b2b", query=query, sources=["web"])


def test_saved_broad_history_does_not_reintroduce_incomplete_candidates():
    row = {"id": uuid4(), "market": "b2b", "query": "psicologos", "location": "Porto Alegre",
           "sources": ["web"], "result_limit": 10, "status": "completed", "confirmed_at": None,
           "created_at": datetime.now(UTC), "error_code": None}
    items = [{"id": str(uuid4()), "source": "web", "title": "Dicionario de telefone",
              "url": "https://dictionary.example/telefone", "summary": "", "public_data": {}}]
    before = deepcopy(items)
    result = HunterRepository._search(row, items)
    assert result["results"] == []
    assert result["warnings"]
    assert items == before


def test_historical_crm_contact_is_flagged_without_deleting_or_claiming_interest():
    row = {"id": uuid4(), "consumer_id": uuid4(), "display_name": "O Gato da Praca Pub",
           "instagram_username": None, "attributes": {"hunter": {"source": "web",
               "source_url": "https://pub.example/", "research_query": "psicologos",
               "phone": "5132251122", "address": "Porto Alegre", "location": "Porto Alegre",
               "address_evidence": "verified_public_page"}}, "stage": "new", "next_action": None,
           "version": 1, "updated_at": datetime.now(UTC)}
    before = deepcopy(row)
    result = object.__new__(PostgresRepository)._pipeline(row)
    assert result["consumer"]["prospecting_status"] == "review_required"
    assert "niche_match" in result["consumer"]["quality_gaps"]
    assert result["qualification"] is None
    assert row == before
