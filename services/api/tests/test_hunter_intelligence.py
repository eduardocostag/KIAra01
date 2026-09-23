import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.hunter_intelligence import expand_provider_query, understand_search


def test_understands_entity_service_location_and_presence():
    plan = understand_search(
        "50 dentistas que fazem implante, tenham Instagram e não tenham site",
        "Porto Alegre, RS",
    )
    assert plan["entity"] == "Clínica odontológica"
    assert "implante" in plan["services"]
    assert plan["digital_presence"]["instagram"] is True
    assert plan["digital_presence"]["without_website"] is True
    assert plan["location"] == "Porto Alegre, RS"


def test_expands_professional_synonyms_without_requiring_an_llm():
    query = expand_provider_query("personal trainer", "Canoas")
    assert "educador fisico" in query
    assert "treinador pessoal" in query
    assert query.endswith("Canoas")


def test_understands_problem_based_commercial_intent():
    plan = understand_search("clínicas que provavelmente precisam de marketing", "Porto Alegre")
    assert plan["entity"] == "Clínica médica"
    assert plan["commercial_intent"] == "marketing_opportunity"


def test_unknown_niche_remains_searchable():
    plan = understand_search("restauradores de vitrais históricos", "Pelotas")
    assert plan["entity"] is None
    assert expand_provider_query(plan["raw_query"], plan["location"]) == "\"restauradores de vitrais históricos\" Pelotas"
