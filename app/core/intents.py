from __future__ import annotations

import re
import unicodedata
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
            key: value.strip() if key in {"text", "body"} else value.strip().rstrip(".!?")
            for key, value in zip(self.parameter_names, matched.groups(), strict=True)
            if value is not None
        }
        return Intent(self.name, self.confidence, parameters)


@dataclass(frozen=True, slots=True)
class LocalLeadResearchMatcher:
    """Concept-based matcher tolerant of natural phrasing and small transcription errors."""

    name: str = "local_lead_research"

    def match(self, message: str) -> Intent | None:
        normalized = self._normalize(message)
        tokens = normalized.split()

        discovery = self._has_approx(
            tokens,
            (
                "buscar", "busque", "pesquise", "procurar", "procure", "ache",
                "encontre", "traga", "lista", "prospectar", "prospecte",
            ),
        ) or bool(re.search(r"\b\d{1,3}\b", normalized))

        lead_noun = self._has_approx(tokens, ("lead", "leads", "prospecto", "prospectos"))
        no_site = bool(
            re.search(
                r"\b(?:sem|nao (?:tem|tenham|possui|possuem|possua|possuam))\b.{0,18}"
                r"\b(?:sites?|paginas?|dominios?|presenca digital|site proprio|site pr\w+)\b",
                normalized,
            )
        )
        contact = self._has_approx(
            tokens, ("whatsapp", "whats", "whatssap", "zap", "telefone", "contato")
        )
        outreach = bool(
            re.search(r"\b(?:oferecer|vender|prospectar|chamar|entrar em contato|falar com|contatar)\b", normalized)
        )
        business = bool(
            re.search(
                r"\b(?:empresa|empresa local|loja|lojista|escola|consultorio|cl\w+nica|"
                r"servi[cç]o|prestador|profissional|atendimento|neg[oó]cio|estabelecimento|"
                r"barbearia|beauty|estetica|oficina|restaurante|advogado|mecanica|psicologo|"
                r"veterinario|dentista|odontologia|medico|contabilidade|imobiliaria)\b",
                normalized,
            )
        )
        possible_niche = bool(
            re.search(
                r"\b(?:[a-z]+(?:\s+[a-z]+){0,4}\s*(?:de|da|do)?\s*[a-z]+(?:\s+[a-z]+){0,3}\s*(?:em|na|no))\b",
                normalized,
            )
        )

        digital_gap = no_site or contact or outreach or lead_noun
        target = business or possible_niche or self._has_approx(
            tokens,
            (
                "dentista", "dentistas", "odontologista", "odontologia", "clinica",
                "clinicas", "profissional", "profissionais", "loja", "lojas", "empresa",
                "empresas", "negocio", "negocios", "servico", "servicos"
            ),
        )

        if target and discovery and digital_gap:
            return Intent(self.name, 0.96, {})
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        value = unicodedata.normalize("NFKD", value.casefold())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())

    @classmethod
    def _has_approx(cls, tokens: list[str], choices: tuple[str, ...]) -> bool:
        return any(cls._edit_distance_at_most_one(token, choice) for token in tokens for choice in choices)

    @staticmethod
    def _edit_distance_at_most_one(left: str, right: str) -> bool:
        if left == right:
            return True
        if abs(len(left) - len(right)) > 1 or min(len(left), len(right)) < 4:
            return False
        if len(left) == len(right):
            return sum(a != b for a, b in zip(left, right, strict=True)) <= 1
        shorter, longer = (left, right) if len(left) < len(right) else (right, left)
        index_short = index_long = differences = 0
        while index_short < len(shorter) and index_long < len(longer):
            if shorter[index_short] == longer[index_long]:
                index_short += 1
            else:
                differences += 1
                if differences > 1:
                    return False
            index_long += 1
        return True


