"""Read-only discovery of packaged skills; never executes instructions or scripts."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml


def _words(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return set(re.findall(r"[a-z0-9]+", normalized))


class OperationalSkills:
    def __init__(self, resources: Path | None = None) -> None:
        self.resources = resources or Path(__file__).resolve().parents[1] / "resources"

    def _entries(self) -> dict[str, Path]:
        entries: dict[str, Path] = {}
        for folder in ("instagram_agent/skills", "operational_skills"):
            root = self.resources / folder
            for path in sorted(root.glob("*/SKILL.md")):
                if path.resolve().is_relative_to(self.resources.resolve()):
                    entries[path.parent.name] = path
        return entries

    def catalog(self) -> list[dict[str, str]]:
        result = []
        for name, path in self._entries().items():
            text = path.read_text(encoding="utf-8-sig")
            parts = text.split("---", 2)
            meta = yaml.safe_load(parts[1]) if len(parts) == 3 else {}
            result.append({"name": name, "description": str((meta or {}).get(
                "description", name
            ))[:700]})
        return result

    def read(self, name: str, resource: str = "SKILL.md") -> str:
        path = self._entries().get(name)
        if path is None:
            raise ValueError("Skill operacional desconhecida.")
        candidate = (path.parent / resource).resolve()
        if not candidate.is_relative_to(path.parent.resolve()):
            raise ValueError("Recurso fora da skill.")
        if candidate.suffix.lower() not in {".md", ".json"} or not candidate.is_file():
            raise ValueError("Somente referências Markdown/JSON da skill podem ser lidas.")
        if candidate.stat().st_size > 100_000:
            raise ValueError("Referência excede o limite de leitura.")
        return candidate.read_text(encoding="utf-8-sig")[:20_000]

    def relevant(self, query: str) -> list[dict[str, Any]]:
        words = _words(query)
        instagram = bool(words & {"instagram", "reel", "reels", "legenda", "caption",
                                   "carrossel", "carousel", "ig", "bio", "stories"})
        entries = self.catalog()
        scored = []
        aliases = {
            "google-maps-scraper": {"maps", "mapas", "prospeccao", "prospectar", "captar", "captacao"},
            "kiara-freellmapi": {"freellmapi"},
            "kiara-chatwoot": {"chatwoot"},
            "kiara-video-studio": {"video", "videos", "apresentacao", "narracao", "narrado", "mp4"},
            "ig-reel": {"reel", "reels", "roteiro", "gancho", "hook", "ganchos"},
            "ig-caption": {"legenda", "legendas", "caption", "hashtags"},
            "ig-carousel": {"carrossel", "carrosseis", "carousel", "slides"},
            "ig-story": {"story", "stories"},
            "ig-profile": {"perfil", "bio", "profile"},
            "ig-plan": {"planeje", "planejar", "calendario", "cronograma"},
            "ig-dm": {"dm", "direct"},
            "ig-comment": {"comentario", "comentarios", "comment"},
            "ig-human": {"humanize", "humanizar", "artificial"},
            "ig-audit": {"audite", "auditar", "auditoria"},
            "ig-reply": {"resposta", "responder", "reply"},
            "ig-repurpose": {"reaproveite", "reaproveitar", "repurpose"},
            "ig-viral": {"viral", "viralizacao", "viralizar"},
        }
        for entry in entries:
            score = len(words & _words(entry["name"] + " " + entry["description"]))
            score += 20 * len(words & aliases.get(entry["name"], set()))
            if instagram and entry["name"].startswith("ig-"):
                score += 1
            if score:
                scored.append((score, entry["name"], entry))
        selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:2]
        return [{**entry, "content": self.read(name)[:5_000],
                 "trust": "untrusted_reference", "tool": "operational_skill"}
                for _, name, entry in selected]
