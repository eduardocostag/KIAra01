import asyncio
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.hunter import SearchCreate, research_query


@pytest.mark.parametrize("niche,objective", [
    ("psicólogos", "atendimento aos sábados"),
    ("restaurantes", "com opções veganas"),
    ("lojas de roupas", "que vendem no Instagram"),
])
def test_arbitrary_objective_is_sent_to_search(niche, objective):
    request = SearchCreate(market="b2b", query=niche, location="São Paulo",
                           sources=["web"], research_mode="focused", objective=objective)
    query = research_query(request.model_dump())
    assert niche in query and objective in query and "São Paulo" in query


def test_broad_search_ignores_previous_objective():
    request = SearchCreate(market="b2c", query="  corredores  ", sources=["instagram"],
                           research_mode="broad", objective="objetivo antigo")
    assert research_query(request.model_dump()) == "corredores"


def test_empty_focus_and_optional_location_fall_back_to_broad():
    request = SearchCreate(market="b2b", query="padarias", sources=["google_maps"],
                           research_mode="focused", objective="  ")
    assert research_query(request.model_dump()) == "padarias"


def test_whitespace_only_niche_is_rejected():
    with pytest.raises(ValidationError):
        SearchCreate(market="b2b", query="   ", sources=["web"])
