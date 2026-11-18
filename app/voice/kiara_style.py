"""Kiara's speaking style, shared by the chat voice and the presentation videos.

One place for the voice, pace and pronunciation fixes, so Kiara sounds the same everywhere.
"""
from __future__ import annotations

import re

# Native pt-BR voice. ThalitaMultilingual mixes languages and sounds Spanish on names and greetings.
VOICE = "pt-BR-FranciscaNeural"
# Slightly brisker than default: natural and confident without sounding rushed.
RATE = "+2%"
# Acronyms the Portuguese voices spell or read wrong (case-sensitive: "IA" must not touch the verb "ia").
PRONUNCIATION = {
    "CRM": "cê érre ême",
    "Automation": "Automêichon",
    "KIARA": "Kiara",
    "IA": "I A",
    "SDR": "ésse dê érre",
    "ERP": "é érre pê",
    "API": "a pê í",
    "QR": "quê érre",
    "SaaS": "sás",
    "ROI": "retorno sobre o investimento",
}
# English words Francisca reads letter by letter in Portuguese. Checked on 2026-11-18 by synthesizing each word in
# a sentence and transcribing it back (faster-whisper, pt): only the words that came back wrong are here. Most
# loanwords (leads, WhatsApp, online, feedback, app, site, dashboard, startup, design) already sound right and a
# respelling made them worse. Case-insensitive.
LOANWORDS = {
    "follow-ups": "fólou ápis",
    "follow-up": "fólou ápi",
    "follow up": "fólou ápi",
    "followup": "fólou ápi",
    "stories": "stóris",
    "story": "stóri",
    "reels": "vídeos curtos",
    "reel": "vídeo curto",
    "insights": "ínsaitis",
    "insight": "ínsaiti",
}
_PER = {"mês": "por mês", "mes": "por mês", "dia": "por dia", "ano": "por ano", "hora": "por hora", "h": "por hora",
        "semana": "por semana", "pessoa": "por pessoa", "unidade": "por unidade"}
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
_BOUND = r"(?<![\wÀ-ÿ]){}(?![\wÀ-ÿ])"


def _clock(match: re.Match[str]) -> str:
    hours, minutes = int(match.group(1)), match.group(2)
    if hours > 23 or int(minutes) > 59:
        return match.group(0)
    unit = "hora" if hours == 1 else "horas"
    return f"{hours} {unit}" if minutes == "00" else f"{hours} {unit} e {int(minutes)}"


def speakable_symbols(text: str) -> str:
    """Formats the voice reads oddly, written the way a person says them (14h30, 3x, R$ 99/mês, a/b, etc.)."""
    text = _EMOJI.sub("", text)
    text = re.sub(r"\b(\d{1,2})(?:h|:)(\d{2})\b", _clock, text)
    text = re.sub(r"\b(\d+)\s?x(?![\wÀ-ÿ])", r"\1 vezes", text)
    text = re.sub(r"(?<=[\d\wÀ-ÿ])\s?/\s?(mês|mes|dia|ano|hora|h|semana|pessoa|unidade)\b",
                  lambda m: " " + _PER[m.group(1).lower()], text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[A-Za-zÀ-ÿ])/(?=[A-Za-zÀ-ÿ])", " ou ", text)
    text = re.sub(r"\betc\b", "etcétera", text)
    text = re.sub(r"\s*(?:->|→|=>)\s*", ", ", text)
    text = re.sub(r"(?<=[\d\s])=(?=[\s\d])", " é igual a ", text)
    text = re.sub(r"(?<=\s)~\s?(?=\d)", "cerca de ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r" +([,.;:!?])", r"\1", text).strip()


def spoken(text: str, extra: dict[str, str] | None = None) -> str:
    """Rewrite what the voice mispronounces (e.g. CRM -> "cê érre ême", follow-up -> "fólou ápi", 14h30)."""
    text = speakable_symbols(text)
    for word, sound in LOANWORDS.items():
        text = re.sub(_BOUND.format(re.escape(word)), sound, text, flags=re.IGNORECASE)
    for word, sound in {**PRONUNCIATION, **(extra or {})}.items():
        text = re.sub(_BOUND.format(re.escape(word)), sound, text)
    return text
