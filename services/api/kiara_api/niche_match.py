"""Does a business belong to the niche the user searched for? Works for any niche.

Two mistakes to avoid, for every niche, including ones nobody listed:
* accepting a sibling of the same family ("pizzaria" for a "padaria" search);
* rejecting the same niche written differently ("Advocacia" for "advogado",
  "Restaurador de móveis" for "restauração de móveis", plural and gender variants).

Words are compared by their root (prefix stem), so derivations match without a dictionary;
`SYNONYMS` only covers real synonyms whose roots differ. Family siblings are never synonyms.
"""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset({
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas", "para", "pra", "com",
    "por", "um", "uma", "que", "sem", "ou", "loja", "lojas", "empresa", "empresas", "servico", "servicos", "negocio",
    "negocios", "perto", "proximo", "melhor", "melhores", "regiao", "cidade", "bairro", "centro",
})

# Qualifiers describe a niche but rarely appear in a business name or Maps category.
QUALIFIERS = frozenset({
    "feminina", "femininas", "feminino", "femininos", "masculina", "masculinas", "masculino", "masculinos", "infantil",
    "infantis", "artesanal", "artesanais", "premium", "popular", "populares", "barato", "baratos", "gourmet", "importados",
    "importadas", "usados", "usadas", "novos", "novas", "24h", "24", "horas", "delivery", "online", "especializada",
    "especializado", "profissional", "profissionais", "qualidade", "pequena", "pequenas", "grande", "grandes",
})

# Groups of real synonyms (different roots, same business). Never put siblings together.
SYNONYMS: tuple[tuple[str, ...], ...] = (
    ("dentista", "odontologia", "odontologo", "consultorio odontologico", "clinica odontologica", "implantodontia", "ortodontia", "ortodontista"),
    ("padaria", "panificadora", "panificacao", "padoca", "panificio"),
    ("confeitaria", "doceria", "boleria", "bolos", "doces"),
    ("advogado", "advocacia", "escritorio juridico", "assessoria juridica", "juridico"),
    ("contador", "contabilidade", "escritorio contabil", "contabil"),
    ("psicologo", "psicologia", "psicoterapia", "psicoterapeuta", "psicanalista", "psicanalise"),
    ("nutricionista", "nutricao"),
    ("fisioterapeuta", "fisioterapia", "reabilitacao"),
    ("veterinario", "veterinaria", "clinica veterinaria", "hospital veterinario"),
    ("pet shop", "petshop", "banho e tosa", "pet center"),
    ("academia", "fitness", "musculacao", "centro de treinamento"),
    ("personal trainer", "personal", "treinador pessoal", "educador fisico"),
    ("salao de beleza", "cabeleireiro", "cabelereiro", "cabeleireira", "hair", "studio de beleza"),
    ("barbearia", "barbeiro", "barber"),
    ("manicure", "pedicure", "nail", "esmalteria", "unhas"),
    ("estetica", "esteticista", "clinica de estetica", "centro estetico"),
    ("mecanico", "oficina mecanica", "auto center", "autocenter", "mecanica automotiva", "centro automotivo"),
    ("imobiliaria", "corretor de imoveis", "corretora de imoveis", "imoveis", "consultoria imobiliaria"),
    ("arquiteto", "arquitetura", "escritorio de arquitetura"),
    ("engenheiro", "engenharia"),
    ("pizzaria", "pizza", "pizzas"),
    ("hamburgueria", "burger", "hamburguer", "lanchonete", "lanches"),
    ("cafeteria", "cafe", "coffee"),
    ("restaurante", "bistro", "cantina", "churrascaria"),
    ("farmacia", "drogaria"),
    ("otica", "oculos"),
    ("escola", "colegio", "ensino"),
    ("creche", "bercario", "educacao infantil"),
    ("hotel", "pousada", "hostel", "hospedagem"),
    ("medico", "clinica medica", "consultorio medico", "centro medico"),
    ("energia solar", "fotovoltaica", "fotovoltaico", "painel solar", "placas solares"),
    ("ar condicionado", "climatizacao", "refrigeracao"),
    ("eletricista", "instalacoes eletricas", "servicos eletricos"),
    ("encanador", "hidraulica", "desentupidora"),
    ("marcenaria", "marceneiro", "moveis planejados", "moveis sob medida"),
    ("dedetizadora", "dedetizacao", "controle de pragas"),
    ("agencia de marketing", "marketing digital", "agencia digital", "publicidade"),
    ("grafica", "impressao", "comunicacao visual"),
    ("transportadora", "transporte", "logistica", "frete"),
    ("seguradora", "corretora de seguros", "seguros"),
    ("autoescola", "auto escola", "centro de formacao de condutores", "cfc"),
)


