"""Who decides at a hunted business: the owner or person in charge, from public sources only.

Order of trust:
1. Receita Federal partners (CNPJ printed on the business's own site) - the registry says who owns it;
2. a name with a role on the business's own site ("Proprietária: Ana Souza", "Dra. Ana Souza - CRO-RS 1234");
3. a professional name in the Google Maps title ("Dra. Ana Souza | Odontologia").
Nothing is guessed: no name is built from an e-mail, a handle or a company name.
"""
from __future__ import annotations

import re
from typing import Any

_UP = "A-ZÁÉÍÓÚÂÊÔÃÕÇÀ"
_LOW = "a-záéíóúâêôãõçàü"
_WORD = rf"[{_UP}][{_LOW}]+"
NAME = rf"{_WORD}(?:\s+(?:(?:da|de|do|das|dos|e)\s+)?{_WORD}){{1,4}}"

_ROLES = (
    r"propriet[aá]ri[oa]|fundador[a]?|s[oó]ci[oa][- ]?(?:fundador[a]?|propriet[aá]ri[oa]|administrador[a]?)?"
    r"|diretor[a]?(?:\s+(?:cl[ií]nic[oa]|t[eé]cnic[oa]|geral|comercial))?|respons[aá]vel\s+t[eé]cnic[oa]"
    r"|ceo|gerente(?:\s+geral)?|coordenador[a]?|administrador[a]?"
)
_ROLE_FIRST = re.compile(rf"\b({_ROLES})\s*[:\-–|]?\s*(?:(?:Dra?|Doutora?)\.?\s+)?({NAME})", re.IGNORECASE)
_DOCTOR = re.compile(rf"\b(Dra?\.|Dra\b|Doutora?)\s+({NAME})")
_REGISTRY = re.compile(rf"({NAME})\s*[,\-–|·]?\s*\(?\s*(CRO|CRM|CRP|CREFITO|CRN|CRF|CRMV|OAB|CRECI|CRC|COREN|CRBM)\b")

_NOT_A_NAME = {
    "clinica", "clínica", "odontologia", "consultorio", "consultório", "centro", "rua", "avenida", "contato", "agende",
    "agendamento", "whatsapp", "todos", "direitos", "reservados", "equipe", "nossa", "nosso", "sobre", "home", "politica",
    "política", "termos", "instituto", "studio", "estudio", "estúdio", "academia", "pizzaria", "restaurante", "loja",
    "imobiliaria", "imobiliária", "escritorio", "escritório", "advocacia", "grupo", "empresa", "saude", "saúde", "atendimento",
    "horario", "horário", "segunda", "sexta", "sabado", "sábado", "domingo", "endereco", "endereço", "telefone", "email",
    "unidade", "especialista", "especialidades", "tratamentos", "servicos", "serviços", "dentista", "medico", "médico",
    "psicologa", "psicóloga", "psicologo", "psicólogo", "advogado", "advogada", "corretor", "corretora", "fale",
}
_CONNECTORS = {"da", "de", "do", "das", "dos", "e"}


def _clean_name(value: str) -> str | None:
    words = value.split()
    real = [word for word in words if word.lower() not in _CONNECTORS]
    if not 2 <= len(real) <= 5 or any(word.lower().strip(".") in _NOT_A_NAME for word in real):
        return None
    while words and words[-1].lower() in _CONNECTORS:
        words.pop()
    return " ".join(words)[:80]


def title_case_name(value: str) -> str:
    """'MARIA DA SILVA' -> 'Maria da Silva'."""
    return " ".join(word.lower() if word.lower() in _CONNECTORS else word.capitalize() for word in value.split())[:80]


def _role_label(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw.strip().lower())
    for prefix, label in (("propriet", "Proprietário(a)"), ("fundador", "Fundador(a)"), ("sóci", "Sócio(a)"), ("soci", "Sócio(a)"),
                          ("diretor", "Diretor(a)"), ("respons", "Responsável técnico(a)"), ("ceo", "CEO"),
                          ("gerente", "Gerente"), ("coordenador", "Coordenador(a)"), ("administrador", "Administrador(a)")):
        if text.startswith(prefix):
            return label
    return raw.strip()[:40]


def people_from_text(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Names with a role or professional registry found on the business's own pages."""
    found: list[dict[str, str]] = []
    sample = (text or "")[:100000]

    def add(name: str, role: str) -> None:
        clean = _clean_name(name)
        if clean and all(clean.lower() != item["name"].lower() for item in found):
            found.append({"name": clean, "role": role, "source": "site"})

    for match in _ROLE_FIRST.finditer(sample):
        add(match.group(2), _role_label(match.group(1)))
    for match in _REGISTRY.finditer(sample):
        add(re.sub(r"^(?:Dra?\.?|Doutora?)\s+", "", match.group(1)), f"Profissional ({match.group(2).upper()})")
    for match in _DOCTOR.finditer(sample):
        add(match.group(2), "Dra." if match.group(1).lower().startswith(("dra", "doutora")) else "Dr.")
    return found[:limit]


def person_from_title(title: str) -> dict[str, str] | None:
    """'Dra. Ana Souza | Odontologia' -> Ana Souza (the listing is the professional's own)."""
    match = _DOCTOR.search(title or "")
    name = _clean_name(match.group(2)) if match else None
    if not name:
        return None
    return {"name": name, "role": "Dra." if match.group(1).lower().startswith(("dra", "doutora")) else "Dr.", "source": "maps"}


_PARTNER_PRIORITY = ("administrador", "titular", "presidente", "diretor", "sócio", "socio")


def _first(name: str) -> str:
    return name.split()[0].lower() if name else ""


def decision_maker(company: dict[str, Any] | None, site_people: list[dict[str, str]] | None,
                   title: str | None) -> dict[str, str] | None:
    """The best person to address, with where it came from."""
    company = company if isinstance(company, dict) else {}
    site_people = site_people or []
    partners = [item for item in company.get("partners") or [] if isinstance(item, dict) and item.get("name")]
    if partners:
        def rank(item: dict[str, Any]) -> int:
            role = str(item.get("role") or "").lower()
            return next((index for index, word in enumerate(_PARTNER_PRIORITY) if word in role), len(_PARTNER_PRIORITY))
        best = sorted(partners, key=rank)[0]
        name = title_case_name(str(best["name"]))
        # The site often writes the same person in a friendlier way ("Dra. Ana Souza").
        same = next((person for person in site_people if _first(person["name"]) == _first(name)), None)
        return {"name": same["name"] if same else name, "role": str(best.get("role") or "Sócio(a)")[:60], "source": "receita"}
    if company.get("mei") and company.get("legal_name"):
        owner = _clean_name(title_case_name(re.sub(r"^[\d.\s/-]+", "", str(company["legal_name"]))))
        if owner:
            return {"name": owner, "role": "Titular (MEI)", "source": "receita"}
    priority = ("Proprietário(a)", "Fundador(a)", "Sócio(a)", "Diretor(a)", "Responsável técnico(a)", "CEO", "Administrador(a)")
    for wanted in priority:
        person = next((item for item in site_people if item["role"] == wanted), None)
        if person:
            return person
    if site_people:
        return site_people[0]
    return person_from_title(title or "")
