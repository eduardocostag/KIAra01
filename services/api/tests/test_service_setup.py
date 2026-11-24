import pytest

from kiara_api import service_setup as ss


def test_the_client_setup_wins_and_the_niche_fills_the_gaps():
    block = ss.service_block({"niche": "odontologia", "services": [{"name": "Avaliação", "price": "R$ 100"}, {"name": "Implante", "price": ""}],
                              "hours": "Seg a sex, 8h às 18h", "payment": "Unimed Odonto e Pix", "tone": "formal", "emojis": False})
    assert "Nicho: Odontologia." in block and "- Avaliação: R$ 100" in block and "- Implante: valor sob consulta" in block
    assert "Convênios e formas de pagamento: Unimed Odonto e Pix" in block
    assert "agendar uma avaliação" in block and "Convênio ou particular" in block  # niche defaults for goal and discovery
    assert "código de ética odontológico" in block and "Não use emojis." in block and "formal" in block
    custom = ss.service_block({"niche": "imobiliaria", "goal": "handoff", "discover": ["Bairro"], "handoff": "Sempre que pedirem desconto."})
    assert "passar o contato para um vendedor" in custom and "Bairro." in custom and "Comprar ou alugar" not in custom
    assert "Sempre que pedirem desconto." in custom and "Proposta" not in custom


def test_hidden_prices_and_other_niche():
    block = ss.service_block({"niche": "outro", "niche_other": "Pet shop", "hide_prices": True, "services": [{"name": "Banho", "price": "R$ 50"}]})
    assert "Nicho: Pet shop." in block and "R$ 50" not in block and "Não informe preços" in block


def test_nothing_configured_adds_nothing_and_bad_data_is_ignored():
    assert ss.service_block({}) == "" and ss.service_block(None) == "" and ss.service_block("x") == ""
    assert ss.stored_setup({"niche": "odontologia", "future_field": 1}).niche == "odontologia"
    assert ss.stored_setup({"services": "nope"}).niche == ""
    with pytest.raises(ValueError):
        ss.ServiceSetup.model_validate({"niche": "Odonto!"})
    assert {item["id"] for item in ss.niche_catalog()} >= {"odontologia", "imobiliaria", "advocacia"}
    assert all(item["goal"] in ss.GOALS for item in ss.niche_catalog())
