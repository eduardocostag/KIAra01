import pytest

from kiara_api.niche_match import matches_niche

CASES = [
    ("padaria", "Don Aurélio Rodízio de Pizza · Pizzaria", False),
    ("padaria", "Padoca do Bairro · Padaria", True),
    ("padaria", "Panificadora Estrela · Panificadora", True),
    ("dentista", "Clínica Oral Unic · Clínica odontológica", True),
    ("dentista", "Ortodontia Sorriso · Ortodontista", True),
    ("advogado trabalhista", "Silva & Souza Advocacia · Escritório de advocacia", True),
    ("advogado", "Imobiliária Central · Imobiliária", False),
    ("restauração de móveis antigos", "Ateliê Madeira Viva · Restaurador de móveis", True),
    ("conserto de celular", "TecFix · Loja de reparo de celulares", True),
    ("conserto de celular", "Claro · Loja de celulares", False),
    ("conserto de celular", "Bike Fix · Reparo de bicicletas", False),
    ("energia solar", "Gera Mais · Empresa de energia fotovoltaica", True),
    ("pet shop", "Banho e Tosa Amigo · Pet shop", True),
    ("pet shop", "Clínica Vet Vida · Veterinário", False),
    ("contabilidade", "Escritório Contábil Alfa · Contador", True),
    ("salão de beleza", "Studio Hair Ana · Cabeleireiro", True),
    ("salão de beleza", "Barbearia do Zé · Barbearia", False),
    ("tatuador", "Ink Studio · Estúdio de tatuagem", True),
    ("climatização", "Frio Total · Serviço de ar-condicionado", True),
    ("autoescola", "CFC Volante · Centro de formação de condutores", True),
    ("aluguel de carros", "Localiza · Locadora de veículos", True),
    ("loja de roupas femininas", "Moda Bella · Loja de roupas", True),
    ("loja de roupas femininas", "Calçados Bia · Loja de calçados", False),
    ("cerveja artesanal", "Cervejaria Lupulus · Cervejaria", True),
    ("material de construção", "Casa do Construtor · Loja de materiais de construção", True),
    ("lavanderia", "Lava Bem · Lavanderia", True),
    ("lavanderia", "Lava Rápido Top · Lava-jato", False),
    ("lojas", "Loja", True),
]


@pytest.mark.parametrize(("query", "listing", "expected"), CASES)
def test_niche_matching_handles_synonyms_roots_and_siblings(query, listing, expected):
    assert matches_niche(query, listing) is expected
