"""Evidence-based Hunter constraints and public contact extraction.

Missing data is not evidence of a missing website. Only an inspected Maps
business detail can satisfy ``without_website``; the claim remains scoped to
that listing. A phone is never upgraded to WhatsApp without a public link.
"""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


def folded(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.lower())
                   if unicodedata.category(c) != "Mn")


_NO_SITE = re.compile(
    r"\b(?:(?:que\s+)?nao\s+(?:tem|tenham|tenha|possui|possuem|possuam)|sem)"
    r"\s+(?:(?:um|uma|o|a)\s+)?(?:site(?:\s+proprio)?|website|pagina\s+web)\b"
)
_HAS_SITE = re.compile(
    r"\b(?:(?:que\s+)?(?:tem|tenham|tenha|possui|possuem|possuam)|com)"
    r"\s+(?:(?:um|uma|o|a)\s+)?(?:site(?:\s+proprio)?|website|pagina\s+web)\b"
)
_WHATSAPP = re.compile(
    r"\b(?:(?:com|(?:que\s+)?(?:tem|tenham)|(?:somente|apenas)(?:\s+o)?)\s+)"
    r"(?:(?:numero|contato)(?:\s+de)?\s+)?whats(?:app)?\b"
)
_PHONE = re.compile(
    r"\b(?:com|(?:que\s+)?(?:tem|tenham)|somente|apenas)\s+"
    r"(?:(?:numero|contato)\s+de\s+)?(?:telefone|celular)\b"
)
_CRITERION_HINT = re.compile(r"\b(?:sem|com|que|apenas|somente|aceita|aceitem|atendem|atendam)\b")


def _strip_spans(value: str, patterns: list[re.Pattern[str]]) -> str:
    """Match accent-folded text but retain the user's original spelling."""
    positions: list[int] = []
    normalized = ""
    for index, char in enumerate(value):
        fragment = folded(char)
        normalized += fragment
        positions.extend([index] * len(fragment))
    remove: set[int] = set()
    for pattern in patterns:
        for match in pattern.finditer(normalized):
            remove.update(positions[match.start():match.end()])
    text = "".join(" " if index in remove else char for index, char in enumerate(value))
    return re.sub(r"\s+", " ", text).strip(" ,.;-")


def research_options(search: dict[str, Any]) -> dict[str, Any]:
    objective = (search.get("objective") or "").strip() if search.get("research_mode") == "focused" else ""
    query = search.get("query") or ""
    combined = folded(f"{query} {objective}")
    website = search.get("website_filter", "any")
    contact = search.get("contact_filter", "any")
    if _NO_SITE.search(combined):
        website = "without_website"
    elif website == "any" and _HAS_SITE.search(combined):
        website = "with_website"
    if _WHATSAPP.search(combined):
        contact = "whatsapp"
    elif contact == "any" and _PHONE.search(combined):
        contact = "phone"
    patterns = [_NO_SITE, _HAS_SITE, _WHATSAPP, _PHONE]
    niche = _strip_spans(query, patterns)
    remainder = _strip_spans(objective, patterns)
    # Connectors left after supported criteria are not a new requirement.
    if re.fullmatch(r"(?:(?:e|ou|que|com)[\s,.;-]*)*", folded(remainder)):
        remainder = ""
    unsupported = bool(remainder or _CRITERION_HINT.search(folded(niche)))
    return {"website_filter": website, "contact_filter": contact,
            "provider_query": niche or query, "remaining_objective": remainder,
            "unsupported_criterion": unsupported, "objective": objective}


def safe_public_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = html.unescape(value.strip()).rstrip(".,;")
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        _ = parts.port
    except ValueError:
        return None
    return value[:3000]


