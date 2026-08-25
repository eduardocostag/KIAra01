from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Intent:
    name: str
    confidence: float
    parameters: dict[str, Any] = field(default_factory=dict)


class IntentMatcher(Protocol):
    def match(self, message: str) -> Intent | None: ...


@dataclass(frozen=True, slots=True)
class PatternMatcher:
    name: str
    pattern: re.Pattern[str]
    parameter_names: tuple[str, ...] = ()
    confidence: float = 1.0

    def match(self, message: str) -> Intent | None:
        matched = self.pattern.search(message)
        if matched is None:
            return None
        parameters = {
            key: value.strip().rstrip(".!?")
            for key, value in zip(self.parameter_names, matched.groups(), strict=True)
            if value is not None
        }
        return Intent(self.name, self.confidence, parameters)


class IntentRouter:
    def __init__(self, matchers: list[IntentMatcher] | None = None) -> None:
        self._matchers = matchers or default_matchers()

    def route(self, message: str) -> Intent:
        for matcher in self._matchers:
            intent = matcher.match(message)
            if intent is not None:
                return intent
        return Intent("conversation", 0.5, {"message": message})


def default_matchers() -> list[IntentMatcher]:
    flags = re.IGNORECASE
    return [
        PatternMatcher(
            "current_datetime",
            re.compile(
                r"(?:que\s+dia\s+(?:é|e)\s+hoje|qual\s+(?:é|e)\s+a\s+data(?:\s+de\s+hoje)?|"
                r"data\s+de\s+hoje|qual\s+(?:é|e)\s+(?:a\s+)?hora|que\s+horas\s+são)",
                flags,
            ),
        ),
        PatternMatcher(
            "helpdesk_verify",
            re.compile(
                r"(?:verifique|confira|teste).{0,30}(?:se|que).{0,12}(?:resolveu|melhorou|funcionou)"
                r"(?:.{0,20}(driver|drivers|rede|network|internet|bateria|battery|evento|eventos|logs))?",
                flags,
            ),
            ("category",),
        ),
        PatternMatcher(
            "helpdesk_diagnostic",
            re.compile(
                r"(?:faça|faca|rode|execute|realize|colete).{0,25}(?:um\s+)?"
                r"(?:diagnóstico|diagnostico|checagem|verificação|verificacao)"
                r"(?:.{0,30}(driver|drivers|rede|network|internet|bateria|battery|evento|eventos|logs))?",
                flags,
            ),
            ("category",),
        ),
        PatternMatcher(
            "sync_obsidian", re.compile(r"(?:sincronize|atualize).{0,20}obsidian", flags)
        ),
        PatternMatcher(
            "search_obsidian",
            re.compile(
                r"(?:pesquise|procure|busque).{0,12}(?:no|meu)\s+obsidian(?:\s+por)?\s+(.+)", flags
            ),
            ("query",),
        ),
        PatternMatcher(
            "open_obsidian_note",
            re.compile(r"(?:abra|abrir).{0,12}(?:a\s+)?nota\s+(.+?)\s+(?:no|do)\s+obsidian", flags),
            ("note",),
        ),
        PatternMatcher(
            "save_obsidian_note",
            re.compile(r"(?:salve|grave|anote).{0,12}(?:no|meu)\s+obsidian\s*:?\s*(.+)", flags),
            ("content",),
        ),
        PatternMatcher(
            "complex_task",
            re.compile(
                r"(?:planeje e execute|execute (?:os )?seguintes passos|tarefa complexa)", flags
            ),
        ),
        PatternMatcher("active_window", re.compile(r"(?:qual programa|janela ativa)", flags)),
        PatternMatcher(
            "screen_capability",
            re.compile(
                r"(?:consegue|pode|voc[eê]\s+consegue|voc[eê]\s+pode).{0,30}"
                r"(?:ver|enxergar|analisar|ler).{0,20}(?:minha|a)?\s*tela",
                flags,
            ),
        ),
        PatternMatcher(
            "powershell",
            re.compile(r"(?:powershell\s+(?:o\s+)?comando|comando)\s+([\w-]+)\s*[.!?]?$", flags),
            ("command",),
        ),
        PatternMatcher(
            "screen_context",
            re.compile(
                r"(?:o\s*que|oque).{0,20}(?:estou|est[aá]|t[oô]|voc[eê]).{0,12}"
                r"(?:vendo|v[eê])|"
                r"(?:descreva|analise|leia|explique|olha|olhe|observe).{0,20}"
                r"(?:minha|a|essa)?\s*tela|"
                r"(?:olha|olhe|analise|explique).{0,20}(?:o\s+que\s+est[aá]|o\s+conte[uú]do).{0,20}"
                r"(?:na|d[aá]|nessa)\s*tela|"
                r"(?:essa|esta)\s+tela",
                flags,
            ),
        ),
        PatternMatcher(
            "open_url", re.compile(r"(?:abra|abrir|acesse)\s+(https?://\S+)", flags), ("url",)
        ),
        PatternMatcher(
            "open_application",
            re.compile(r"(?:abra|abrir)\s+(?:(?:o|a)\s+)?(.+?)(?:\s+por favor)?[.!?]?$", flags),
            ("application",),
        ),
    ]
