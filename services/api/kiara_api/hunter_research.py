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
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlsplit, urlunsplit


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
_NO_EMAIL = re.compile(
    r"\b(?:(?:que\s+)?nao\s+(?:tem|tenham|tenha|possui|possuem|possuam)|sem)\s+"
    r"(?:(?:um|uma|o|a)\s+)?(?:e-?mail|correio eletronico)\b"
)
_WEAK_WEBSITE = re.compile(
    r"\b(?:site|website|pagina)\s+(?:feio|ruim|fraco|antigo|desatualizado|lento|precario|amador)\b|"
    r"\b(?:site|website)\s+(?:que\s+)?(?:nao\s+)?(?:e\s+)?(?:bonito|moderno|responsivo|profissional)\b"
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
    email = "without_email" if _NO_EMAIL.search(combined) else "any"
    website_quality = "opportunity" if _WEAK_WEBSITE.search(combined) else "any"
    patterns = [_NO_SITE, _HAS_SITE, _WHATSAPP, _PHONE, _NO_EMAIL, _WEAK_WEBSITE]
    niche = _strip_spans(query, patterns)
    remainder = _strip_spans(objective, patterns)
    # Connectors left after supported criteria are not a new requirement.
    if re.fullmatch(r"(?:(?:e|ou|que|com)[\s,.;-]*)*", folded(remainder)):
        remainder = ""
    unsupported = bool(remainder or _CRITERION_HINT.search(folded(niche)))
    return {"website_filter": website, "contact_filter": contact,
            "email_filter": email, "website_quality_filter": website_quality,
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


def canonical_public_identity(value: Any) -> str | None:
    """Keep resource identity at every deduplication stage, dropping tracking only."""
    safe = safe_public_url(value)
    if not safe:
        return None
    parts = urlsplit(safe)
    host = (parts.hostname or "").lower().removeprefix("www.")
    if ":" in host:
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port and parts.port not in {80, 443} else ""
    query = urlencode(sorted((key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
                             if not key.lower().startswith("utm_")
                             and key.lower() not in {"fbclid", "gclid", "ref", "hl", "authuser", "entry", "g_ep"}))
    return urlunsplit(("https", host + port, parts.path.rstrip("/") or "/", query, ""))


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
    value = html.unescape(value).strip()
    is_link = value[:4].lower() == "tel:"
    value = unquote(value[4:] if is_link else value)
    if is_link:
        # RFC 3966 parameters are not part of the subscriber number. Never
        # concatenate an extension or phone-context into a different phone.
        value = value.split(";", 1)[0]
    value = value.strip()
    if not re.fullmatch(r"\+?[0-9(][0-9\s().-]*", value):
        return None
    digits = re.sub(r"[^0-9]", "", value)
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
    tel = next((phone_number(link) for link in links if link[:4].lower() == "tel:" and phone_number(link)), None)
    # Only context-labelled phone numbers, not unrelated dates/IDs in a page.
    match = re.search(r"(?:telefone|phone|celular|tel\.?|whatsapp)\s*[:\-]?\s*(\+?[\d (][\d ()\-]{8,22}\d)", text, re.IGNORECASE)
    tel = tel or (phone_number(match.group(1)) if match else None)
    if not tel and whatsapp:
        tel = "+" + urlsplit(whatsapp).path.strip("/")
    email_match = re.search(r"(?<![\w.+-])([\w.+-]{1,64}@[\w.-]+\.[a-zA-Z]{2,24})(?![\w.-])", html.unescape(text))
    email = email_match.group(1).lower() if email_match else None
    result = {"phone": tel, "whatsapp_url": whatsapp}
    if email:
        result["email"] = email
    return result


def merge_public_contacts(data: dict[str, Any], contacts: dict[str, Any]) -> None:
    """Fill missing contacts without erasing facts observed in another source."""
    for key, value in contacts.items():
        existing = data.get(key)
        if key == "phone":
            existing = phone_number(existing)
        elif key == "whatsapp_url":
            existing = whatsapp_link(existing)
        if value and not existing:
            data[key] = value


def extract_public_address(text: str, source_url: str) -> dict[str, Any]:
    """Extract a complete visible Brazilian street address, preserving its source.

    A street number plus an observed state or postcode is required. Search-query
    locations and indexed snippets must never be passed as inspected page text.
    """
    source = safe_public_url(source_url)
    if not source:
        return {}
    visible = re.sub(r"\s+", " ", html.unescape(text))
    street = re.compile(
        r"\b(?:Rua|R\.|Avenida|Av\.|Alameda|Travessa|Estrada|Rodovia|Praça)\s+"
        r"[\wÀ-ÿ .'-]{2,100}?,?\s+(?:n[º°o.]?\s*)?\d{1,6}\b",
        re.IGNORECASE,
    )
    state = r"(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)"
    ending = re.compile(
        rf"(?:\bCEP\s*[:\-]?\s*\d{{5}}-?\d{{3}}\b|\b\d{{5}}-\d{{3}}\b|"
        rf"[\-/–,]\s*{state}\b|\b[A-ZÀ-Ý][\wÀ-ÿ'-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'-]+){{0,4}}\s+{state}\b)"
    )
    for match in street.finditer(visible):
        tail = visible[match.end():match.start() + 300]
        # Do not borrow location evidence from a later contact/marketing block.
        tail = re.split(r"\b(?:telefone|whatsapp|e-?mail|copyright|todos os direitos)\b", tail, maxsplit=1, flags=re.IGNORECASE)[0]
        tail = re.split(r"[.!?](?:\s|$)", tail, maxsplit=1)[0]
        end = ending.search(tail)
        if end:
            address = visible[match.start():match.end()] + tail[:end.end()]
            return {"address": address, "address_evidence": "verified_public_page",
                    "address_source_url": source, "address_evidence_text": address}
    return {}


def website_opportunity(url: str, content: str, links: list[str]) -> tuple[int, list[str]]:
    """Score observable homepage signals; never claim subjective visual quality."""
    score, signals = 100, []
    if urlsplit(url).scheme != "https":
        score -= 25; signals.append("Site sem HTTPS")
    words = len(clean_summary(content, 5000).split())
    if words < 80:
        score -= 30; signals.append("Pouco conteúdo público na página analisada")
    contacts = extract_contacts(content, links)
    if not any(contacts.values()):
        score -= 25; signals.append("Nenhum telefone, WhatsApp ou e-mail identificado no site")
    internal = [link for link in links if safe_public_url(link) and urlsplit(link).hostname == urlsplit(url).hostname]
    if len(internal) < 2:
        score -= 20; signals.append("Estrutura de navegação pública limitada")
    return max(0, score), signals


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
    if item.get("source") == "web":
        # Preserve the source title: a readable label is not a verified name.
        raw_title = data.get("source_title") or item.get("title") or ""
        raw_title = raw_title if isinstance(raw_title, str) else ""
        data["source_title"] = raw_title[:500]
        data["name_status"] = "source_title"
        data["display_name"] = web_source_name(raw_title, str(item.get("url") or ""))
    if item.get("source") == "instagram":
        profile_url = safe_public_url(item.get("url"))
        parts = urlsplit(profile_url) if profile_url else None
        host = (parts.hostname or "").lower().removeprefix("www.") if parts else ""
        segments = parts.path.strip("/").split("/") if parts else []
        if host == "instagram.com" and len(segments) == 1 and re.fullmatch(r"[A-Za-z0-9_.]{1,30}", segments[0]):
            data["profile_handle"] = segments[0]
            data["content_kind"] = "profile"
        elif host == "instagram.com" and len(segments) == 2 and segments[0].lower() in {"p", "reel", "tv"}:
            data["content_kind"] = "publication"
    elif item.get("source") == "facebook":
        profile_url = safe_public_url(item.get("url"))
        parts = urlsplit(profile_url) if profile_url else None
        host = (parts.hostname or "").lower().removeprefix("www.") if parts else ""
        segments = parts.path.strip("/").split("/") if parts else []
        if host in {"facebook.com", "fb.com"}:
            first = segments[0].lower() if segments else ""
            if (
                first in {"posts", "photos", "videos", "watch", "events", "share", "sharer", "story.php", "permalink.php"}
                or (len(segments) >= 2 and segments[1].lower() in {"posts", "photos", "videos"})
            ):
                data["content_kind"] = "publication"
            elif first == "profile.php":
                uid = (parse_qs(parts.query).get("id") or [""])[0]
                if uid.isdigit():
                    data["profile_handle"] = uid
                    data["content_kind"] = "profile"
            elif len(segments) == 1 and re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", segments[0]):
                data["profile_handle"] = segments[0]
                data["content_kind"] = "profile"
            elif first in {"pages", "people"} and len(segments) >= 2:
                data["profile_handle"] = segments[1]
                data["content_kind"] = "profile"
    text = " ".join(str(value or "") for value in (data.pop("content", None), item.get("summary")))
    # User notes are not a verified source of public contact information.
    contacts = {"phone": None, "whatsapp_url": None, "email": None} if data.get("manual_import") else extract_contacts(text)
    data["phone"] = phone_number(data.get("phone")) or contacts["phone"]
    data["whatsapp_url"] = whatsapp_link(data.get("whatsapp_url")) or contacts["whatsapp_url"]
    data["email"] = (str(data.get("email") or "").strip().lower() or contacts.get("email"))
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


def web_source_name(title: str, url: str) -> str:
    """Shorten a delimited title only when the segment matches the source host."""
    fallback = clean_summary(title, 300) or "Página sem nome"
    safe = safe_public_url(url)
    if not safe:
        return fallback
    host = re.sub(r"[^a-z0-9]", "", folded(urlsplit(safe).hostname or ""))
    generic = {"clinica", "clinicas", "odontologia", "odontologica", "dentista", "dentistas",
               "medica", "medicas", "saude", "site", "oficial", "home", "inicio", "contato", "blog", "rede"}
    candidates = []
    parts = re.split(r"\s*[|•·]\s*|\s+[-–—]\s+", html.unescape(title))
    if len(parts) < 2:
        return fallback
    for part in parts:
        label = clean_summary(part, 300)
        tokens = {token for token in re.findall(r"[a-z0-9]+", folded(label))
                  if len(token) >= 4 and token not in generic}
        matches = sum(token in host for token in tokens)
        if matches and 2 <= len(label) <= 120:
            candidates.append((matches, -len(label), label))
    return max(candidates)[2] if candidates else fallback


_BRAZIL_STATES = {
    "ac": "acre", "al": "alagoas", "ap": "amapa", "am": "amazonas", "ba": "bahia",
    "ce": "ceara", "df": "distrito federal", "es": "espirito santo", "go": "goias",
    "ma": "maranhao", "mt": "mato grosso", "ms": "mato grosso do sul", "mg": "minas gerais",
    "pa": "para", "pb": "paraiba", "pr": "parana", "pe": "pernambuco", "pi": "piaui",
    "rj": "rio de janeiro", "rn": "rio grande do norte", "rs": "rio grande do sul",
    "ro": "rondonia", "rr": "roraima", "sc": "santa catarina", "sp": "sao paulo",
    "se": "sergipe", "to": "tocantins",
}


def address_matches_location(address: str, location: str | None) -> bool:
    """Require the requested city/region in observed locality, never infer from UF/CEP."""
    if not location or not location.strip():
        return True

    def words(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", folded(value)).strip()

    requested = words(location)
    requested_locality = folded(location)
    observed = address
    # A street called Curitiba does not prove that the business is in Curitiba.
    if re.match(r"\s*(?:rua|r\.|avenida|av\.|alameda|travessa|estrada|rodovia|praça)\s", address, re.IGNORECASE):
        numbered = re.search(r"\b\d{1,6}\b", address)
        if numbered:
            observed = address[numbered.end():]
    locality_address = observed
    observed = " " + words(observed) + " "
    region = None
    # Prefer the longest names, e.g. Mato Grosso do Sul before Mato Grosso.
    for abbreviation, name in sorted(_BRAZIL_STATES.items(), key=lambda pair: len(pair[1]), reverse=True):
        for suffix in (name, abbreviation):
            if requested == suffix and suffix in {"sao paulo", "rio de janeiro"}:
                continue  # Ambiguous capital/state names alone mean the requested city.
            if requested == suffix or requested.endswith(" " + suffix):
                region = (abbreviation, name)
                requested = requested[:-len(suffix)].strip()
                requested_locality = re.sub(re.escape(suffix) + r"$", "", requested_locality).strip(" ,;/–-")
                break
        if region:
            break
    if region and not any(" " + value + " " in observed for value in region):
        return False
    # Compare complete locality components: São Paulo de Olivença is not São Paulo.
    locality_parts = [words(part) for part in re.split(r"[,;/–-]", requested_locality)]
    observed_parts = {words(part) for part in re.split(r"[,;/–-]", locality_address)}
    for part in tuple(observed_parts):
        for abbreviation, name in _BRAZIL_STATES.items():
            for suffix in (abbreviation, name):
                if part.endswith(" " + suffix):
                    observed_parts.add(part[:-len(suffix)].strip())
    return all(part in observed_parts for part in locality_parts if part)


def lead_requirement_gaps(item: dict[str, Any], search: dict[str, Any]) -> list[str]:
    """Return missing evidence for the minimum fields required of a Hunter lead."""
    data = item.get("public_data") or {}
    title = str(item.get("title") or "").strip()
    has_name = bool(title and title.lower() not in {
        "contato público", "contato publico", "resultado sem nome", "empresa no google maps",
        "resultado público", "resultado publico", "perfil público", "perfil publico",
    })
    if item.get("source") in {"instagram", "facebook"} and data.get("profile_handle"):
        has_name = True
    label = data.get("display_name") or title
    if len(str(label)) > 140:
        has_name = False
    missing = [] if has_name else ["name"]
    if not phone_number(data.get("phone")) and not whatsapp_link(data.get("whatsapp_url")):
        missing.append("phone_or_whatsapp")

    address = clean_summary(data.get("address"), 300)
    verified_source_address = bool(address) and (
        item.get("source") == "google_maps" and data.get("detail_inspected") is True
        or item.get("source") == "web" and data.get("address_evidence") == "verified_public_page"
    )
    if verified_source_address:
        verified_source_address = address_matches_location(address, search.get("location"))
    verified_social_profile = (
        item.get("source") == "instagram"
        and data.get("bio_status") == "verified_public_profile"
        or item.get("source") == "facebook"
        and data.get("page_status") == "verified_public_page"
    )
    verified_social_location = (
        verified_social_profile
        and data.get("bio_location_evidence") is True
        and bool(data.get("profile_bio"))
        and bool(search.get("location"))
        and not data.get("manual_import")
    )
    if not verified_source_address and not verified_social_location:
        missing.append("verified_location")

    if not safe_public_url(data.get("source_url") or item.get("url")):
        missing.append("source_url")
    return missing


def result_niche_matches(item: dict[str, Any], search: dict[str, Any]) -> bool:
    """A provider ranking is not evidence that a business serves the niche (see niche_match)."""
    from .niche_match import matches_niche

    query = research_options(search)["provider_query"]
    data = item.get("public_data") or {}
    observed = " ".join(str(value or "") for value in (
        item.get("title"), item.get("summary"), data.get("profile_bio"), data.get("category"),
    ))
    return matches_niche(query, observed)


def is_editorial_or_post(item: dict[str, Any]) -> bool:
    """Obvious articles and posts are sources, not CRM contact identities."""
    url = safe_public_url(item.get("url"))
    if not url:
        return True
    path = urlsplit(url).path.lower()
    if item.get("source") == "instagram":
        if (urlsplit(url).hostname or "").lower().removeprefix("www.") != "instagram.com":
            return True
        segments = path.strip("/").split("/")
        if len(segments) == 1 and re.fullmatch(r"[a-z0-9_.]{1,30}", segments[0]) and segments[0] not in {"p", "reel", "reels", "explore", "stories", "accounts", "direct", "about"}:
            return False
        return not (len(segments) == 2 and segments[0] in {"p", "reel", "tv"}
                    and re.fullmatch(r"[a-z0-9_-]{5,80}", segments[1]))
    if item.get("source") == "facebook":
        if (urlsplit(url).hostname or "").lower().removeprefix("www.") not in {"facebook.com", "fb.com"}:
            return True
        segments = path.strip("/").split("/")
        if not segments or segments == [""]:
            return True
        first = segments[0].lower()
        if first in {"groups", "events", "watch", "share", "sharer", "help", "login", "marketplace", "about", "policies", "recover", "settings"}:
            return True
        if len(segments) == 1 and re.fullmatch(r"[a-z0-9_.-]{1,60}", segments[0]) and first not in {
            "p", "posts", "photos", "videos", "watch", "groups", "events", "share", "sharer", "story.php", "permalink.php", "login", "pages", "help", "marketplace", "about", "policies", "recover", "settings"
        }:
            return False
        if first in {"pages", "people"} and len(segments) >= 2:
            return False
        if first == "profile.php" and "id=" in urlsplit(url).query.lower():
            return False
        return not ((len(segments) == 2 and first in {"posts", "photos", "videos", "p"})
                    or (len(segments) >= 3 and segments[1].lower() in {"posts", "photos", "videos"}))
    if item.get("source") == "web":
        title = folded(str(item.get("title") or ""))
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        # An aggregator's contact page belongs to the directory, not to every
        # business listed there. Do not import its footer phone as a prospect.
        directory_hosts = {"doctoralia.com.br", "locaisdobrasil.com.br", "maisnobairro.com.br",
                           "dentmap.com.br", "gyms1.com", "telelistas.net", "guiamais.com.br",
                           "apontador.com.br", "solutudo.com.br"}
        return bool(
            is_profile_url(url)
            or any(host == domain or host.endswith("." + domain) for domain in directory_hosts)
            or host in {"drive.google.com", "docs.google.com"}
            or re.search(r"\b(?:dicionario|significado|sinonimos|enciclopedia)\b", title)
            or re.search(r"/(?:equipe|equipe-tecnica|team|profissionais)(?:/|$)", path)
            or re.search(r"/(?:blog|artigos?|noticias?|news|posts?|search|maps/search)(?:/|$)", path)
            or re.match(
                r"^(?:(?:\d+\s+)?(?:melhores|principais|top)\b|"
                r"(?:os|as)\s+(?:\d+\s+)?(?:melhores|principais|top)\b|"
                r"(?:pesquisar|search)\s+(?:locais|places|no google maps)\b|"
                r"como\s+(?:escolher|encontrar|contratar|abrir|criar|saber|funciona|atrair|conseguir)|"
                r"o que\s+(?:e|sao|faz))",
                title,
            )
        )
    return False


def filter_results(items: list[dict[str, Any]], search: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    options = research_options(search)
    accepted: list[dict[str, Any]] = []
    counts = {"checked": len(items), "accepted": 0, "excluded": 0, "unknown": 0,
              "incomplete": 0, "source_failures": 0, "confirmed": 0, "probable": 0, "to_review": 0}
    partial: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in items:
        item = normalize_result(raw)
        data = item["public_data"]
        # Leads that could not be fully confirmed are kept with a lower tier instead of discarded:
        # "probable" has a direct contact, "to_review" has only the business and its public source.
        tier = "confirmed"
        if item["source"] == "google_maps" and data.get("detail_inspected") is not True:
            if "/maps/place/" not in (data.get("source_url") or item.get("url") or ""):
                counts["excluded"] += 1
                continue
            tier = "to_review"
        if item["source"] in {"instagram", "facebook"} and not data.get("manual_import"):
            has_relevant_profile = (
                data.get("content_kind") == "profile"
                and data.get("bio_status") == "verified_public_profile"
                and data.get("bio_niche_evidence") is True
                and (
                    not search.get("location")
                    or data.get("bio_location_evidence") is True
                )
            )
            if not has_relevant_profile:
                if data.get("content_kind") == "publication" or not result_niche_matches(item, search):
                    counts["excluded"] += 1
                    continue
                tier = "to_review"
        # Identity query parameters (Facebook id, Maps cid/place_id, etc.)
        # distinguish real businesses. Drop tracking only; path-only keys used
        # to collapse unrelated profiles into a single result.
        normalized_source = canonical_public_identity(data["source_url"]) or ""
        identities = {f"url:{normalized_source}"} if normalized_source else set()
        if data.get("place_id"):
            identities.add(f"place:{str(data['place_id']).lower()}")
        if data.get("phone"):
            identities.add(f"phone:{re.sub(r'\D', '', str(data['phone']))}:{folded(item['title'])}")
        website_url = safe_public_url(data.get("website_url"))
        if website_url and data.get("address"):
            website_host = (urlsplit(website_url).hostname or "").lower().removeprefix("www.")
            identities.add(f"business:{website_host}:{folded(str(data['address']))}:{folded(item['title'])}")
        if not data["source_url"]:
            counts["excluded"] += 1
            counts["incomplete"] += 1
            continue
        if identities & seen or is_editorial_or_post(item):
            counts["excluded"] += 1
            continue
        gaps = lead_requirement_gaps(item, search)
        if "name" in gaps or "source_url" in gaps or _verified_elsewhere(item, search):
            counts["excluded"] += 1
            counts["incomplete"] += 1
            continue
        if gaps:
            tier = "probable" if "phone_or_whatsapp" not in gaps or data.get("email") else "to_review"
            # A web page with no contact at all is almost always a guide or listing ("Onde comer em…"),
            # not a business: only Maps places and social profiles may be shown without a contact.
            if tier == "to_review" and item["source"] == "web":
                counts["excluded"] += 1
                continue
            if tier == "probable" and "verified_location" in gaps and item["source"] == "google_maps" and data.get("detail_inspected") is not True:
                tier = "to_review"
        if not result_niche_matches(item, search):
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
        if options["email_filter"] == "without_email":
            rejected = rejected or bool(data["email"])
            unknown = unknown or (not data["email"] and data.get("enrichment") != "completed" and item["source"] != "google_maps")
        if options["website_quality_filter"] == "opportunity":
            rejected = rejected or data.get("website_quality_score", 100) > 55
            unknown = unknown or data.get("website_quality_score") is None
        # Filters the user chose explicitly stay strict: a lead that does not prove them is not shown.
        if rejected or unknown:
            counts["excluded"] += 1
            counts["unknown"] += int(unknown and not rejected)
            continue
        seen.update(identities)
        is_social_publication = (item["source"] in {"instagram", "facebook"} and data.get("content_kind") == "publication")
        is_social_missing_evidence = (
            item["source"] in {"instagram", "facebook"}
            and (
                data.get("bio_status") not in {"verified_public_profile", "verified_public_page"}
                or not data.get("bio_niche_evidence")
                or (search.get("location") and not data.get("bio_location_evidence"))
            )
        )
        data["criterion_status"] = ("not_verified" if options["unsupported_criterion"] or is_social_publication or is_social_missing_evidence else
                                    "verified" if website != "any" or contact != "any" or options["email_filter"] != "any" or options["website_quality_filter"] != "any" else "not_requested")
        reasons = []
        if website == "without_website": reasons.append("Site não informado no perfil inspecionado")
        if options["email_filter"] == "without_email": reasons.append("E-mail não encontrado nas fontes inspecionadas")
        if options["website_quality_filter"] == "opportunity": reasons.extend(data.get("website_quality_signals") or [])
        if contact == "phone": reasons.append("Telefone público confirmado")
        if contact == "whatsapp": reasons.append("WhatsApp público confirmado")
        data["match_reasons"] = list(dict.fromkeys(reasons))
        data["research_objective"] = options["objective"]
        data["verification_version"] = 1
        apply_lead_tier(item, tier)
        counts[tier] += 1
        counts["incomplete"] += int(tier != "confirmed")
        (accepted if tier == "confirmed" else partial).append(item)
    rank = {"probable": 0, "to_review": 1}
    partial.sort(key=lambda row: (rank[row["public_data"]["lead_tier"]], -row["public_data"]["lead_score"]))
    accepted.sort(key=lambda row: -row["public_data"]["lead_score"])
    accepted.extend(partial)
    counts["accepted"] = len(accepted)
    return accepted, counts


TIER_LABELS = {"confirmed": "Confirmado", "probable": "Provável", "to_review": "A conferir"}
TIER_PENALTY = {"confirmed": 0, "probable": 8, "to_review": 22}


def _verified_elsewhere(item: dict[str, Any], search: dict[str, Any]) -> bool:
    """A verified address in another city is a different market, not a weaker lead."""
    data = item["public_data"]
    address = clean_summary(data.get("address"), 300)
    verified = bool(address) and (
        item.get("source") == "google_maps" and data.get("detail_inspected") is True
        or item.get("source") == "web" and data.get("address_evidence") == "verified_public_page"
    )
    return bool(verified and search.get("location") and not address_matches_location(address, search.get("location")))


def apply_lead_tier(item: dict[str, Any], tier: str) -> None:
    """Confidence tier plus a hot/warm/cold temperature with its reasons, for the result card."""
    from .company_data import lead_fit

    data = item["public_data"]
    fit = lead_fit({key: data.get(key) for key in ("phone", "email", "whatsapp_url", "website_status",
                                                   "website_quality_score", "rating", "user_rating_count")})
    score = max(0, min(100, fit["score"] + 20 - TIER_PENALTY[tier]))
    temperature = "hot" if score >= 55 else "warm" if score >= 30 else "cold"
    reasons = [reason["text"] for reason in fit["reasons"] if reason["points"] > 0][:3]
    if tier == "probable":
        reasons.append("Endereço ou critério ainda não confirmado")
    elif tier == "to_review":
        reasons.append("Contato ainda não encontrado: confira a fonte")
    data.update({"lead_tier": tier, "lead_tier_label": TIER_LABELS[tier], "lead_score": score,
                 "temperature": temperature, "temperature_reasons": reasons})


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
    public_data = {**contacts, "address": detail.get("address"),
                   "address_evidence": "verified_maps_detail" if inspected and detail.get("address") else None,
                   "website_url": website,
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
    # Google reputation shown on the business panel ("4,7" and "(1.234)" / "1.234 avaliações").
    rating = re.search(r"\d+(?:[.,]\d)?", str(detail.get("rating") or ""))
    if inspected and rating and 0 < float(rating.group().replace(",", ".")) <= 5:
        public_data["rating"] = float(rating.group().replace(",", "."))
        reviews = re.search(r"(\d[\d.\s]*)\s*(?:avaliaç|avaliac|review)", str(detail.get("reviews") or ""), re.IGNORECASE)
        if reviews:
            public_data["user_rating_count"] = int(re.sub(r"\D", "", reviews.group(1)))
    return {"source": "google_maps", "title": detail.get("title") or item.get("title") or "Empresa no Google Maps",
            "url": item["url"], "summary": clean_summary(detail.get("category")) or "Perfil empresarial público no Google Maps.",
            "public_data": public_data}