def fold(value: str) -> str:
    text = unicodedata.normalize("NFD", (value or "").lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", fold(value))


def stem(word: str) -> str:
    """Prefix root: 'odontologia' -> 'odontolo', 'restauracao' -> 'restaur', 'padarias' -> 'padari'."""
    word = word.rstrip("s") if len(word) > 3 else word
    if len(word) <= 5:
        return word
    return word[:max(5, len(word) - 3)]


def _phrase_present(phrase: str, observed: list[str]) -> bool:
    parts = [stem(part) for part in words(phrase) if part not in STOPWORDS]
    return bool(parts) and all(any(word.startswith(part) for word in observed) for part in parts)


def niche_terms(query: str) -> list[str]:
    """The user's own wording plus the synonym groups it mentions (never the whole family)."""
    folded = " " + " ".join(words(query)) + " "
    terms = [query]
    for group in SYNONYMS:
        if any(_phrase_present(member, words(query)) or f" {member} " in folded for member in group):
            terms.extend(group)
    return list(dict.fromkeys(terms))


# Single words with different roots but the same meaning in a service name.
WORD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "conserto": ("reparo", "assistencia", "manutencao", "concerto"),
    "reparo": ("conserto", "assistencia", "manutencao"),
    "manutencao": ("conserto", "reparo", "assistencia"),
    "instalacao": ("instalador", "instaladora"),
    "aula": ("curso", "escola", "professor"),
    "curso": ("aula", "escola"),
    "aluguel": ("locacao", "locadora"),
    "locacao": ("aluguel", "locadora"),
    "venda": ("loja", "comercio", "revenda"),
    "celular": ("smartphone", "iphone", "telefone"),
    "carro": ("automovel", "automotivo", "veiculo", "auto"),
    "moto": ("motocicleta", "motos"),
    "cachorro": ("cao", "caes", "pet"),
    "crianca": ("infantil", "kids"),
    "casamento": ("noiva", "noivas", "nupcial"),
}


def _word_present(word: str, observed: list[str]) -> bool:
    synonyms = WORD_SYNONYMS.get(word) or WORD_SYNONYMS.get(word.rstrip("s"), ())
    options = [stem(word), *(stem(option) for option in synonyms)]
    return any(item.startswith(option) for option in options for item in observed)


def matches_niche(query: str, observed_text: str) -> bool:
    observed = words(observed_text)
    if not observed:
        return False
    for term in niche_terms(query)[1:]:
        if _phrase_present(term, observed):
            return True
    # Any niche, listed or not: the main word and most of the meaningful words, by root or synonym.
    significant = [word for word in words(query) if word not in STOPWORDS and word not in QUALIFIERS and len(word) >= 3]
    if not significant:
        # Generic searches ("lojas", "empresas"): fall back to the words themselves.
        significant = [word for word in words(query) if len(word) >= 4]
    if not significant:
        return False
    found = sum(_word_present(word, observed) for word in significant)
    return _word_present(significant[0], observed) and found >= len(significant) // 2 + 1 or found == len(significant)