def clean_summary(value: Any, limit: int = 500) -> str:
    """Produce a compact plain-language excerpt, never raw crawl Markdown."""
    if not isinstance(value, str):
        return ""
    text = html.unescape(value)
    text = re.sub(r"!\[[^\]]*\]\([^\n]*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\s)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://[^\s<>)\]]+", " ", text)
    text = re.sub(r"(?im)^\s*(?:ir para o conte[uú]do|skip to content|menu|in[ií]cio)\s*$", " ", text)
    text = re.sub(r"[\[\]#*_`|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -()")
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def phone_number(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.removeprefix("tel:").strip()
    digits = re.sub(r"\D", "", value)
    if not 10 <= len(digits) <= 15 or len(set(digits)) < 3:
        return None
    # Preserve the observed national number; never infer a country code.
    return ("+" if value.startswith("+") else "") + digits


def whatsapp_link(value: Any) -> str | None:
    safe = safe_public_url(value)
    if not safe:
        return None
    parts = urlsplit(safe)
    hostname = (parts.hostname or "").lower().removeprefix("www.")
    if hostname == "wa.me":
        number = parts.path.strip("/")
    elif hostname in {"api.whatsapp.com", "web.whatsapp.com"} and parts.path.rstrip("/") == "/send":
        number = (parse_qs(parts.query).get("phone") or [""])[0]
    else:
        return None
    # wa.me needs an international-format number. Do not invent +55.
    digits = re.sub(r"[+ ()-]", "", number)
    return f"https://wa.me/{digits}" if re.fullmatch(r"[1-9]\d{9,14}", digits) else None


def extract_contacts(text: str, links: list[str] | None = None) -> dict[str, Any]:
    links = [link for link in links or [] if isinstance(link, str)]
    candidates = links + re.findall(r"https?://[^\s<>\]\)\"']+", html.unescape(text))
    whatsapp = next((match for link in candidates if (match := whatsapp_link(link))), None)
    tel = next((phone_number(link) for link in links if link.startswith("tel:") and phone_number(link)), None)
    # Only context-labelled phone numbers, not unrelated dates/IDs in a page.
    match = re.search(r"(?:telefone|phone|celular|tel\.?|whatsapp)\s*[:\-]?\s*(\+?[\d (][\d ()\-]{8,22}\d)", text, re.IGNORECASE)
    tel = tel or (phone_number(match.group(1)) if match else None)
    if not tel and whatsapp:
        tel = "+" + urlsplit(whatsapp).path.strip("/")
    return {"phone": tel, "whatsapp_url": whatsapp}


_PROFILE_DOMAINS = {
    "instagram.com", "facebook.com", "linkedin.com", "tiktok.com", "youtube.com",
    "google.com", "google.com.br", "maps.app.goo.gl", "wa.me", "whatsapp.com",
    "doctoralia.com.br", "vittude.com", "zenklub.com.br", "psicologiaviva.com.br",
    "yelp.com", "tripadvisor.com", "tripadvisor.com.br", "guiafacil.com", "apontador.com.br",
    "telelistas.net", "solutudo.com.br", "linktr.ee",
}


def is_profile_url(value: str) -> bool:
    host = (urlsplit(value).hostname or "").lower()
    return any(host == item or host.endswith("." + item) for item in _PROFILE_DOMAINS)


def normalize_result(item: dict[str, Any]) -> dict[str, Any]:
    data = dict(item.get("public_data") or {})
    text = " ".join(str(value or "") for value in (data.pop("content", None), item.get("summary")))
    contacts = extract_contacts(text)
    data["phone"] = phone_number(data.get("phone")) or contacts["phone"]
    data["whatsapp_url"] = whatsapp_link(data.get("whatsapp_url")) or contacts["whatsapp_url"]
    data["source_url"] = safe_public_url(item.get("url"))
    data["website_url"] = safe_public_url(data.get("website_url"))
    if data["website_url"]:
        data["website_status"] = "present"
    elif (item.get("source") == "google_maps" and data.get("detail_inspected") is True
          and data.get("website_status") == "not_listed"):
        data["website_status"] = "not_listed"
    elif item.get("source") == "web" and data["source_url"] and not is_profile_url(data["source_url"]):
        data["website_status"] = "present"
        data["website_url"] = data["source_url"]
        data["website_evidence"] = "Página web encontrada como fonte; vínculo comercial não verificado."
    else:
        data["website_status"] = "unknown"
    data["address"] = clean_summary(data.get("address"), 300) or None
    return {**item, "title": clean_summary(item.get("title"), 300) or "Contato público",
            "summary": clean_summary(text), "public_data": data}


def is_editorial_or_post(item: dict[str, Any]) -> bool:
    """Obvious articles and posts are sources, not CRM contact identities."""
    url = safe_public_url(item.get("url"))
    if not url:
        return True
    path = urlsplit(url).path.lower()
    if item.get("source") == "instagram":
        segments = path.strip("/").split("/")
        return len(segments) != 1 or segments[0] in {"", "p", "reel", "reels", "explore", "stories", "accounts", "direct"}
    if item.get("source") == "linkedin":
        return not re.match(r"^/(?:in|company|school)/[^/]+", path)
    if item.get("source") == "web":
        title = folded(str(item.get("title") or ""))
        return bool(re.search(r"/(?:blog|artigos?|noticias?|news|posts?)(?:/|$)", path)
                    or re.match(r"^(?:\d+\s+(?:melhores|dicas|motivos|passos)|como\s+(?:escolher|encontrar|contratar|abrir|criar|saber|funciona|atrair|conseguir)|o que\s+(?:e|sao|faz))\b", title))
    return False


def filter_results(items: list[dict[str, Any]], search: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    options = research_options(search)
    accepted: list[dict[str, Any]] = []
    counts = {"checked": len(items), "accepted": 0, "excluded": 0, "unknown": 0, "source_failures": 0}
    seen: set[str] = set()
    for raw in items:
        item = normalize_result(raw)
        data = item["public_data"]
        if not data["source_url"] or data["source_url"] in seen or is_editorial_or_post(item):
            counts["excluded"] += 1
            continue
        website = options["website_filter"]
        contact = options["contact_filter"]
        unknown = False
        rejected = False
        if website == "without_website":
            rejected = data["website_status"] == "present"
            unknown = not rejected and not (item["source"] == "google_maps"
                and data.get("detail_inspected") is True and data["website_status"] == "not_listed")
        elif website == "with_website":
            rejected = data["website_status"] == "not_listed"
            unknown = data["website_status"] == "unknown"
        if contact == "whatsapp" and not data["whatsapp_url"]:
            unknown = True
        if contact == "phone" and not data["phone"]:
            unknown = True
        if rejected or unknown:
            counts["excluded"] += 1
            counts["unknown"] += int(unknown and not rejected)
            continue
        seen.add(data["source_url"])
        data["criterion_status"] = ("not_verified" if options["unsupported_criterion"] else
                                    "verified" if website != "any" or contact != "any" else "not_requested")
        data["research_objective"] = options["objective"]
        data["verification_version"] = 1
        accepted.append(item)
    counts["accepted"] = len(accepted)
    return accepted, counts


def maps_detail_result(item: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    """Pure transformation of a fully rendered business detail snapshot."""
    expected_title = re.sub(r"\W+", " ", folded(item.get("title") or "")).strip()
    observed_title = re.sub(r"\W+", " ", folded(detail.get("title") or "")).strip()
    if expected_title and observed_title and expected_title != observed_title:
        detail = {}  # Never attach another listing's contacts to this URL.
        observed_title = ""
    inspected = bool(observed_title and detail.get("loaded") and (not expected_title or observed_title == expected_title))
    listed_link = safe_public_url(detail.get("website"))
    whatsapp_website = whatsapp_link(listed_link)
    profile_website = bool(listed_link and is_profile_url(listed_link) and not whatsapp_website)
    website = listed_link if not whatsapp_website and not profile_website else None
    # A labelled website button whose URL could not be read means unknown.
    state = "present" if website else "not_listed" if inspected and (whatsapp_website or not detail.get("website_button")) and not profile_website else "unknown"
    contacts = extract_contacts(str(detail.get("phone") or ""), [*(detail.get("links") or []), *([listed_link] if listed_link else [])])
    contacts["phone"] = phone_number(detail.get("phone")) or contacts["phone"]
    public_data = {**contacts, "address": detail.get("address"), "website_url": website,
                   "website_status": state, "detail_inspected": inspected,
                   "website_evidence": ("O campo Site do Google Maps aponta para WhatsApp; nenhum site comercial foi listado nesse campo."
                    if whatsapp_website and inspected else "O campo Site aponta para um perfil ou diretório; site comercial não verificado."
                    if profile_website and inspected else "Link de site informado no perfil do Google Maps inspecionado."
                    if website and inspected else "Página de detalhes do Google Maps inspecionada; ausência limitada ao campo Site desta fonte."
                    if inspected else "Detalhes do Google Maps não puderam ser verificados."),
                   "source_url": item["url"]}
    place = re.search(r"!1s([^!/?]+)", unquote(item["url"]))
    if place:
        public_data["place_id"] = place.group(1)
    return {"source": "google_maps", "title": detail.get("title") or item.get("title") or "Empresa no Google Maps",
            "url": item["url"], "summary": clean_summary(detail.get("category")) or "Perfil empresarial público no Google Maps.",
            "public_data": public_data}
