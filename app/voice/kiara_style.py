"""Kiara's speaking style, shared by the chat voice and the presentation videos.

One place for the voice, pace and pronunciation fixes, so Kiara sounds the same everywhere.
"""
from __future__ import annotations

import re

# Native pt-BR voice. ThalitaMultilingual mixes languages and sounds Spanish on names and greetings.
VOICE = "pt-BR-FranciscaNeural"
# Slightly brisker than default: natural and confident without sounding rushed.
RATE = "+2%"
# Words the Portuguese voices tend to mispronounce. Applied to the spoken text only.
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
}


def spoken(text: str, extra: dict[str, str] | None = None) -> str:
    """Rewrite words that the voice mispronounces (e.g. CRM -> "cê érre ême")."""
    for word, sound in {**PRONUNCIATION, **(extra or {})}.items():
        text = re.sub(rf"(?<![\wÀ-ÿ]){re.escape(word)}(?![\wÀ-ÿ])", sound, text)
    return text
