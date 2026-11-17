"""Open sites and apps for the person, like the old desktop Kiara ("abra o youtube").

Kiara answers with [[ABRIR: key]] or [[ABRIR: key | what to search]]; the chat turns it into buttons (and opens
the first site by itself when the browser allows). Only keys from ACTIONS exist: Kiara never builds a URL, so a
prompt cannot send anyone to an arbitrary address. Programs that a web page cannot start (Prompt de Comando,
Chrome as a program) are explained instead of faked.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import quote_plus

MARKER = re.compile(r"\[\[\s*ABRIR\s*:\s*([^\]|]{1,40})(?:\|\s*([^\]]{0,200}))?\]\]", re.IGNORECASE)
MAX_ACTIONS = 3

# key -> (button label, address, search address with {q} or "")
ACTIONS: dict[str, tuple[str, str, str]] = {
    "youtube": ("YouTube", "https://www.youtube.com", "https://www.youtube.com/results?search_query={q}"),
    "google": ("Google", "https://www.google.com", "https://www.google.com/search?q={q}"),
    "nova aba": ("Nova aba", "https://www.google.com", "https://www.google.com/search?q={q}"),
    "maps": ("Google Maps", "https://www.google.com/maps", "https://www.google.com/maps/search/{q}"),
    "gmail": ("Gmail", "https://mail.google.com", ""),
    "drive": ("Google Drive", "https://drive.google.com", ""),
    "agenda": ("Google Agenda", "https://calendar.google.com", ""),
    "outlook": ("Outlook", "https://outlook.office.com/mail/", ""),
    "github": ("GitHub", "https://github.com", "https://github.com/search?q={q}"),
    "linkedin": ("LinkedIn", "https://www.linkedin.com", "https://www.linkedin.com/search/results/all/?keywords={q}"),
    "instagram": ("Instagram", "https://www.instagram.com", ""),
    "facebook": ("Facebook", "https://www.facebook.com", ""),
    "whatsapp": ("WhatsApp Web", "https://web.whatsapp.com", ""),
    "wikipedia": ("Wikipédia", "https://pt.wikipedia.org", "https://pt.wikipedia.org/w/index.php?search={q}"),
    "vscode": ("VS Code", "vscode://", ""),
    "obsidian": ("Obsidian", "obsidian://open", "obsidian://search?query={q}"),
    "edge": ("Microsoft Edge", "microsoft-edge:https://www.bing.com", "microsoft-edge:https://www.bing.com/search?q={q}"),
}
ALIASES = {"chrome": "nova aba", "navegador": "nova aba", "aba": "nova aba", "mapa": "maps", "google maps": "maps",
           "email": "gmail", "e-mail": "gmail", "calendario": "agenda", "visual studio code": "vscode", "vs code": "vscode",
           "code": "vscode", "zap": "whatsapp", "wpp": "whatsapp", "insta": "instagram", "face": "facebook",
           "wiki": "wikipedia", "microsoft edge": "edge", "bing": "edge"}

ACTION_STYLE = (
    "\nVocê pode abrir sites e alguns programas para a pessoa. Quando ela pedir para abrir algo (ex.: \"abra o youtube\", "
    "\"abre o github\", \"pesquisa receita de bolo no youtube\"), responda em uma frase curta e coloque no fim "
    "[[ABRIR: chave]] ou, para já abrir com uma busca, [[ABRIR: chave | o que buscar]]. Chaves: "
    + ", ".join(sorted(ACTIONS)) + ". Para \"abra o chrome\" ou \"o navegador\" use a chave nova aba. "
    "Só use quando ela pedir para abrir, no máximo 3 por resposta. Diga \"Abrindo o YouTube\" (o botão aparece embaixo), "
    "nunca que já está aberto. Programas fora da lista (Prompt de Comando, Word, Excel, configurações do Windows) você "
    "não consegue abrir por aqui: diga isso com simplicidade e explique o caminho mais rápido para a pessoa abrir.\n")


def _key(raw: str) -> str:
    plain = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().lower().strip()
    plain = re.sub(r"^(o|a|os|as)\s+", "", plain)
    return plain if plain in ACTIONS else ALIASES.get(plain, "")


def take_actions(text: str) -> tuple[str, list[dict[str, str]]]:
    """Answer without the markers, and the buttons (label + address) for the known keys."""
    actions: list[dict[str, str]] = []
    for match in MARKER.finditer(text or ""):
        key = _key(match.group(1))
        if not key or len(actions) == MAX_ACTIONS:
            continue
        label, url, search = ACTIONS[key]
        query = re.sub(r"\s+", " ", (match.group(2) or "")).strip()
        if query and search:
            url, label = search.format(q=quote_plus(query[:150])), f"{label}: {query[:40]}"
        if all(item["url"] != url for item in actions):
            actions.append({"label": label, "url": url})
    return MARKER.sub("", text or "").strip(), actions
