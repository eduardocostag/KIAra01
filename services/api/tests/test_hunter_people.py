"""Who decides at a hunted business: registry partners first, then names with a role on the site, then the Maps title."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api import hunter
from kiara_api.hunter_people import decision_maker, people_from_text, person_from_title, title_case_name
from kiara_api.sdr import contact_profile


def test_names_with_role_or_registry_on_the_site():
    text = ("Clínica Sorriso Feliz. Proprietária: Ana Paula Souza. Nossa equipe: Dr. Carlos Lima - CRO-RS 12345. "
            "Responsável técnico: Dra. Beatriz Rocha. Rua das Flores, 10. Todos os direitos reservados.")
    people = people_from_text(text)
    assert {"name": "Ana Paula Souza", "role": "Proprietário(a)", "source": "site"} in people
    assert any(p["name"] == "Carlos Lima" for p in people)
    assert any(p["name"] == "Beatriz Rocha" and p["role"] == "Responsável técnico(a)" for p in people)
    assert not any("Clínica" in p["name"] or "Rua" in p["name"] for p in people)


def test_no_invented_names():
    assert people_from_text("Agende sua consulta pelo WhatsApp. Atendimento de segunda a sexta.") == []
    assert person_from_title("Clínica Odontológica Central") is None
    assert person_from_title("Dra. Ana Souza | Odontologia")["name"] == "Ana Souza"


def test_registry_partner_wins_and_uses_the_friendlier_site_name():
    company = {"partners": [{"name": "JOAO PEREIRA", "role": "Sócio"}, {"name": "ANA PAULA SOUZA", "role": "Sócio-Administrador"}]}
    site = [{"name": "Ana Paula Souza", "role": "Dra.", "source": "site"}]
    assert decision_maker(company, site, "Clínica") == {"name": "Ana Paula Souza", "role": "Sócio-Administrador", "source": "receita"}
    assert decision_maker(company, [], "")["name"] == "Ana Paula Souza"
    assert title_case_name("MARIA DA SILVA") == "Maria da Silva"


def test_mei_owner_comes_from_the_legal_name():
    company = {"mei": True, "partners": [], "legal_name": "45.123.456 MARIA DA SILVA"}
    assert decision_maker(company, [], "") == {"name": "Maria da Silva", "role": "Titular (MEI)", "source": "receita"}


def test_identify_decision_makers_looks_up_cnpj_and_falls_back_to_site_and_title():
    calls = []

    def lookup(cnpj):
        calls.append(cnpj)
        return {"cnpj": cnpj, "partners": [{"name": "CARLA MENDES", "role": "Sócio-Administrador"}]}

    results = [
        {"title": "Studio X", "public_data": {"cnpj": "11222333000181"}},
        {"title": "Clínica Y", "public_data": {"site_people": [{"name": "Rui Alves", "role": "Proprietário(a)", "source": "site"}]}},
        {"title": "Dr. Paulo Nunes", "public_data": {}},
        {"title": "Pizzaria Z", "public_data": {}},
    ]
    assert asyncio.run(hunter.identify_decision_makers(results, lookup=lookup)) == 3
    assert calls == ["11222333000181"]
    assert results[0]["public_data"]["decision_maker"]["name"] == "Carla Mendes"
    assert results[0]["public_data"]["company"]["cnpj"] == "11222333000181"
    assert results[1]["public_data"]["decision_maker"]["source"] == "site" and "site_people" not in results[1]["public_data"]
    assert results[2]["public_data"]["decision_maker"] == {"name": "Paulo Nunes", "role": "Dr.", "source": "maps"}
    assert "decision_maker" not in results[3]["public_data"]


def test_sdr_knows_who_is_in_charge():
    lines = contact_profile({"hunter": {"decision_maker": {"name": "Carla Mendes", "role": "Sócio-Administrador"}}})
    assert "Responsável pela empresa: Carla Mendes (Sócio-Administrador)" in lines