@dataclass(frozen=True, slots=True)
class OrganicConsumerResearchMatcher:
    name: str = "organic_consumer_research"

    def match(self, message: str) -> Intent | None:
        normalized = LocalLeadResearchMatcher._normalize(message)
        if not re.search(r"\b(?:b2c|consumidores?|pessoas?|clientes? finais?)\b", normalized):
            return None
        if not re.search(r"\b(?:busque|pesquise|procure|encontre|traga|capte)\b", normalized):
            return None
        if not re.search(r"\b(?:organicos?|instagram|facebook|tiktok|linkedin|redes sociais)\b", normalized):
            return None
        count_match = re.search(r"\b(\d{1,2})\b", normalized)
        location_match = re.search(
            r"\b(?:em|no|na)\s+(rio grande do sul|rs|[a-z ]+?)(?:\s+(?:no|na)\s+|$)",
            normalized,
        )
        niche_match = re.search(
            r"\b(?:para|de)\s+(.+?)(?:\s+(?:em|no|na)\s+(?:rio grande do sul|rs)|$)",
            normalized,
        )
        return Intent(self.name, 0.98, {
            "query": (niche_match.group(1) if niche_match else "serviços locais").strip(),
            "location": (location_match.group(1) if location_match else "Rio Grande do Sul").strip(),
            "limit": min(40, int(count_match.group(1))) if count_match else 20,
        })


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
        OrganicConsumerResearchMatcher(),
        LocalLeadResearchMatcher(),
        PatternMatcher(
            "realtime_research",
            re.compile(
                r"(?:escala[cç][aã]o|palpites?\s+(?:de\s+)?aposta|apostas?|"
                r"jogos?.{0,20}hoje|placar.{0,20}hoje|resultados?.{0,20}hoje|"
                r"not[ií]cias?.{0,20}hoje|quem\s+joga.{0,20}hoje)",
                flags,
            ),
        ),
        PatternMatcher(
            "network_ping",
            re.compile(
                r"(?:abra|abre|abrir)\s+(?:o\s+)?cmd\s+e\s+(?:d[eê]|fa[cç]a|execute)\s+"
                r"(?:um\s+)?ping\s+(-a\s+)?(?:em|para)?\s*"
                r"([a-zA-Z0-9.-]+)[.!?]?$",
                flags,
            ),
            ("resolve_name", "target"),
        ),
        PatternMatcher(
            "correction_inbox",
            re.compile(
                r"(?:onde\s+(?:est[aã]o|fica(?:m)?)|mostre|liste|abra).{0,25}"
                r"(?:corre[cç][aã]o|corre[cç][oõ]es)(?:\s+pendentes)?|"
                r"(?:arquivo|caixa).{0,15}(?:de\s+)?corre[cç][oõ]es",
                flags,
            ),
        ),
        PatternMatcher(
            "current_datetime",
            re.compile(
                r"(?:que\s+dia\s+(?:é|e)\s+hoje|qual\s+(?:é|e)\s+a\s+data(?:\s+de\s+hoje)?|"
                r"data\s+de\s+hoje|qual\s+(?:é|e)\s+(?:a\s+)?hora|que\s+horas\s+são)",
                flags,
            ),
        ),
        PatternMatcher(
            "work_calendar",
            re.compile(
                r"(?:veja|mostre|liste|consulte).{0,25}"
                r"(?:(?:reuni[oõ]es?).{0,15}teams|calend[aá]rio|agenda)"
                r"(?:.{0,20}(semana|hoje|amanh[aã]))?",
                flags,
            ),
            ("period",),
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
            "list_personal_tasks",
            re.compile(r"(?:liste|mostre|quais s[aÃ£]o).{0,15}(?:minhas\s+)?tarefas", flags),
        ),
        PatternMatcher(
            "complete_personal_task",
            re.compile(r"(?:conclua|complete|finalize).{0,12}tarefa\s+([a-fA-F0-9-]{8,36})", flags),
            ("task_id",),
        ),
        PatternMatcher(
            "add_personal_task",
            re.compile(r"(?:adicione|crie|anote).{0,12}(?:uma\s+)?tarefa(?:\s+de)?\s+(.+)$", flags),
            ("title",),
        ),
        PatternMatcher(
            "list_personal_events",
            re.compile(
                r"(?:liste|mostre|quais s[aÃ£]o).{0,20}(?:meus\s+)?(?:compromissos|eventos|agenda)",
                flags,
            ),
        ),
        PatternMatcher(
            "add_personal_event",
            re.compile(
                r"(?:agende|marque).{0,8}(.+?)\s+(?:para|em)\s+"
                r"(hoje|amanh[aÃ£]|\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})"
                r"\s+(?:[aÃà]s?\s+)?(\d{1,2})(?::(\d{2}))?(?:h)?$",
                flags,
            ),
            ("title", "date", "hour", "minute"),
        ),
        PatternMatcher(
            "search_personal_files",
            re.compile(r"(?:encontre|localize|procure).{0,15}(?:o\s+)?arquivo\s+(.+)$", flags),
            ("query",),
        ),
        PatternMatcher(
            "draft_email",
            re.compile(
                r"(?:crie|prepare|escreva).{0,15}rascunho(?:\s+de)?\s+e-?mail\s+para\s+"
                r"([^\s]+@[^\s]+)\s+assunto\s+(.+?)\s+(?:mensagem|corpo)\s+(.+)$",
                flags,
            ),
            ("to", "subject", "body"),
        ),
        PatternMatcher(
            "list_mcp_servers",
            re.compile(r"(?:liste|mostre).{0,20}servidores\s+mcp", flags),
        ),
        PatternMatcher(
            "discover_mcp_tools",
            re.compile(
                r"(?:liste|mostre|descubra).{0,20}ferramentas\s+mcp"
                r"(?:\s+do|\s+no)?\s+servidor\s+([a-zA-Z0-9_-]+)",
                flags,
            ),
            ("server",),
        ),
        PatternMatcher(
            "call_mcp_tool",
            re.compile(
                r"(?:execute|use|chame).{0,12}ferramenta\s+mcp\s+([\w./:-]+)"
                r"\s+(?:do|no)\s+servidor\s+([a-zA-Z0-9_-]+)"
                r"\s+com\s+argumentos\s+(\{.*\})$",
                flags,
            ),
            ("tool", "server", "arguments"),
        ),
        PatternMatcher(
            "build_business_site",
            re.compile(
                r"(?:crie|gere|construa).{0,20}(?:um\s+)?site(?:\s+completo)?\s+para\s+"
                r"(.+?)(?:\s+usando\s+(?:a\s+)?imagem\s+.+)?$",
                flags,
            ),
            ("business_info",),
        ),
        PatternMatcher(
            "resume_goal",
            re.compile(
                r"(?:execute|retome|continue)(?:\s+o)?\s+plano"
                r"(?:\s+de\s+recupera(?:ção|cao))?\s+(\d+)",
                flags,
            ),
            ("goal_id",),
        ),
        PatternMatcher(
            "complex_task",
            re.compile(
                r"(?:planeje e execute|execute (?:os )?seguintes passos|tarefa complexa)", flags
            ),
        ),
        PatternMatcher("active_window", re.compile(r"(?:qual programa|janela ativa)", flags)),
        PatternMatcher(
            "create_recurring_automation",
            re.compile(
                r"(?:crie|prepare|configure|adicione).{0,18}(?:uma\s+)?automa[cç][aã]o"
                r"\s+(?:para\s+)?abrir\s+(https://\S+?)\s+a\s+cada\s+"
                r"(\d+)\s*(minutos?|horas?|dias?)[.!?]?$",
                flags,
            ),
            ("url", "interval", "unit"),
        ),
        PatternMatcher(
            "start_workflow_design",
            re.compile(
                r"(?:crie|monte|configure|desenhe|automatize).{0,28}"
                r"(?:(?:automa[cç][aã]o|fluxo).{0,20}(?:complex[ao]|atendimento|suporte)|"
                r"(?:atendimento|suporte).{0,20}(?:whatsapp|instagram|telegram|hardware|software))",
                flags,
            ),
        ),
        PatternMatcher(
            "list_workflows",
            re.compile(
                r"(?:liste|mostre|quais\s+s[aã]o).{0,20}"
                r"(?:fluxos|automa[cç][oõ]es).{0,18}(?:complex[ao]s?|atendimento|suporte)",
                flags,
            ),
        ),
        PatternMatcher(
            "list_automations",
            re.compile(
                r"(?:liste|mostre|quais\s+s[aã]o).{0,18}(?:minhas\s+)?automa[cç][oõ]es",
                flags,
            ),
        ),
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
                r"(?:acompanhe|observe|monitore).{0,25}(?:minha|a|essa)?\s*tela|"
                r"(?:acompanhe|observe).{0,25}o\s+que\s+(?:estou|eu\s+estou)\s+fazendo|"
                r"(?:essa|esta)\s+tela",
                flags,
            ),
        ),
        PatternMatcher(
            "social_message",
            re.compile(
                r"(?:mande|envie|escreva)\s+(?:uma\s+)?mensagem\s+(?:no|pelo)\s+"
                r"(instagram|whatsapp|telegram)\s+(?:para|pro|ao|à)\s+"
                r"([@+\w. -]+?)\s+(?:dizendo|com\s+o\s+texto|mensagem)\s+(.+)$",
                flags,
            ),
            ("platform", "recipient", "text"),
        ),
        PatternMatcher(
            "social_message_direct",
            re.compile(
                r"(?=.*\b(instagram|whatsapp|telegram)\b).*\b(?:direct|conversa)\s+"
                r"(?:de|com)\s+([@+\w. -]+?)\s+(?:no|do)\s+"
                r"(?:instagram|whatsapp|telegram).*?(?:escreva|digite)\s+"
                r"(.+?)(?:\s+e\s+envie)?[.!?]?$",
                flags,
            ),
            ("platform", "recipient", "text"),
        ),
        PatternMatcher(
            "web_search",
            re.compile(
                r"(?:abra\s+o\s+google\s+e\s+)?(?:pesquise|procure|busque)"
                r"(?:\s+(?:no\s+google|na\s+internet))?"
                r"(?:\s+(?:por|sobre))?\s+(.+?)"
                r"(?:\s+(?:no\s+google|na\s+internet))?$",
                flags,
            ),
            ("query",),
        ),
        PatternMatcher(
            "web_search",
            re.compile(
                r"(?:abra|abre|abrir)\s+(?:o\s+|a\s+)?(.+?)\s+"
                r"(?:no|pelo)\s+google[.!?]?$",
                flags,
            ),
            ("query",),
        ),
        PatternMatcher(
            "browser_fill",
            re.compile(
                r"(?:preencha|escreva|digite).{0,15}(?:no\s+)?campo\s+(.+?)\s+"
                r"(?:com|o\s+texto)\s+(.+)$",
                flags,
            ),
            ("label", "text"),
        ),
        PatternMatcher(
            "browser_click",
            re.compile(
                r"(?:clique|pressione).{0,10}(?:no|na)\s+"
                r"(bot[aã]o|link|caixa\s+de\s+sele[cç][aã]o)\s+(.+)$",
                flags,
            ),
            ("role", "name"),
        ),
        PatternMatcher(
            "browser_read",
            re.compile(
                r"(?:leia|resuma|explique|analise).{0,20}(?:esta|essa|a)\s+"
                r"(?:p[aá]gina|site)(?:\s+atual)?",
                flags,
            ),
        ),
        PatternMatcher(
            "open_url", re.compile(r"(?:abra|abrir|acesse)\s+(https?://\S+)", flags), ("url",)
        ),
        PatternMatcher(
            "open_website",
            re.compile(r"(?:abra|abrir|acesse)\s+(?:o\s+)?site\s+(?:do|da|de)?\s*(.+)$", flags),
            ("target",),
        ),
        PatternMatcher(
            "open_website",
            re.compile(
                r"(?:abra|abrir|acesse)\s+((?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+\S*)$",
                flags,
            ),
            ("target",),
        ),
        PatternMatcher(
            "open_application",
            re.compile(
                r"(?:abra|abre|abrir)\s+(?:(?:o|a)\s+)?(.+?)"
                r"(?:\s+por favor)?[.!?]?$",
                flags,
            ),
            ("application",),
        ),
    ]
