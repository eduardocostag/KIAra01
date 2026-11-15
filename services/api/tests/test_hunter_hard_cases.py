"""Hard cases found by the Hunter quality battery (2026-11-14)."""
import pytest

from kiara_api.commercial_qualification import qualify_messages
from kiara_api.hunter import combine_same_business
from kiara_api.hunter_research import extract_contacts, is_editorial_or_post
from kiara_api.niche_match import matches_niche


def test_email_at_the_end_of_a_sentence_and_retina_images():
    assert extract_contacts("Fale com a gente: Contato@Clinica.com.br.")["email"] == "contato@clinica.com.br"
    assert "email" not in extract_contacts('<img src="logo@2x.png"> <img src="banner@3x.webp">')
    assert extract_contacts("logo@2x.png e oi@loja.com")["email"] == "oi@loja.com"


@pytest.mark.parametrize("query,observed,expected", [
    ("restaurante japonês", "Temakeria e Sushi Bar Nakami", True),
    ("restaurante japonês", "Churrascaria Gaúcha Fogo de Chão", False),
    ("restaurante japonês", "Restaurante Sabor Caseiro", False),
    ("academia de crossfit", "CrossFit Box Amazonas", True),
    ("academia de crossfit", "Academia Fit Center Musculação", False),
    ("studio de pilates", "Studio Pilates Corpo e Mente", True),
    ("pizzaria italiana", "Cantina Italiana Nonna", True),
    ("empresa de software ERP", "Softplan Sistemas de Gestão", True),
    ("empresa de software ERP", "Padaria Pão Quente", False),
    ("padaria", "Pizzaria Bella Napoli", False),
])
def test_niche_types_inside_a_family(query, observed, expected):
    assert matches_niche(query, observed) is expected


@pytest.mark.parametrize("title,url", [
    ("Dentistas perto de você - Encontre agora", "https://www.encontreumdentista.com.br/rs/porto-alegre"),
    ("Encontre um advogado em Curitiba", "https://www.achaadvogado.com.br/curitiba"),
    ("Guia de restaurantes japoneses em SP", "https://guia.example.com.br/japoneses"),
])
def test_directory_listings_are_not_leads(title, url):
    assert is_editorial_or_post({"source": "web", "title": title, "url": url})


def test_shared_phone_with_only_a_generic_word_keeps_businesses_apart():
    rows = [
        {"source": "google_maps", "title": "Clínica Sorriso Feliz", "public_data": {"place_id": "a", "phone": "(51) 3333-4444"}},
        {"source": "instagram", "title": "Sorriso Feliz", "url": "https://instagram.com/sorrisofeliz", "public_data": {"phone": "51 3333-4444"}},
        {"source": "google_maps", "title": "Clínica Dente de Leite", "public_data": {"place_id": "b", "phone": "(51) 3333-4444"}},
    ]
    combined, merged = combine_same_business(rows)
    assert [row["title"] for row in combined] == ["Clínica Sorriso Feliz", "Clínica Dente de Leite"] and merged == 1


def inbound(*texts):
    return qualify_messages([{"direction": "inbound", "text": text} for text in texts])


def test_qualification_reads_portuguese_nuance():
    assert inbound("Oi! Quanto custa o plano anual? Preciso pra essa semana")["score"] >= 60
    leaving_work = inbound("Vou sair do trabalho às 18h, me liga amanhã que quero fechar")
    assert not leaving_work["optout"] and leaving_work["score"] >= 50
    assert inbound("Sem problema, pode mandar o orçamento")["score"] >= 30
    assert inbound("Me tira da sua lista, por favor")["optout"]
    assert inbound("Quero sair da lista")["optout"]
    assert inbound("Gostei, mas não tenho orçamento agora")["score"] <= 10


def test_requested_specialty_ranks_first():
    from kiara_api.hunter_research import apply_lead_tier, specialty_terms

    terms = specialty_terms({"query": "advogado previdenciário"})
    assert terms == ["previdenciario"]
    generic = {"title": "Sinuhe Advocacia Trabalhista", "public_data": {"phone": "5599999999", "rating": 4.9, "user_rating_count": 200}}
    focused = {"title": "MD Prev Auxílio Acidente", "public_data": {"phone": "5598888888"}}
    for row in (generic, focused):
        apply_lead_tier(row, "confirmed", terms)
    assert focused["public_data"]["specialty_match"] and not generic["public_data"]["specialty_match"]
    assert focused["public_data"]["temperature_reasons"][0] == "Especialidade pedida aparece no nome ou na descrição"
    assert specialty_terms({"query": "clínica veterinária 24 horas"}) == ["24h"]


def test_weak_site_signals_are_verifiable():
    from kiara_api.hunter_research import brazilian_mobile, website_opportunity

    text = " ".join(["conteudo"] * 120) + " Tel: (53) 3222-1111 © 2017 Pneus Bom"
    links = ["https://pneusbom.wixsite.com/loja/a", "https://pneusbom.wixsite.com/loja/b"]
    score, signals = website_opportunity("https://pneusbom.wixsite.com/loja", text, links)
    assert score <= 55 and "Site em subdomínio gratuito (wixsite.com)" in signals
    assert any(signal.startswith("Rodapé com ano 2017") for signal in signals)
    modern = " ".join(["conteudo"] * 120) + " Tel: (53) 3222-1111 © 2025"
    good = ["https://pneus.com.br/a", "https://pneus.com.br/b", "https://wa.me/5553999998888"]
    assert website_opportunity("https://pneus.com.br", modern, good) == (100, [])
    assert [brazilian_mobile(x) for x in ("53999998888", "+55 53 99999-8888", "5332221111")] == [True, True, False]
