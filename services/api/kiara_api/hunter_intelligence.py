"""Commercial intent parsing and deterministic query expansion for Hunter.

The ontology is deliberately local and deterministic: it improves recall even
when no LLM is configured, while keeping every provider query auditable.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Any


def _fold(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value.lower())
                   if unicodedata.category(char) != "Mn")


@dataclass(frozen=True)
class CommercialEntity:
    canonical: str
    terms: tuple[str, ...]
    services: tuple[str, ...] = ()
    audiences: tuple[str, ...] = ()


# Covers the broad commercial families in the product specification. The most
# ambiguous/high-volume families carry richer service vocabularies; unknown
# niches still pass through unchanged and are never rejected by this ontology.
ONTOLOGY: tuple[CommercialEntity, ...] = (
    CommercialEntity("Clínica odontológica", ("dentista", "odontologo", "odontologia", "clinica odontologica", "consultorio odontologico", "centro odontologico"), ("implante", "implantodontia", "aparelho", "alinhador", "ortodontia", "clareamento", "faceta", "canal", "protese", "odontopediatria")),
    CommercialEntity("Clínica médica", ("medico", "clinica", "clinica medica", "consultorio medico", "centro medico", "policlinica"), ("cardiologia", "neurologia", "psiquiatria", "dermatologia", "endocrinologia", "ortopedia", "ginecologia", "pediatria", "geriatria", "oftalmologia")),
    CommercialEntity("Psicologia e saúde mental", ("psicologo", "psicologa", "psicologia", "psicoterapia", "terapeuta", "psicanalista", "neuropsicologo"), ("terapia de casal", "terapia infantil", "ansiedade", "depressao", "burnout", "tdah", "avaliacao neuropsicologica")),
    CommercialEntity("Nutrição", ("nutricionista", "nutricao", "clinica de nutricao", "reeducacao alimentar"), ("emagrecimento", "hipertrofia", "nutricao esportiva", "nutricao funcional", "nutricao comportamental")),
    CommercialEntity("Educação física e fitness", ("personal trainer", "personal training", "educador fisico", "treinador pessoal", "preparador fisico", "academia", "studio fitness", "estudio de treinamento"), ("treinamento funcional", "musculacao", "crossfit", "pilates", "yoga", "corrida", "calistenia", "emagrecimento", "hipertrofia"), ("idosos", "gestantes", "atletas")),
    CommercialEntity("Fisioterapia e reabilitação", ("fisioterapeuta", "fisioterapia", "clinica de fisioterapia", "osteopatia", "quiropraxia", "reabilitacao"), ("rpg", "pos-operatorio", "coluna", "dor lombar", "fisioterapia esportiva", "fisioterapia pelvica")),
    CommercialEntity("Estética", ("clinica estetica", "esteticista", "centro estetico", "estetica facial", "estetica corporal"), ("harmonizacao facial", "botox", "preenchimento", "peeling", "limpeza de pele", "depilacao a laser", "criolipolise")),
    CommercialEntity("Beleza pessoal", ("salao de beleza", "cabeleireiro", "barbearia", "barbeiro", "manicure", "nail designer", "lash designer", "maquiador"), ("corte", "coloracao", "progressiva", "sobrancelha", "extensao de cilios")),
    CommercialEntity("Pet", ("veterinario", "clinica veterinaria", "hospital veterinario", "pet shop", "banho e tosa", "adestrador", "dog walker")),
    CommercialEntity("Advocacia", ("advogado", "advocacia", "escritorio de advocacia"), ("trabalhista", "empresarial", "tributaria", "previdenciaria", "criminal", "familia", "lgpd", "inventario", "divorcio", "registro de marcas")),
    CommercialEntity("Contabilidade", ("contador", "contabilidade", "escritorio contabil"), ("mei", "abertura de empresa", "bpo financeiro", "planejamento tributario", "imposto de renda")),
    CommercialEntity("Serviços financeiros", ("consultor financeiro", "planejador financeiro", "assessoria financeira", "corretora de seguros", "seguros", "consorcio", "credito empresarial")),
    CommercialEntity("Imobiliário", ("corretor de imoveis", "imobiliaria", "construtora", "incorporadora", "loteadora", "administradora de imoveis", "sindico profissional")),
    CommercialEntity("Arquitetura e engenharia", ("arquiteto", "arquitetura", "engenheiro", "engenharia", "escritorio de engenharia"), ("projeto arquitetonico", "reforma", "paisagismo", "calculo estrutural", "laudo tecnico", "ppci", "inspecao predial")),
    CommercialEntity("Construção civil", ("construtora", "empreiteira", "pedreiro", "pintor", "eletricista", "encanador", "gesseiro", "drywall", "telhadista", "vidracaria", "marcenaria", "serralheria")),
    CommercialEntity("Energia solar", ("energia solar", "empresa solar", "painel fotovoltaico", "integrador solar", "projeto fotovoltaico", "usina solar")),
    CommercialEntity("Climatização", ("ar condicionado", "climatizacao", "refrigeracao", "hvac", "pmoc", "camara fria"), ("instalacao", "manutencao", "limpeza", "climatizacao comercial", "climatizacao industrial")),
    CommercialEntity("Segurança eletrônica", ("seguranca eletronica", "cftv", "cameras", "alarmes", "monitoramento", "controle de acesso", "portaria remota")),
    CommercialEntity("Tecnologia da informação", ("empresa de ti", "suporte de ti", "help desk", "msp", "infraestrutura", "redes", "servidores", "consultoria de ti", "ciberseguranca", "cloud computing")),
    CommercialEntity("Software e automação", ("software house", "fabrica de software", "desenvolvimento de sistemas", "saas", "erp", "crm", "inteligencia artificial", "chatbot", "rpa", "automacao empresarial")),
    CommercialEntity("Marketing e comunicação", ("agencia de marketing", "agencia digital", "social media", "gestor de trafego", "marketing", "seo", "branding", "copywriter", "designer grafico", "produtora audiovisual")),
    CommercialEntity("Eventos", ("organizador de eventos", "cerimonialista", "buffet", "salao de festas", "espaco para eventos", "decoracao de festas", "dj")),
    CommercialEntity("Alimentação", ("restaurante", "pizzaria", "hamburgueria", "sushi", "churrascaria", "cafeteria", "padaria", "confeitaria", "doceria", "delivery", "marmitas")),
    CommercialEntity("Hotelaria e turismo", ("hotel", "pousada", "hostel", "resort", "motel", "agencia de viagens", "agencia de turismo", "transfer", "guia turistico")),
    CommercialEntity("Educação", ("escola", "colegio", "creche", "bercario", "professor particular", "curso preparatorio", "faculdade", "universidade", "escola tecnica", "escola de idiomas")),
    CommercialEntity("Recursos humanos e consultoria", ("consultoria de rh", "recrutamento e selecao", "headhunter", "treinamento corporativo", "consultor empresarial", "consultoria empresarial")),
    CommercialEntity("Logística e transporte", ("transportadora", "logistica", "frete", "courier", "motoboy", "armazenagem", "operador logistico", "empresa de mudancas", "transporte executivo")),
    CommercialEntity("Automotivo", ("oficina mecanica", "mecanico", "auto center", "eletrica automotiva", "funilaria", "estetica automotiva", "lava rapido", "borracharia", "concessionaria", "loja de carros", "autopecas")),
    CommercialEntity("Indústria e metalurgia", ("industria", "metalurgica", "usinagem", "torno cnc", "caldeiraria", "estruturas metalicas", "manutencao industrial", "maquinas industriais")),
    CommercialEntity("Agronegócio", ("produtor rural", "fazenda", "agropecuaria", "cooperativa", "revenda agricola", "agronomo", "consultoria agronomica", "maquinas agricolas")),
    CommercialEntity("Limpeza e facilities", ("empresa de limpeza", "limpeza residencial", "limpeza comercial", "limpeza pos-obra", "facilities", "manutencao predial", "zeladoria", "dedetizadora", "controle de pragas", "jardinagem")),
    CommercialEntity("Casa, móveis e decoração", ("loja de moveis", "moveis planejados", "marceneiro", "loja de decoracao", "cortinas", "persianas", "material de construcao", "ferragem", "madeireira")),
    CommercialEntity("Moda e varejo", ("loja de roupas", "moda feminina", "moda masculina", "moda infantil", "boutique", "loja de calcados", "joalheria", "semijoias", "otica", "loja virtual", "ecommerce")),
    CommercialEntity("Gráfica e comunicação visual", ("grafica", "comunicacao visual", "impressao digital", "banner", "adesivo", "fachada", "brindes personalizados")),
    CommercialEntity("Telecom", ("provedor de internet", "internet fibra", "isp", "telefonia empresarial", "pabx", "voip", "telecomunicacoes")),
    CommercialEntity("Saúde ocupacional", ("medicina do trabalho", "saude ocupacional", "clinica ocupacional", "seguranca do trabalho", "pcmso", "pgr", "ltcat", "exame admissional")),
    CommercialEntity("Farmácia e diagnóstico", ("farmacia", "drogaria", "farmacia de manipulacao", "laboratorio de analises clinicas", "clinica de imagem", "ultrassom", "ressonancia", "tomografia")),
    CommercialEntity("Cuidados e terapias", ("fonoaudiologo", "acupuntura", "massoterapia", "casa de repouso", "cuidador de idosos", "home care", "enfermagem domiciliar", "doula")),
    CommercialEntity("Serviços empresariais", ("representante comercial", "distribuidora", "atacadista", "fornecedor industrial", "bpo", "empresa de cobranca", "certificado digital", "despachante", "coworking", "franquia")),
    CommercialEntity("Comércio exterior", ("importadora", "exportadora", "trading company", "despachante aduaneiro", "freight forwarder")),
    CommercialEntity("Sustentabilidade e resíduos", ("consultoria ambiental", "licenciamento ambiental", "gestao de residuos", "coleta de residuos", "reciclagem", "cacamba")),
    CommercialEntity("Criadores de conteúdo", ("influenciador", "creator", "criador de conteudo", "ugc creator", "microinfluenciador")),
)

_DIGITAL_SIGNALS = {
    "instagram": (r"\bcom instagram\b", r"\btenham? instagram\b", r"\bpossua(?:m)? instagram\b"),
    "without_instagram": (r"\bsem instagram\b", r"\bnao (?:tem|possui) instagram\b"),
    "website": (r"\bcom (?:site|website)\b",),
    "without_website": (r"\bsem (?:site|website)\b", r"\bnao (?:tem|tenham?|possui|possuam?) (?:site|website)\b"),
    "whatsapp": (r"\bcom whatsapp\b",),
    "email": (r"\bcom e-?mail\b",),
    "google_business": (r"\bcom google (?:meu negocio|business)\b",),
}

_COMMERCIAL_INTENTS = {
    "marketing_opportunity": ("precisa de marketing", "precisam de marketing", "oportunidade de marketing"),
    "software_opportunity": ("precisa de sistema", "precisam de sistema", "precisa de automacao", "processo manual"),
    "solar_opportunity": ("comprar energia solar", "precisa de energia solar", "alto consumo eletrico"),
}


def _contains(text: str, term: str) -> bool:
    normalized = _fold(term)
    return bool(re.search(rf"(?<!\w){re.escape(normalized)}(?:s|es)?(?!\w)", text))


def understand_search(query: str, location: str | None = None) -> dict[str, Any]:
    """Turn natural language into an auditable commercial search plan."""
    normalized = _fold(query)
    intent = next((key for key, phrases in _COMMERCIAL_INTENTS.items()
                   if any(phrase in normalized for phrase in phrases)), None)
    entity_text = normalized
    if intent:
        for phrase in _COMMERCIAL_INTENTS[intent]:
            entity_text = entity_text.replace(phrase, " ")
    scored: list[tuple[int, CommercialEntity]] = []
    for entity in ONTOLOGY:
        matches = [term for term in (*entity.terms, *entity.services) if _contains(entity_text, term)]
        if matches:
            scored.append((max(len(_fold(term)) for term in matches), entity))
    entity = max(scored, default=(0, None), key=lambda row: row[0])[1]
    matched_services = [service for service in (entity.services if entity else ()) if _contains(normalized, service)]
    matched_audiences = [audience for audience in (entity.audiences if entity else ()) if _contains(normalized, audience)]
    digital = {key: any(re.search(pattern, normalized) for pattern in patterns)
               for key, patterns in _DIGITAL_SIGNALS.items()}
    alternatives: list[str] = []
    if entity:
        # Prefer terms related to the user's wording, then diversify. A short
        # expansion avoids turning provider queries into keyword soup.
        alternatives = [entity.canonical, *matched_services, *entity.terms][:8]
    alternatives = list(dict.fromkeys(item.strip() for item in alternatives if item.strip()))
    return {
        "entity": entity.canonical if entity else None,
        "services": matched_services,
        "audiences": matched_audiences,
        "location": (location or "").strip() or None,
        "digital_presence": digital,
        "commercial_intent": intent,
        "alternatives": alternatives,
        "raw_query": query.strip(),
    }


def expand_provider_query(query: str, location: str | None = None) -> str:
    plan = understand_search(query, location)
    original = query.strip()
    terms = [original, *plan["alternatives"]]
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = _fold(term)
        if key and key not in seen:
            seen.add(key); unique.append(term)
    # Quoted alternatives work for web indexes and remain readable to Maps.
    expanded = " OR ".join(f'"{term}"' if " " in term else term for term in unique[:8])
    return " ".join(filter(None, [expanded, plan["location"]]))


def public_search_plan(query: str, location: str | None = None) -> dict[str, Any]:
    """Serializable plan for tests, logs, and future UI explanations."""
    plan = understand_search(query, location)
    return {**plan, "provider_query": expand_provider_query(query, location)}
