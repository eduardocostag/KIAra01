"""Public company data (Receita Federal via BrasilAPI) and the explainable lead fit score.

The CNPJ comes from the user or from the lead's own website footer; nothing is guessed by name.
Only public registry fields are kept. Partner names are public in the CNPJ registry but are
reduced to name + role, without any personal identifier.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CNPJ_TEXT = re.compile(r"(?<!\d)(\d{2})\.?(\d{3})\.?(\d{3})/?(\d{4})-?(\d{2})(?!\d)")
PROVIDERS = (
    ("brasilapi", "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"),
    ("minhareceita", "https://minhareceita.org/{cnpj}"),
)


class CompanyLookupError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def clean_cnpj(value: str) -> str | None:
    """Digits of a valid CNPJ (check digits verified), or None."""
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 14 or len(set(digits)) == 1:
        return None

    def check(base: str) -> str:
        weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(base):]
        total = sum(int(d) * w for d, w in zip(base, weights, strict=True))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    first = check(digits[:12])
    second = check(digits[:12] + first)
    return digits if digits[12:] == first + second else None


def format_cnpj(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def find_cnpjs(text: str) -> list[str]:
    """Valid CNPJs mentioned in a page, in order, without duplicates."""
    found: list[str] = []
    for match in CNPJ_TEXT.finditer(text or ""):
        digits = clean_cnpj("".join(match.groups()))
        if digits and digits not in found:
            found.append(digits)
    return found


def _text(value: Any, limit: int = 200) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def normalize_company(raw: dict[str, Any], cnpj: str, provider: str) -> dict[str, Any]:
    situation = _text(raw.get("descricao_situacao_cadastral"), 40)
    partners = []
    for item in raw.get("qsa") or []:
        if isinstance(item, dict) and _text(item.get("nome_socio")):
            partners.append({"name": _text(item.get("nome_socio"), 120), "role": _text(item.get("qualificacao_socio"), 80)})
    capital = raw.get("capital_social")
    secondary = [
        _text(item.get("descricao"), 160) for item in raw.get("cnaes_secundarios") or []
        if isinstance(item, dict) and _text(item.get("descricao"))
    ]
    return {
        "cnpj": cnpj,
        "cnpj_formatted": format_cnpj(cnpj),
        "legal_name": _text(raw.get("razao_social")),
        "trade_name": _text(raw.get("nome_fantasia")),
        "status": situation,
        "active": (situation or "").upper() == "ATIVA",
        "opened_at": _text(raw.get("data_inicio_atividade"), 10),
        "size": _text(raw.get("porte") or raw.get("descricao_porte"), 60),
        "legal_nature": _text(raw.get("natureza_juridica"), 120),
        "main_activity": _text(raw.get("cnae_fiscal_descricao"), 200),
        "secondary_activities": secondary[:8],
        "capital": float(capital) if isinstance(capital, (int, float)) else None,
        "city": _text(raw.get("municipio"), 80),
        "state": _text(raw.get("uf"), 2),
        "simples": raw.get("opcao_pelo_simples") if isinstance(raw.get("opcao_pelo_simples"), bool) else None,
        "mei": raw.get("opcao_pelo_mei") if isinstance(raw.get("opcao_pelo_mei"), bool) else None,
        "partners": partners[:10],
        "source": provider,
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def fetch_company(cnpj: str, *, opener=urlopen) -> dict[str, Any]:
    """Look the CNPJ up on public registries (BrasilAPI, then Minha Receita)."""
    digits = clean_cnpj(cnpj)
    if not digits:
        raise CompanyLookupError("cnpj_invalid", "CNPJ inválido. Confira os 14 dígitos.")
    not_found = False
    for provider, template in PROVIDERS:
        request = Request(template.format(cnpj=digits), headers={"Accept": "application/json", "User-Agent": "KiaraLeadIntelligence/1.0"})
        try:
            with opener(request, timeout=12) as response:
                payload = json.loads(response.read(500_001)[:500_000])
        except HTTPError as error:
            not_found = not_found or error.code in {400, 404}
            continue
        except (URLError, TimeoutError, OSError, ValueError):
            continue
        if isinstance(payload, dict) and payload.get("razao_social"):
            return normalize_company(payload, digits, provider)
    if not_found:
        raise CompanyLookupError("cnpj_not_found", "Esse CNPJ não foi encontrado na Receita Federal.")
    raise CompanyLookupError("cnpj_provider_unavailable", "A consulta pública de CNPJ não respondeu agora. Tente de novo em instantes.")


def _years_since(value: str | None, today: date | None = None) -> float | None:
    try:
        opened = date.fromisoformat(value or "")
    except ValueError:
        return None
    return ((today or date.today()) - opened).days / 365.25


def lead_fit(lead: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """0-100 profile score with the reasons behind it, from data the lead already has.

    It measures how reachable and how solid the business looks, and whether it has a clear
    digital gap Kiara's users can sell into. It is a prioritization aid, not a prediction.
    """
    points = 0
    reasons: list[dict[str, Any]] = []

    def add(value: int, text: str) -> None:
        nonlocal points
        points += value
        reasons.append({"points": value, "text": text})

    # Reachability.
    if lead.get("whatsapp_url"):
        add(18, "WhatsApp público encontrado")
    elif lead.get("phone"):
        add(12, "Telefone público")
    if lead.get("email"):
        add(6, "E-mail público")
    # Reputation on Google.
    rating, reviews = lead.get("rating"), lead.get("user_rating_count")
    if isinstance(reviews, (int, float)) and reviews > 0:
        if reviews >= 100:
            add(14, f"{int(reviews)} avaliações no Google: negócio movimentado")
        elif reviews >= 20:
            add(9, f"{int(reviews)} avaliações no Google")
        else:
            add(4, f"Poucas avaliações no Google ({int(reviews)})")
    if isinstance(rating, (int, float)) and rating > 0:
        if rating >= 4.5:
            add(8, f"Nota {rating:.1f} no Google: clientes satisfeitos")
        elif rating < 3.5:
            add(-6, f"Nota {rating:.1f} no Google: reputação a melhorar")
    # Digital gap: an opportunity, not a flaw.
    website = lead.get("website_status")
    quality = lead.get("website_quality_score")
    if website in {"not_listed", "absent", "missing", "none"}:
        add(16, "Sem site próprio: oportunidade clara")
    elif isinstance(quality, (int, float)) and quality < 50:
        add(10, "Site com qualidade baixa: espaço para melhoria")
    elif website == "present":
        add(4, "Já tem site")
    # Public registry.
    company = lead.get("company") if isinstance(lead.get("company"), dict) else None
    if company:
        if company.get("active") is False:
            add(-40, f"CNPJ com situação {str(company.get('status') or 'irregular').lower()}")
        else:
            add(8, "CNPJ ativo na Receita Federal")
        years = _years_since(company.get("opened_at"), today)
        if years is not None:
            if years >= 5:
                add(10, f"Empresa com {int(years)} anos: negócio estabelecido")
            elif years >= 2:
                add(6, f"Empresa com {int(years)} anos")
            else:
                add(4, "Empresa nova: costuma investir para crescer")
        size = (company.get("size") or "").upper()
        if "DEMAIS" in size or "PEQUENO" in size or "EPP" in size:
            add(6, "Porte acima de microempresa")
        elif company.get("mei"):
            add(-4, "MEI: orçamento costuma ser menor")
    score = max(0, min(100, points))
    grade = "A" if score >= 70 else "B" if score >= 50 else "C" if score >= 30 else "D"
    labels = {"A": "Prioridade alta", "B": "Bom potencial", "C": "Potencial médio", "D": "Baixa prioridade"}
    return {"score": score, "grade": grade, "label": labels[grade],
            "reasons": sorted(reasons, key=lambda item: -abs(item["points"]))[:8],
            "has_company_data": bool(company)}
