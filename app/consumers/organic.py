from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class OrganicOpportunity:
    platform: str
    source_url: str
    title: str
    excerpt: str
    intent_score: int
    intent_signals: tuple[str, ...]
    location: str = ""
    status: str = "revisar"


class OrganicIntentClassifier:
    """Classifica sinais públicos sem inferir identidade ou autorização de contato."""

    SIGNALS: ClassVar[dict[str, tuple[str, int]]] = {
        "pedido de indicação": (r"\bindic(?:a|acao|ação|am|aria)\b", 24),
        "procura ativa": (r"\b(?:procuro|procurando|preciso|busco|onde encontro)\b", 28),
        "pedido de preço": (r"\b(?:preco|preço|valor|orcamento|orçamento|quanto custa)\b", 24),
        "urgência": (r"\b(?:urgente|hoje|essa semana|esta semana|o quanto antes)\b", 14),
        "localização": (r"\b(?:em|perto|proximo|próximo|regiao|região)\b", 8),
    }
    PLATFORM_HOSTS: ClassVar[dict[str, str]] = {
        "instagram.com": "instagram",
        "facebook.com": "facebook",
        "tiktok.com": "tiktok",
        "linkedin.com": "linkedin",
    }

    def classify(self, *, url: str, title: str, excerpt: str, location: str = "") -> OrganicOpportunity | None:
        host = (urlparse(url).hostname or "").casefold().removeprefix("www.")
        platform = next((value for key, value in self.PLATFORM_HOSTS.items() if host == key or host.endswith(f".{key}")), "")
        if not platform:
            return None
        text = self._normalize(f"{title} {excerpt}")
        matched = tuple(label for label, (pattern, _weight) in self.SIGNALS.items() if re.search(pattern, text))
        if not matched:
            return None
        score = min(100, 20 + sum(self.SIGNALS[label][1] for label in matched))
        return OrganicOpportunity(platform, url, title.strip(), excerpt.strip(), score, matched, location.strip())

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(normalized.split())
