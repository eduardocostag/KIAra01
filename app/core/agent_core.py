from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from app.agents.router import AgentRouter
from app.consumers import ConsumerStore, OrganicIntentClassifier
from app.core.context import ContextManager
from app.core.intents import Intent, IntentRouter
from app.helpdesk import compare_snapshots
from app.leads import LeadScoringPolicy, LeadStore
from app.leads.intelligence import CommercialIntelligenceService
from app.perception import ScreenPerception
from app.perception.analysis import (
    parse_screen_analysis,
    screen_analysis_is_consistent,
    screen_analysis_prompt,
)
from app.planning import PlanRejected, TaskPlanner
from app.providers.llm import LLMProvider
from app.tools.registry import ToolRegistry
from app.workflows import ConversationalWorkflowBuilder

IntentHandler = Callable[[Intent, str], Awaitable[str]]


class FeedbackLearningStore(Protocol):
    def save(self, user_message: str, assistant_response: str) -> Any: ...


class CorrectionInboxStore(Protocol):
    path: Any

    def add(self, user_message: str, assistant_response: str) -> str: ...

    def pending_count(self) -> int: ...


class AgentCore:
    def __init__(
        self,
        tools: ToolRegistry,
        llm: LLMProvider,
        context: ContextManager,
        router: IntentRouter | None = None,
        agent_router: AgentRouter | None = None,
        background: Any | None = None,
        resources: list[Any] | None = None,
        task_planner: TaskPlanner | None = None,
        perception: ScreenPerception | None = None,
        feedback_learning: FeedbackLearningStore | None = None,
        correction_inbox: CorrectionInboxStore | None = None,
        feedback_prompt: str = "Te auxiliei?",
        workflow_builder: ConversationalWorkflowBuilder | None = None,
        lead_store: LeadStore | None = None,
        consumer_store: ConsumerStore | None = None,
    ) -> None:
        self.tools, self.llm, self.context = tools, llm, context
        self.router = router or IntentRouter()
        self.agent_router = agent_router or AgentRouter(llm)
        self.background = background
        self.resources = resources or []
        self.task_planner = task_planner
        self.perception = perception
        self.feedback_learning = feedback_learning
        self.correction_inbox = correction_inbox
        self.feedback_prompt = feedback_prompt.strip() or "Te auxiliei?"
        self.workflow_builder = workflow_builder
        self.lead_store = lead_store
        self.consumer_store = consumer_store
        self._pending_feedback: tuple[str, str] | None = None
        self._pending_site_brief: tuple[str, str] | None = None
        self._pending_local_lead_research: str | None = None
        self._diagnostic_baselines: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, IntentHandler] = {
            "active_window": self._active_window,
            "open_application": self._open_application,
            "powershell": self._powershell,
            "network_ping": self._network_ping,
            "screen_context": self._screen_context,
            "screen_capability": self._screen_capability,
            "open_url": self._open_url,
            "open_website": self._open_website,
            "web_search": self._web_search,
            "browser_fill": self._browser_fill,
            "browser_click": self._browser_click,
            "browser_read": self._browser_read,
            "social_message": self._social_message,
            "social_message_direct": self._social_message,
            "conversation": self._conversation,
            "complex_task": self._complex_task,
            "resume_goal": self._resume_goal,
            "build_business_site": self._build_business_site,
            "list_mcp_servers": self._list_mcp_servers,
            "discover_mcp_tools": self._discover_mcp_tools,
            "call_mcp_tool": self._call_mcp_tool,
            "add_personal_task": self._add_personal_task,
            "list_personal_tasks": self._list_personal_tasks,
            "complete_personal_task": self._complete_personal_task,
            "add_personal_event": self._add_personal_event,
            "list_personal_events": self._list_personal_events,
            "search_personal_files": self._search_personal_files,
            "draft_email": self._draft_email,
            "sync_obsidian": self._sync_obsidian,
            "search_obsidian": self._search_obsidian,
            "open_obsidian_note": self._open_obsidian_note,
            "save_obsidian_note": self._save_obsidian_note,
            "helpdesk_diagnostic": self._helpdesk_diagnostic,
            "helpdesk_verify": self._helpdesk_verify,
            "current_datetime": self._current_datetime,
            "correction_inbox": self._correction_inbox,
            "work_calendar": self._work_calendar,
            "realtime_research": self._realtime_research,
            "local_lead_research": self._local_lead_research,
            "organic_consumer_research": self._organic_consumer_research,
            "create_recurring_automation": self._create_recurring_automation,
            "list_automations": self._list_automations,
            "start_workflow_design": self._start_workflow_design,
            "list_workflows": self._list_workflows,
        }

    async def handle(self, message: str) -> str:
        if self.workflow_builder is not None and self.workflow_builder.active:
            self._pending_feedback = None
            response = self.workflow_builder.consume(message)
            self.context.remember_exchange(message, response)
            return response
        lead_followup = await self._consume_local_lead_location(message)
        if lead_followup is not None:
            self._pending_feedback = None
            displayed = self._request_feedback(message, lead_followup)
            self.context.remember_exchange(message, lead_followup)
            return displayed
        site_followup = await self._consume_site_source(message)
        if site_followup is not None:
            self._pending_feedback = None
            displayed = self._request_feedback(message, site_followup)
            self.context.remember_exchange(message, site_followup)
            return displayed
        feedback = self._consume_feedback(message)
        if feedback is not None:
            return feedback
        self._pending_feedback = None
        intent = self.router.route(message)
        response = await self._handlers.get(intent.name, self._conversation)(intent, message)
        if intent.name == "start_workflow_design" and self.workflow_builder is not None:
            self.context.remember_exchange(message, response)
            return response
        displayed = self._request_feedback(message, response)
        # The feedback question belongs to the UI, not to future model context.
        self.context.remember_exchange(message, response)
        return displayed

    async def handle_stream(self, message: str) -> AsyncIterator[str]:
        """Stream ordinary conversation while preserving safe handlers for actions."""
        if self.workflow_builder is not None and self.workflow_builder.active:
            self._pending_feedback = None
            response = self.workflow_builder.consume(message)
            self.context.remember_exchange(message, response)
            yield response
            return
        lead_followup = await self._consume_local_lead_location(message)
        if lead_followup is not None:
            self._pending_feedback = None
            displayed = self._request_feedback(message, lead_followup)
            self.context.remember_exchange(message, lead_followup)
            yield displayed
            return
        site_followup = await self._consume_site_source(message)
        if site_followup is not None:
            self._pending_feedback = None
            displayed = self._request_feedback(message, site_followup)
            self.context.remember_exchange(message, site_followup)
            yield displayed
            return
        feedback = self._consume_feedback(message)
        if feedback is not None:
            yield feedback
            return
        self._pending_feedback = None
        intent = self.router.route(message)
        if intent.name != "conversation":
            response = await self._handlers.get(intent.name, self._conversation)(intent, message)
            if intent.name == "start_workflow_design" and self.workflow_builder is not None:
                self.context.remember_exchange(message, response)
                yield response
                return
            displayed = self._request_feedback(message, response)
            self.context.remember_exchange(message, response)
            yield displayed
            return
        context = self._conversation_context(message)
        if self._screen_related(message):
            context.update(await self._screen_conversation_context(message))
        chunks: list[str] = []
        async for delta in self.agent_router.stream_respond(message, context):
            chunks.append(delta)
            yield delta
        response = "".join(chunks)
        displayed = self._request_feedback(message, response)
        if displayed != response:
            yield f"\n\n{self.feedback_prompt}"
        self.context.remember_exchange(message, response)

    def _request_feedback(self, user_message: str, response: str) -> str:
        if self._pending_site_brief is not None:
            self._pending_feedback = None
            return response
        if self.feedback_learning is None and self.correction_inbox is None:
            return response
        self._pending_feedback = (user_message, response)
        return f"{response.rstrip()}\n\n{self.feedback_prompt}"

    def _consume_feedback(self, message: str) -> str | None:
        if self._pending_feedback is None:
            return None
        normalized = self._normalized(message)
        positive = normalized in {
            "sim",
            "sim ajudou",
            "ajudou",
            "resolveu",
            "com certeza",
        }
        negative = normalized in {"nao", "nao ajudou", "nao resolveu", "ainda nao"} or bool(
            re.match(r"^(?:nao|ainda nao)\b", normalized)
        )
        if not positive and not negative:
            return None
        pending = self._pending_feedback
        if negative:
            self._pending_feedback = None
            if self.correction_inbox is None:
                return "Certo. Não guardei esta conversa no Obsidian."
            try:
                self.correction_inbox.add(*pending)
                count = self.correction_inbox.pending_count()
            except Exception as exc:  # noqa: BLE001 - local persistence boundary
                return (
                    "Não guardei esta conversa no Obsidian, mas não consegui registrá-la "
                    f"para correção ({type(exc).__name__})."
                )
            return (
                "Certo. Não guardei esta conversa no Obsidian. Registrei a resposta para "
                f"correção local ({count} pendente(s)). Diga “onde estão as correções?” "
                "para localizar o arquivo."
            )
        if self.feedback_learning is None:
            self._pending_feedback = None
            return "Entendido. O aprendizado no Obsidian não está habilitado."
        try:
            destination = self.feedback_learning.save(*pending)
        except Exception as exc:  # noqa: BLE001 - local integration boundary
            return f"Não consegui guardar o aprendizado no Obsidian ({type(exc).__name__})."
        self._pending_feedback = None
        return f"Perfeito. Guardei este aprendizado no Obsidian: {destination.name}."

    async def _correction_inbox(self, _intent: Intent, _message: str) -> str:
        if self.correction_inbox is None:
            return "A caixa local de correções não está habilitada."
        count = self.correction_inbox.pending_count()
        return (
            f"Há {count} correção(ões) pendente(s). O arquivo está em:\n"
            f"{self.correction_inbox.path}\n\n"
            "Abra esse arquivo no projeto e anexe-o nesta conversa, ou copie as linhas "
            "que deseja revisar. Ele não é enviado automaticamente."
        )

    def start_background(self) -> None:
        if self.background is not None:
            self.background.start()

    def stop_background(self) -> None:
        if self.background is not None:
            self.background.stop()

    def set_proactive_notifier(self, callback: Callable[[dict[str, object]], None] | None) -> None:
        if self.background is not None:
            self.background.set_proactive_notifier(callback)

    async def astart(self) -> None:
        if self.background is not None:
            await self.background.astart()

    async def aclose(self) -> None:
        errors: list[Exception] = []
        if self.background is not None:
            try:
                await self.background.astop()
            except Exception as exc:  # noqa: BLE001 - continue closing independent resources
                errors.append(exc)
        for resource in reversed(self.resources):
            close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
            if close is None:
                continue
            try:
                outcome = close()
                if hasattr(outcome, "__await__"):
                    await outcome
            except Exception as exc:  # noqa: BLE001 - best-effort coordinated teardown
                errors.append(exc)
        if errors:
            raise ExceptionGroup("Falhas ao encerrar recursos da Kiara", errors)

    async def _active_window(self, _intent: Intent, _message: str) -> str:
        screen = self.context.screen()
        application = screen.active_application or "um aplicativo não identificado"
        return f"Você está usando {application}: {screen.window_title or 'sem título'}."

    async def _open_application(self, intent: Intent, _message: str) -> str:
        requested = str(intent.parameters["application"]).casefold().strip()
        requested = re.sub(r"\s+agora$", "", requested).strip()
        requested = re.sub(r"^(?:o|a|os|as)\s+", "", requested)
        requested = re.sub(
            r"^(?:aplicativo|programa|site)"
            r"(?:\s+(?:do|da|de))?\s+",
            "",
            requested,
        )
        sites = {
            "google": "https://www.google.com",
            "instagram": "https://www.instagram.com",
            "youtube": "https://www.youtube.com",
            "facebook": "https://www.facebook.com",
            "linkedin": "https://www.linkedin.com",
            "twitter": "https://x.com",
            "x": "https://x.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
            "outlook": "https://outlook.live.com",
            "google drive": "https://drive.google.com",
            "google maps": "https://maps.google.com",
            "reddit": "https://www.reddit.com",
            "tiktok": "https://www.tiktok.com",
            "chatgpt": "https://chatgpt.com",
            "openrouter": "https://openrouter.ai",
            "whatsapp": "https://web.whatsapp.com",
            "whats": "https://web.whatsapp.com",
            "telegram": "https://web.telegram.org",
            "windy": "https://www.windy.com",
            "vercel": "https://vercel.com",
            "climatempo": "https://www.climatempo.com.br",
            "clima tempo": "https://www.climatempo.com.br",
            "g1": "https://g1.globo.com",
            "globo": "https://www.globo.com",
            "uol": "https://www.uol.com.br",
            "terra": "https://www.terra.com.br",
            "amazon": "https://www.amazon.com.br",
            "mercado livre": "https://www.mercadolivre.com.br",
            "mercadolivre": "https://www.mercadolivre.com.br",
            "shopee": "https://shopee.com.br",
            "netflix": "https://www.netflix.com",
            "prime video": "https://www.primevideo.com",
            "disney plus": "https://www.disneyplus.com",
            "disney+": "https://www.disneyplus.com",
            "twitch": "https://www.twitch.tv",
            "pinterest": "https://www.pinterest.com",
            "canva": "https://www.canva.com",
            "figma": "https://www.figma.com",
            "notion": "https://www.notion.so",
            "trello": "https://trello.com",
            "asana": "https://asana.com",
            "dropbox": "https://www.dropbox.com",
            "onedrive": "https://onedrive.live.com",
            "office": "https://www.office.com",
            "microsoft 365": "https://www.microsoft365.com",
            "deezer": "https://www.deezer.com",
        }
        kiara_browser_sites = {
            "instagram da kiara": "https://www.instagram.com",
            "whatsapp da kiara": "https://web.whatsapp.com",
            "telegram da kiara": "https://web.telegram.org",
        }
        if requested in kiara_browser_sites:
            return await self._run_tool("browser_navigate", url=kiara_browser_sites[requested])
        if requested in sites:
            return await self._run_tool("open_url", url=sites[requested])
        new_tab = bool(re.search(r"\bnov[ao]\s+aba\b", requested))
        if requested.startswith(("chrome", "google chrome")):
            requested = "chrome"
        result = await self.tools.execute(
            "open_application", application=requested, new_tab=new_tab
        )
        self.context.remember_action("open_application", result.success)
        if result.success:
            return result.output
        fallback = await self.tools.execute(
            "open_url", url=f"https://www.google.com/search?q={quote_plus(requested)}"
        )
        self.context.remember_action("open_url", fallback.success)
        if fallback.success:
            return (
                f"Não encontrei um aplicativo local chamado “{requested}”. "
                "Abri uma pesquisa segura no Google para você encontrar o site ou confirmar "
                "qual programa deseja."
            )
        return f"Não consegui localizar nem pesquisar por {requested}: {fallback.error}"

    async def _create_recurring_automation(self, intent: Intent, _message: str) -> str:
        from app.automation import AutomationSpec, TriggerKind

        engine = getattr(self.background, "automations", None)
        if engine is None:
            return "O mecanismo de automações não está disponível nesta instalação."
        url = str(intent.parameters["url"]).rstrip(".!?")
        amount = int(intent.parameters["interval"])
        unit = self._normalized(str(intent.parameters["unit"]))
        multipliers = {"minuto": 60, "minutos": 60, "hora": 3600, "horas": 3600,
                       "dia": 86400, "dias": 86400}
        seconds = amount * multipliers[unit]
        spec = AutomationSpec(
            name=f"Abrir {url} a cada {amount} {unit}",
            trigger_kind=TriggerKind.RECURRING,
            action="open_url",
            action_parameters={"url": url},
            interval_seconds=seconds,
            enabled=False,
        )
        automation_id = engine.add(spec)
        return (
            f"Preparei a automação {automation_id}: abrir {url} a cada {amount} {unit}. "
            "Ela foi salva desativada para revisão; ative-a no painel Automações quando quiser."
        )

    async def _list_automations(self, _intent: Intent, _message: str) -> str:
        engine = getattr(self.background, "automations", None)
        if engine is None:
            return "O mecanismo de automações não está disponível nesta instalação."
        items = engine.store.list()
        if not items:
            return "Você ainda não possui automações salvas."
        lines = [
            f"- {item.name} ({'ativa' if item.enabled else 'desativada'}; id {item.id})"
            for item in items
        ]
        return "Automações salvas:\n" + "\n".join(lines)

    async def _start_workflow_design(self, _intent: Intent, message: str) -> str:
        if self.workflow_builder is None:
            return "O construtor de fluxos complexos não está disponível nesta instalação."
        return self.workflow_builder.begin(message)

    async def _list_workflows(self, _intent: Intent, _message: str) -> str:
        if self.workflow_builder is None:
            return "O construtor de fluxos complexos não está disponível nesta instalação."
        workflows = self.workflow_builder.store.list()
        if not workflows:
            return "Você ainda não possui fluxos complexos salvos."
        return "Fluxos complexos:\n" + "\n".join(
            f"- {item.name} ({item.channel}; {item.status}; "
            f"{'ativo' if item.enabled else 'desativado'}; id {item.id})"
            for item in workflows
        )

    async def _web_search(self, intent: Intent, _message: str) -> str:
        query = str(intent.parameters["query"]).strip()
        if self._normalized(query) in {"inter", "o inter"}:
            query = "Sport Club Internacional"
        result = await self.tools.execute(
            "browser_navigate", url=f"https://www.google.com/search?q={quote_plus(query)}"
        )
        self.context.remember_action("browser_navigate", result.success)
        if result.success:
            return f"Pesquisa por “{query}” concluída em segundo plano."
        return (
            "Não consegui concluir a pesquisa em segundo plano: "
            f"{result.error or 'fonte indisponível'}. Nenhuma janela foi aberta."
        )

    async def _organic_consumer_research(self, intent: Intent, _message: str) -> str:
        if self.consumer_store is None:
            return "O pipeline B2C não está disponível nesta instalação."
        query = str(intent.parameters.get("query", "serviços locais")).strip()
        location = str(intent.parameters.get("location", "Rio Grande do Sul")).strip()
        limit = int(intent.parameters.get("limit", 20))
        result = await self.tools.execute(
            "organic_consumer_search", query=query, location=location, limit=limit
        )
        self.context.remember_action("organic_consumer_search", result.success)
        if not result.success:
            return (
                "Não consegui concluir a descoberta orgânica em segundo plano: "
                f"{result.error or 'fontes indisponíveis'}. Nenhuma janela foi aberta."
            )
        classifier = OrganicIntentClassifier()
        saved = []
        for item in result.metadata.get("results", []):
            if not isinstance(item, dict):
                continue
            opportunity = classifier.classify(
                url=str(item.get("url", "")), title=str(item.get("title", "")),
                excerpt=str(item.get("excerpt", "")), location=location,
            )
            if opportunity is None:
                continue
            identifier = self.consumer_store.save_organic_opportunity(opportunity)
            saved.append((identifier, opportunity))
        if not saved:
            return (
                "A varredura terminou sem sinais públicos suficientemente claros. "
                "Nenhuma pessoa foi criada como lead e nenhuma mensagem foi enviada."
            )
        lines = [
            f"Encontrei {len(saved)} oportunidade(s) orgânica(s) para revisão no B2C.",
            "São sinais públicos, ainda sem autorização para contato privado:",
        ]
        lines.extend(
            f"- {op.platform.title()} · intenção {op.intent_score}/100 · {op.title or op.source_url}"
            for _identifier, op in saved[:10]
        )
        lines.append("Próximo passo: revisar e responder publicamente; só converter após opt-in.")
        return "\n".join(lines)

    async def _local_lead_research(self, _intent: Intent, message: str) -> str:
        normalized = self._normalized(message)
        statewide_rs = self._is_statewide_rs_request(message)
        has_explicit_location = bool(
            re.search(
                r"\b(?:dentistas?|profissionais?)\b[^.!?]{0,120}\b(?:em|na|no|de)\s+"
                r"[A-Za-zÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9 ,./-]{1,80}",
                message,
                re.IGNORECASE,
            )
            or re.search(
                r"\b(?:sao paulo|rio de janeiro|belo horizonte|porto alegre|curitiba|salvador|"
                r"recife|brasilia|fortaleza|goiania|manaus|belém|belem|joao pessoa|campinas|"
                r"natal|florianopolis|vitoria|aracaju|maceio|teresina|palmas|rio grande|"
                r"novo hamburgo|caxias do sul|canoas|sao leopoldo|gramado|pelotas)\b",
                normalized,
                re.IGNORECASE,
            )
        )
        location_is_vague = bool(
            re.search(
                r"\b(?:onde\s+estamos|perto\s+de\s+mim|minha\s+regiao|aqui\s+perto)\b",
                normalized,
            )
        )
        if (location_is_vague or not has_explicit_location) and not statewide_rs:
            self._pending_local_lead_research = message
            return (
                "Para medir um raio real, preciso do ponto central. Informe a cidade e o estado "
                "ou um CEP (não preciso do seu endereço completo). Depois vou pesquisar os "
                "profissionais, conferir a evidência de site próprio e devolver somente contatos "
                "sustentados pelos resultados. Se não houver 25 verificáveis, informarei a "
                "quantidade encontrada em vez de completar com dados inventados."
            )
        return await self._research_local_leads(message)

    async def _consume_local_lead_location(self, message: str) -> str | None:
        if self._pending_local_lead_research is None:
            return None
        normalized_message = message.strip()
        has_location = bool(
            re.search(r"\b\d{5}-?\d{3}\b", normalized_message)
            or re.search(
                r"\b[A-Za-zÀ-ÖØ-öø-ÿ ]{2,40}\s*[-,/]+\s*[A-Za-z]{2}\b",
                normalized_message,
            )
            or re.fullmatch(
                r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ -][A-Za-zÀ-ÖØ-öø-ÿ]+){1,4}",
                normalized_message,
            )
        )
        if not has_location:
            return None
        original = self._pending_local_lead_research
        self._pending_local_lead_research = None
        location_hint = normalized_message
        if not re.search(
            r"\b(?:rs|rio grande do sul)\b", self._normalized(normalized_message)
        ) and re.fullmatch(
            r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ -][A-Za-zÀ-ÖØ-öø-ÿ]+){1,4}", normalized_message
        ):
            location_hint = f"{normalized_message}, RS"
        return await self._research_local_leads(
            f"{original}\nPonto central informado: {location_hint}"
        )

    async def _research_local_leads(self, message: str) -> str:
        count_match = re.search(
            r"\b(\d{1,3})\s+(?:profissionais?|dentistas?|leads?|cl\w*nica(?:s)?|lojas?|empresas?|"
            r"neg[oó]cios?|servi[cç]os?|consult[oó]rios?|especialistas?)\b",
            message,
            re.IGNORECASE,
        )
        statewide_rs = self._is_statewide_rs_request(message)
        requested_count = min(
            int(count_match.group(1)) if count_match else (50 if statewide_rs else 25), 50
        )
        point_match = re.search(
            r"(?:ponto central informado|cidade|local informado|local|ponto central):\s*(.+?)(?:[.!?]|$)",
            message,
            re.IGNORECASE,
        )
        if point_match:
            location = self._clean_location(point_match.group(1))
        else:
            location_candidates: list[str] = []
            city_pattern = (
                r"(?:[A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'\-.]+(?:\s+[A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'\-.]+){0,3})"
                r"(?:\s*,\s*(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO))?"
            )
            for match in re.finditer(rf"\b(?:em|na|no)\s+({city_pattern})\b", message, re.IGNORECASE):
                candidate = self._clean_location(match.group(1))
                if candidate:
                    location_candidates.append(candidate)
            location = location_candidates[-1] if location_candidates else ""
        if not location:
            city_match = re.fullmatch(
                r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[ -][A-Za-zÀ-ÖØ-öø-ÿ]+){0,4}(?:\s*,\s*(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO))?",
                message.strip(),
                re.IGNORECASE,
            )
            if city_match:
                location = self._clean_location(message.strip())
        if statewide_rs:
            location = "Rio Grande do Sul"
        query_target = self._extract_business_target(message, location)
        tool_names_method = getattr(self.tools, "names", None)
        tool_names = set(tool_names_method()) if callable(tool_names_method) else set()
        if location and "google_maps_business_search" in tool_names:
            locations = (
                [
                    "Porto Alegre, RS", "Canoas, RS", "Caxias do Sul, RS", "Pelotas, RS",
                    "Santa Maria, RS", "Gravataí, RS", "Viamão, RS", "Novo Hamburgo, RS",
                    "São Leopoldo, RS", "Rio Grande, RS", "Alvorada, RS", "Passo Fundo, RS",
                    "Sapucaia do Sul, RS", "Uruguaiana, RS", "Santa Cruz do Sul, RS",
                    "Cachoeirinha, RS", "Bagé, RS", "Bento Gonçalves, RS", "Erechim, RS",
                    "Guaíba, RS",
                ]
                if statewide_rs
                else [location]
            )
            businesses: list[Any] = []
            seen_maps: set[tuple[str, str]] = set()
            per_location = 10 if statewide_rs else min(requested_count * 2, 50)
            for search_location in locations:
                query = f"{query_target} em {search_location}" if query_target else f"dentistas em {search_location}"
                maps_result = await self.tools.execute(
                    "google_maps_business_search",
                    query=query,
                    limit=per_location,
                )
                self.context.remember_action("google_maps_business_search", maps_result.success)
                found = maps_result.metadata.get("businesses", []) if maps_result.success else []
                for item in found:
                    if not isinstance(item, dict):
                        continue
                    key = (
                        self._normalized(str(item.get("name", ""))),
                        "".join(c for c in str(item.get("phone", "")) if c.isdigit()),
                    )
                    if key in seen_maps:
                        continue
                    seen_maps.add(key)
                    businesses.append(item)
                eligible_count = sum(
                    1
                    for item in businesses
                    if str(item.get("whatsapp", "")).strip()
                    and not str(item.get("website", "")).strip()
                )
                if eligible_count >= requested_count:
                    break
            qualified = [
                item
                for item in businesses
                if isinstance(item, dict)
                and str(item.get("whatsapp", "")).strip()
                and not str(item.get("website", "")).strip()
            ]
            ranked = []
            scoring = LeadScoringPolicy()
            commercial_profile = self.lead_store.profile() if self.lead_store is not None else None
            for item in qualified:
                normalized_item = dict(item)
                normalized_item["niche"] = query_target or ""
                if commercial_profile is not None:
                    evaluated = scoring.evaluate(normalized_item, commercial_profile)
                    normalized_item["_score"] = evaluated.total
                    normalized_item["_score_explanation"] = evaluated.explanation
                    normalized_item["_qualification"] = evaluated.qualification
                    normalized_item["_score_dimensions"] = evaluated.as_dict()
                else:
                    normalized_item["_score"] = self._lead_quality_score(normalized_item)
                    normalized_item["_score_explanation"] = "Score de verificabilidade da ficha"
                    normalized_item["_qualification"] = "Lead verificável para revisão comercial"
                normalized_item["_priority"] = self._lead_priority_label(normalized_item["_score"])
                ranked.append(normalized_item)
            ranked = sorted(ranked, key=lambda item: item["_score"], reverse=True)[:requested_count]
            if ranked:
                rows = []
                for index, item in enumerate(ranked, start=1):
                    rows.append(
                        {
                            "rank": index,
                            "name": str(item.get("name", "")).strip() or "Sem nome",
                            "address": str(item.get("address", "")).strip() or "Sem endereço",
                            "whatsapp": self._clean_phone(str(item.get("whatsapp", ""))),
                            "website": "Sem site",
                            "score": item["_score"],
                            "priority": item["_priority"],
                            "maps_url": str(item.get("maps_url", "")).strip(),
                            "score_explanation": str(item.get("_score_explanation", "")),
                            "qualification": str(item.get("_qualification", "")),
                            "rating": float(item.get("rating", 0) or 0),
                            "review_count": int(item.get("review_count", 0) or 0),
                            "score_dimensions": item.get("_score_dimensions", {}),
                        }
                    )
                if self.lead_store is not None:
                    for row in rows:
                        dimensions = row.get("score_dimensions", {})
                        if not isinstance(dimensions, dict):
                            dimensions = {}
                        lead_id = self.lead_store.upsert(
                            company=str(row["name"]), niche=query_target or "Não informado",
                            location=str(row["address"]), whatsapp=str(row["whatsapp"]),
                            source_url=str(row["maps_url"]), score=int(row["score"]),
                            qualification=str(row["qualification"]),
                            score_explanation=str(row["score_explanation"]),
                            dossier=(
                                f"{row['name']} — {query_target or 'negócio local'} em "
                                f"{row['address']}. WhatsApp confirmado e site não encontrado "
                                "na ficha verificada do Google Maps. "
                                f"Reputação observada: {row['rating']:.1f} em "
                                f"{row['review_count']} avaliações."
                            ),
                            rating=float(row["rating"]), review_count=int(row["review_count"]),
                            confidence_score=int(dimensions.get("confidence", 0)),
                            fit_score=int(dimensions.get("fit", 0)),
                            opportunity_score=int(dimensions.get("opportunity", 0)),
                            engagement_score=int(dimensions.get("engagement", 0)),
                            score_model_version=str(dimensions.get("model_version", "")),
                        )
                        source_url = str(row["maps_url"])
                        for field_name, value, confidence in (
                            ("company", str(row["name"]), 0.9),
                            ("address", str(row["address"]), 0.85),
                            ("whatsapp", str(row["whatsapp"]), 0.85),
                            ("rating", str(row["rating"]), 0.8),
                            ("review_count", str(row["review_count"]), 0.8),
                            ("website_status", "NOT_LISTED_ON_MAPS", 0.75),
                        ):
                            self.lead_store.add_observation(
                                lead_id, field_name=field_name, value=value,
                                source_url=source_url, source_type="google_maps",
                                status="OBSERVED", confidence=confidence,
                            )
                        saved_lead = next(
                            (
                                candidate
                                for candidate in self.lead_store.list(limit=1000)
                                if candidate.id == lead_id
                            ),
                            None,
                        )
                        if saved_lead is not None:
                            intelligence = CommercialIntelligenceService().generate(
                                saved_lead,
                                commercial_profile,
                                self.lead_store.observations(lead_id),
                            )
                            payload = intelligence.as_dict()
                            score_data = row.get("score_dimensions", {})
                            if not isinstance(score_data, dict):
                                score_data = {}
                            qualification = payload["qualification"]
                            status_map = {
                                "sql": "sql_pronto", "nurture": "nutricao",
                                "research": "precisa_pesquisar",
                                "disqualified": "desqualificado",
                            }
                            qualification["status"] = status_map.get(
                                str(qualification.get("status", "research")),
                                "precisa_pesquisar",
                            )
                            if payload["validation_errors"]:
                                qualification["status"] = "precisa_pesquisar"
                            qualification["readiness_score"] = int(
                                score_data.get("readiness", 0) or 0
                            )
                            qualification["missing_information"] = list(
                                score_data.get("missing_information", ())
                            )
                            meeting = payload["meeting"]
                            proposal = payload["proposal"]
                            self.lead_store.update_sales_intelligence(
                                lead_id,
                                qualification=qualification,
                                dossier={
                                    "executive_summary": qualification["executive_summary"],
                                    "verified_facts": qualification["facts"],
                                    "hypotheses": [
                                        claim["value"] for claim in qualification["inferences"]
                                    ],
                                    "decision_makers": [
                                        claim for claim in qualification["facts"]
                                        if claim["field"] == "decision_maker"
                                    ],
                                    "triggers": [
                                        claim for claim in qualification["facts"]
                                        if claim["field"] in {"timing", "urgency"}
                                    ],
                                    "risks": list(qualification["disqualifiers"]),
                                    "likely_objections": list(meeting["likely_objections"]),
                                    "discovery_questions": list(meeting["discovery_questions"]),
                                    "meeting_brief": (
                                        f"{meeting['objective']}\n{meeting['opening']}"
                                    ),
                                },
                                artifacts={
                                    "opening_message": payload["outreach"]["body"],
                                    "follow_ups": [],
                                    "call_script": "\n".join(
                                        [meeting["opening"], *meeting["discovery_questions"]]
                                    ),
                                    "proposal": proposal,
                                    "contract_draft": payload["contract"],
                                    "approval_required": True,
                                    "grounded": not bool(payload["validation_errors"]),
                                    "validation_errors": list(payload["validation_errors"]),
                                },
                            )
                table_rows = [
                    "| Rank | Nome | Endereço | WhatsApp | Site | Score | Prioridade |",
                    "|---:|---|---|---|---|---:|---|",
                ]
                table_rows.extend(
                    "| {rank} | {name} | {address} | {whatsapp} | {website} | {score} | {priority} |".format(
                        rank=row["rank"],
                        name=str(row["name"]).replace("|", "\\|"),
                        address=str(row["address"]).replace("|", "\\|"),
                        whatsapp=str(row["whatsapp"]).replace("|", "\\|"),
                        website=str(row["website"]).replace("|", "\\|"),
                        score=row["score"],
                        priority=str(row["priority"]).replace("|", "\\|"),
                    )
                    for row in rows
                )
                csv_buffer = io.StringIO(newline="")
                csv_writer = csv.writer(csv_buffer)
                csv_writer.writerow(
                    ("rank", "nome", "endereco", "whatsapp", "site", "score", "prioridade")
                )
                csv_writer.writerows(
                    (row["rank"], row["name"], row["address"], row["whatsapp"],
                     row["website"], row["score"], row["priority"])
                    for row in rows
                )
                csv_lines = csv_buffer.getvalue().strip().splitlines()
                coverage = (
                    f"A busca percorreu {len(locations)} polos municipais do RS em lotes. "
                    if statewide_rs
                    else ""
                )
                return (
                    f"Encontrei {len(ranked)} candidato(s) priorizado(s), com contato observado e em qualificação comercial. "
                    + coverage
                    + "\n\n"
                    + "\n".join(table_rows)
                    + "\n\nCSV pronto para exportação:\n"
                    + "\n".join(csv_lines)
                    + "\n\nA ausência de site descreve as fichas verificadas nesta busca; não é prova absoluta de inexistência em toda a internet."
                )
            return (
                "Li as fichas individuais do Google Maps, mas nenhuma passou simultaneamente "
                "pelos filtros de WhatsApp validado e ausência do botão de site. Nenhum contato "
                "incerto foi incluído."
            )
        fallback_location = location or "Brasil"
        business_label = query_target or "profissionais"
        queries = (
            f"{business_label} em {fallback_location} telefone WhatsApp",
            f"Google Maps {business_label} em {fallback_location}",
            f"{business_label} em {fallback_location} WhatsApp",
        )
        evidence: list[dict[str, str]] = []
        for query in queries:
            url = f"https://www.google.com/search?q={quote_plus(query)}"
            result = await self.tools.execute("browser_navigate", url=url)
            self.context.remember_action("browser_navigate", result.success)
            page_text = str(result.metadata.get("text", "")) if result.success else ""
            if len(page_text.strip()) >= 80:
                evidence.append({"query": query, "text": page_text[:20_000]})
        if not evidence:
            return (
                "Não consegui ler resultados suficientes para montar uma lista verificável. "
                "A pesquisa permaneceu em segundo plano e nenhuma janela foi aberta. "
                "Não vou afirmar que profissionais não possuem site nem inventar telefones sem evidência."
            )
        discovery_prompt = {
            "role": "extrator_de_candidatos_de_prospeccao",
            "request": message,
            "requested_count": requested_count,
            "search_evidence": evidence,
            "instructions": (
                "Extraia candidatos reais para verificação individual. Responda somente JSON válido "
                "no formato {\"candidates\":[{\"name\":\"...\",\"location\":\"...\","
                "\"whatsapp\":\"...\",\"source\":\"...\"}]}. Inclua apenas candidatos com nome "
                "e telefone/WhatsApp presentes literalmente nas evidências. Não conclua ainda se "
                "possuem site. Remova duplicatas e nunca invente campos."
            ),
        }
        try:
            raw_candidates = await self.llm.generate(
                json.dumps(discovery_prompt, ensure_ascii=False)
            )
            candidate_payload = json.loads(self._extract_json_object(raw_candidates))
        except (json.JSONDecodeError, TypeError, ValueError):
            return (
                "Encontrei resultados, mas não consegui extrair contatos verificáveis deles. "
                "Nenhum contato foi incluído."
            )
        candidates = candidate_payload.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        verified_evidence: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in candidates[:requested_count * 2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            whatsapp = str(item.get("whatsapp", "")).strip()
            location = str(item.get("location", "")).strip()
            digits = "".join(character for character in whatsapp if character.isdigit())
            key = (self._normalized(name), digits)
            if not name or len(digits) < 10 or key in seen:
                continue
            seen.add(key)
            verification_query = f'"{name}" {location} site oficial telefone WhatsApp'
            verification = await self.tools.execute(
                "browser_navigate",
                url=f"https://www.google.com/search?q={quote_plus(verification_query)}",
            )
            self.context.remember_action("browser_navigate", verification.success)
            verification_text = (
                str(verification.metadata.get("text", "")) if verification.success else ""
            )
            if len(verification_text.strip()) < 80:
                continue
            verified_evidence.append(
                {
                    "candidate": item,
                    "verification_query": verification_query,
                    "verification_text": verification_text[:12_000],
                }
            )
        if not verified_evidence:
            return (
                "Não encontrei candidatos que tivessem simultaneamente WhatsApp verificável e "
                "evidência suficiente para conferir a existência de site. Nenhum contato foi incluído."
            )
        prompt = {
            "role": "pesquisador_de_prospeccao_local",
            "request": message,
            "requested_count": requested_count,
            "individually_checked_candidates": verified_evidence,
            "instructions": (
                "Produza em português uma tabela usando exclusivamente individually_checked_candidates. "
                "A saída deve conter SOMENTE profissionais que satisfaçam as duas condições: (1) o "
                "WhatsApp aparece nas evidências e corresponde ao candidato; (2) a busca individual "
                "não mostra domínio oficial/site próprio. Se aparecer qualquer possível domínio oficial, "
                "exclua o candidato, mesmo que também haja Instagram, Facebook, Doctoralia ou perfil do "
                "Google. Exclua também todo caso ambíguo, sem telefone confirmável ou cuja busca falhou. "
                "Inclua nome, cidade/bairro, WhatsApp e fonte. Remova duplicatas, não invente campos e "
                "informe quantos passaram pelo filtro. Descreva o resultado como 'nenhum site próprio "
                "encontrado nas buscas realizadas', não como prova absoluta de inexistência. Não envie "
                "mensagens; apenas prepare a lista."
            ),
        }
        try:
            return await self.llm.generate(json.dumps(prompt, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - provider boundary has a truthful fallback
            return (
                "Consegui coletar resultados, mas a organização da lista falhou. "
                "Não vou apresentar contatos sem a etapa de validação."
            )

    @staticmethod
    def _clean_phone(value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 10:
            if len(digits) == 11 and digits.startswith("55"):
                digits = digits[2:]
            return f"{digits[:2]} {digits[2:7]}-{digits[7:]}"
        return value.strip()

    @staticmethod
    def _lead_quality_score(item: dict[str, Any]) -> int:
        score = 0
        name = str(item.get("name", "")).strip()
        if name:
            score += 15
        address = str(item.get("address", "")).strip()
        if address:
            score += 20
        whatsapp = str(item.get("whatsapp", "")).strip()
        if whatsapp:
            score += 30
        website = str(item.get("website", "")).strip()
        if not website:
            score += 25
        maps_url = str(item.get("maps_url", "")).strip()
        if maps_url:
            score += 10
        return score

    @staticmethod
    def _lead_priority_label(score: int) -> str:
        if score >= 80:
            return "Alta"
        if score >= 60:
            return "Média"
        return "Baixa"

    @staticmethod
    def _clean_location(value: str) -> str:
        cleaned = value.strip(" ,.;:-/")
        cleaned = re.sub(
            r"(?:,\s*)?(?:num\s+raio|raio\s+de|traga|busque|pesquise|procure|ache|encontre|me\s+traga|para|com|que|somente|apenas)\b.*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+\d{1,3}\s*(?:km|k?m)\b.*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(?i)\s*[.,;]\s*(?:traga|busque|pesquise|procure|ache|encontre|me\s+traga|para|com|que)\b.*$", "", cleaned)
        return cleaned.strip(" ,.;:-/")

    @classmethod
    def _extract_business_target(cls, message: str, location: str) -> str:
        trimmed_message = message.split("\nPonto central informado:", 1)[0].strip()
        normalized = re.sub(r"(?i)^\s*kiara\s*[,;:\-]*\s*", "", trimmed_message)
        normalized = re.sub(
            r"(?i)^\s*(?:busque|procure|pesquise|ache|encontre|traga|lista|me\s+traga|quero|preciso\s+de|faça|faca)\s+",
            "",
            normalized,
        )
        normalized = re.sub(r"(?i)^\s*(?:no\s+)?google\s+", "", normalized)
        normalized = re.sub(r"(?i)^\s*(?:\d+\s+)+", "", normalized)
        normalized = normalized.strip()

        if not normalized:
            return "dentistas"

        for marker in (" em ", " na ", " no ", " sem ", " com ", " para ", " que "):
            if marker in normalized.lower():
                candidate = normalized.split(marker, 1)[0].strip(" ,.;:-/")
                candidate = re.sub(
                    r"(?i)\s+(?:site|dominio|domínio|whatsapp|telefone|contato|google|sem|com|para|que|e)\b.*$",
                    "",
                    candidate,
                )
                candidate = candidate.strip(" ,.;:-/")
                if candidate:
                    return candidate

        candidate = normalized.strip(" ,.;:-/")
        candidate = re.sub(
            r"(?i)\s+(?:site|dominio|domínio|whatsapp|telefone|contato|google|sem|com|para|que|e)\b.*$",
            "",
            candidate,
        )
        return candidate.strip(" ,.;:-/") or "dentistas"

    @staticmethod
    def _extract_json_object(value: str) -> str:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Resposta não contém objeto JSON.")
        return value[start : end + 1]

    @classmethod
    def _is_statewide_rs_request(cls, message: str) -> bool:
        normalized = cls._normalized(message)
        mentions_rs = bool(re.search(r"\b(?:rio grande do sul|rs)\b", normalized))
        statewide_scope = bool(
            re.search(
                r"\b(?:todas as cidades|todo o estado|estado inteiro|todo o rio grande do sul|"
                r"em todo o rio grande do sul|rio grande do sul inteiro)\b",
                normalized,
            )
        )
        return mentions_rs and statewide_scope

    async def _realtime_research(self, _intent: Intent, message: str) -> str:
        query = message.strip()
        if re.search(r"\b(?:o\s+)?inter\b", self._normalized(query)):
            query = re.sub(
                r"\b(?:o\s+)?inter\b",
                "Sport Club Internacional",
                query,
                flags=re.IGNORECASE,
            )
        search_url = f"https://www.google.com/search?q={quote_plus(query)}"
        result = await self.tools.execute("browser_navigate", url=search_url)
        self.context.remember_action("browser_navigate", result.success)
        evidence = str(result.metadata.get("text", "")) if result.success else ""
        blocked = (
            not result.success
            or len(evidence.strip()) < 120
            or "google/sorry" in str(result.output).casefold()
        )
        if blocked:
            return (
                "Não consegui ler resultados atuais de forma confiável agora. "
                "A consulta foi encerrada em segundo plano, sem abrir o navegador. "
                "Não vou inventar escalações, jogos, odds ou palpites sem dados verificáveis."
            )
        current = datetime.now().astimezone().isoformat(timespec="seconds")
        betting = bool(
            re.search(
                r"\b(?:aposta|apostas|palpite|palpites|odd|odds)\b",
                query,
                re.IGNORECASE,
            )
        )
        prompt = {
            "role": "pesquisador_de_informacoes_atuais",
            "question": message,
            "search_query": query,
            "checked_at": current,
            "search_page_text": evidence[:30_000],
            "instructions": (
                "Responda em português usando somente fatos sustentados pelo texto pesquisado. "
                "Diferencie escalação confirmada de provável e diga quando algo não estiver "
                "confirmado. Não invente nomes, horários, resultados, fontes ou odds. Informe "
                "que os dados foram consultados no horário checked_at."
                + (
                    " Para apostas, faça apenas análise informativa: apresente riscos, critérios "
                    "e incertezas, não prometa lucro, não use linguagem de aposta garantida e "
                    "recomende limite de perda responsável."
                    if betting
                    else ""
                )
            ),
        }
        try:
            return await self.llm.generate(json.dumps(prompt, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - provider boundary has independent fallback
            return (
                "Consegui consultar os resultados atuais, mas a síntese por IA falhou. "
                "A página pesquisada ficou aberta para você; tente novamente em instantes."
            )

    async def _work_calendar(self, intent: Intent, message: str) -> str:
        normalized = self._normalized(message)
        tool_names_method = getattr(self.tools, "names", None)
        tool_names = set(tool_names_method()) if callable(tool_names_method) else set()
        asks_teams = "teams" in normalized or "reuniao" in normalized
        if "read_calendar" in tool_names:
            return await self._run_tool("read_calendar", limit=50)
        if asks_teams:
            return (
                "Não consigo consultar suas reuniões do Teams porque a conta Microsoft 365 "
                "ainda não está conectada à Kiara. A integração Microsoft Graph está "
                "desativada; não vou fingir que li o calendário nem depender do que estiver "
                "visível na tela."
            )
        if "list_personal_events" not in tool_names:
            return "A agenda ainda não está disponível nesta instalação da Kiara."
        now = datetime.now().astimezone()
        parameters: dict[str, str] = {"from_at": now.isoformat(timespec="minutes")}
        if self._normalized(str(intent.parameters.get("period", ""))) == "semana":
            days_until_sunday = 6 - now.weekday()
            end = (now + timedelta(days=days_until_sunday)).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            parameters["to_at"] = end.isoformat(timespec="minutes")
        result = await self._run_tool("list_personal_events", **parameters)
        return "Agenda local da Kiara (Microsoft/Teams não conectado):\n" + result

    async def _open_website(self, intent: Intent, _message: str) -> str:
        target = str(intent.parameters["target"]).strip()
        compact = re.sub(r"\s+", "", target)
        if re.fullmatch(
            r"(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?(?:/\S*)?",
            compact,
            re.IGNORECASE,
        ):
            return await self._run_tool("browser_navigate", url=f"https://{compact}")
        return await self._run_tool(
            "open_url",
            url=f"https://www.google.com/search?q={quote_plus(target)}",
        )

    async def _browser_fill(self, intent: Intent, _message: str) -> str:
        return await self._run_tool(
            "browser_fill",
            label=intent.parameters["label"],
            value=intent.parameters["text"],
        )

    async def _browser_click(self, intent: Intent, _message: str) -> str:
        roles = {
            "botao": "button",
            "botão": "button",
            "link": "link",
            "caixa de selecao": "checkbox",
            "caixa de seleção": "checkbox",
        }
        role = roles.get(self._normalized(str(intent.parameters["role"])), "button")
        return await self._run_tool("browser_click", role=role, name=intent.parameters["name"])

    async def _browser_read(self, _intent: Intent, _message: str) -> str:
        return await self._run_tool("browser_read")

    async def _social_message(self, intent: Intent, _message: str) -> str:
        return await self._run_tool(
            "send_social_message",
            platform=intent.parameters["platform"],
            recipient=intent.parameters["recipient"],
            text=intent.parameters["text"],
        )

    async def _powershell(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("execute_powershell", command=intent.parameters["command"])

    async def _network_ping(self, intent: Intent, _message: str) -> str:
        return await self._run_tool(
            "network_ping",
            target=intent.parameters["target"],
            resolve_name=bool(intent.parameters.get("resolve_name")),
        )

    async def _open_url(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("open_url", url=intent.parameters["url"])

    async def _sync_obsidian(self, _intent: Intent, _message: str) -> str:
        return await self._run_tool("sync_obsidian")

    async def _search_obsidian(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("search_obsidian", query=intent.parameters["query"])

    async def _open_obsidian_note(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("open_obsidian_note", note=intent.parameters["note"])

    async def _save_obsidian_note(self, intent: Intent, _message: str) -> str:
        content = intent.parameters["content"]
        title = content.splitlines()[0][:80]
        return await self._run_tool("save_obsidian_note", title=title, content=content)

    async def _current_datetime(self, _intent: Intent, message: str) -> str:
        current = datetime.now().astimezone()
        weekdays = (
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        )
        months = (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        )
        date_text = (
            f"Hoje é {weekdays[current.weekday()]}, {current.day} de "
            f"{months[current.month - 1]} de {current.year}."
        )
        if re.search(r"\b(hora|horas|horário|horario)\b", message, re.IGNORECASE):
            return f"{date_text} Agora são {current:%H:%M} ({current.tzname() or 'horário local'})."
        return date_text

    async def _helpdesk_diagnostic(self, intent: Intent, message: str) -> str:
        category = self._diagnostic_category(intent.parameters.get("category"))
        result = await self.tools.execute("system_diagnostics", category=category)
        self.context.remember_action("system_diagnostics", result.success)
        if not result.success:
            return f"Não consegui coletar o diagnóstico: {result.error}"
        snapshot = result.metadata.get("snapshot", {})
        if not isinstance(snapshot, dict):
            return "O diagnóstico terminou, mas não produziu evidências estruturadas."
        self._diagnostic_baselines[category] = snapshot
        diagnostic_context = self._conversation_context(message)
        diagnostic_context["diagnostic_snapshot"] = {
            "category": category,
            "data": snapshot,
            "trust": "verified_read_only_tool_output",
        }
        return await self.agent_router.respond(f"Helpdesk: {message}", diagnostic_context)

    async def _helpdesk_verify(self, intent: Intent, message: str) -> str:
        category = self._diagnostic_category(intent.parameters.get("category"))
        if category not in self._diagnostic_baselines:
            if len(self._diagnostic_baselines) == 1:
                category = next(iter(self._diagnostic_baselines))
            else:
                return (
                    "Ainda não tenho um diagnóstico inicial comparável. Peça primeiro: "
                    "'Kiara, faça um diagnóstico do computador'."
                )
        result = await self.tools.execute("system_diagnostics", category=category)
        self.context.remember_action("system_diagnostics_verify", result.success)
        if not result.success:
            return f"Não consegui repetir o diagnóstico: {result.error}"
        current = result.metadata.get("snapshot", {})
        if not isinstance(current, dict):
            return "A verificação não produziu evidências estruturadas."
        comparison = compare_snapshots(
            self._diagnostic_baselines[category], current, category=category
        )
        diagnostic_context = self._conversation_context(message)
        diagnostic_context["diagnostic_comparison"] = {
            "category": category,
            **comparison,
            "trust": "verified_read_only_tool_output",
        }
        return await self.agent_router.respond(f"Helpdesk: {message}", diagnostic_context)

    @staticmethod
    def _diagnostic_category(raw: object) -> str:
        text = str(raw or "").casefold()
        aliases = {
            "driver": "drivers",
            "drivers": "drivers",
            "rede": "network",
            "network": "network",
            "internet": "network",
            "bateria": "battery",
            "battery": "battery",
            "evento": "events",
            "eventos": "events",
            "logs": "events",
        }
        return aliases.get(text, "overview")

    async def _screen_context(self, _intent: Intent, message: str) -> str:
        screen = self.context.screen()
        if self.perception is None:
            return self._format_desktop_assistant_response(
                message,
                screen,
                "A captura visual segura não está disponível nesta sessão. Só consigo confirmar o aplicativo e a janela ativa.",
            )

        identity = (screen.active_process, screen.active_application, screen.window_title)
        latest_capture = getattr(self.perception, "latest_capture", None)
        if latest_capture is not None:
            capture = await latest_capture(expected_identity=identity, max_age_seconds=2.0)
        else:
            capture = await self.perception.capture_active_window(include_text=True)
        if capture is None:
            capture = await self.perception.capture_virtual_desktop()

        self.context.remember_action("analyze_screen_ephemeral", capture is not None)
        if capture is None:
            return self._format_desktop_assistant_response(
                message,
                screen,
                "Não consegui capturar a tela ativa para análise visual.",
            )

        if "vision" not in self.llm.capabilities:
            return self._format_desktop_assistant_response(
                message,
                screen,
                (
                    f"Janela ativa: {screen.window_title or 'sem título'}. "
                    f"Aplicativo: {screen.active_application or 'não identificado'}. "
                    "O modelo visual local ainda não está disponível; consigo apenas confirmar a janela e o contexto do sistema."
                ),
            )

        visible_text = capture.visible_text.strip() if capture.visible_text else ""
        prompt = screen_analysis_prompt(
            application=screen.active_application,
            window_title=screen.window_title,
        )
        try:
            raw_analysis = await self.llm.vision_bytes(prompt, capture.png)
            if not raw_analysis.strip():
                raise RuntimeError("resposta visual vazia")
            analysis = parse_screen_analysis(
                raw_analysis, application=screen.active_application
            )
            if not screen_analysis_is_consistent(
                analysis,
                application=screen.active_application,
                window_title=screen.window_title,
            ):
                accessible = (
                    f" Texto acessível observado: {visible_text[:1200]}"
                    if visible_text
                    else " Nenhum texto acessível confiável foi detectado."
                )
                return self._format_desktop_assistant_response(
                    message,
                    screen,
                    "Rejeitei a descrição do modelo visual porque ela contradiz a janela "
                    "ativa; não vou apresentar essa descrição como fato." + accessible,
                )
            return self._format_desktop_assistant_response(
                message, screen, analysis.summary()
            )
        except Exception as exc:  # noqa: BLE001 - provider failure becomes an honest response
            accessible = (
                f" Texto acessível observado: {visible_text[:1200]}"
                if visible_text
                else " Nenhum texto acessível foi detectado."
            )
            return self._format_desktop_assistant_response(
                message,
                screen,
                f"Capturei a tela, mas a análise visual local falhou ({type(exc).__name__})."
                + accessible,
            )

    async def _screen_capability(self, _intent: Intent, _message: str) -> str:
        screen = self.context.screen()
        observed = ""
        if screen.active_application or screen.window_title:
            observed = (
                f" Neste momento, consigo identificar a janela ativa como "
                f"{screen.active_application or 'aplicativo não identificado'}"
                f" — {screen.window_title or 'sem título'}."
            )
        if "vision" in self.llm.capabilities:
            return (
                "Sim. Quando você pedir, consigo capturar e analisar visualmente o desktop "
                "autorizado. Os pixels são usados apenas nessa resposta e não ficam armazenados."
                f"{observed}"
            )
        return (
            "Consigo identificar a janela ativa e fazer uma captura temporária com sua "
            "autorização. O modelo atual não analisa os pixels da imagem; portanto, não vou "
            f"afirmar que vi conteúdo visual que não consegui verificar.{observed}"
        )

    async def _conversation(self, _intent: Intent, message: str) -> str:
        context = self._conversation_context(message)
        if self._screen_related(message):
            context.update(await self._screen_conversation_context(message))
        return await self.agent_router.respond(message, context)

    def _conversation_context(self, message: str) -> dict[str, Any]:
        context = self.context.assemble(message)
        tool_names = set(self.tools.names()) if hasattr(self.tools, "names") else set()
        context["assistant_capabilities"] = {
            "specialty": "SDR de prospecção e qualificação de leads",
            "lead_pipeline": self.lead_store is not None,
            "identify_active_window": self.perception is not None,
            "analyze_screen_pixels_locally": (
                self.perception is not None and "vision" in self.llm.capabilities
            ),
            "system_diagnostics_read_only": "system_diagnostics" in tool_names,
            "execute_actions_with_confirmation": bool(tool_names),
            "current_date_time_from_system_clock": True,
        }
        if self.lead_store is not None:
            profile = self.lead_store.profile()
            context["commercial_profile"] = {
                "business_name": profile.business_name,
                "service": profile.service,
                "target_niches": profile.target_niches,
                "target_locations": profile.target_locations,
                "ideal_customer": profile.ideal_customer,
                "value_proposition": profile.value_proposition,
                "average_ticket": profile.average_ticket,
                "daily_contact_limit": profile.daily_contact_limit,
            }
        return context

    async def _complex_task(self, _intent: Intent, message: str) -> str:
        if self.task_planner is None:
            return "O planejamento com execução está desativado por segurança."
        try:
            return await self.task_planner.run(message, self.context.assemble(message))
        except PlanRejected as exc:
            return f"Não executei: o plano não passou pelas regras de segurança ({exc})."

    async def _resume_goal(self, intent: Intent, _message: str) -> str:
        if self.task_planner is None:
            return "O planejamento persistente está desativado."
        identifier = int(intent.parameters["goal_id"])
        try:
            return await self.task_planner.resume_goal(identifier)
        except KeyError:
            return f"Não encontrei o plano {identifier}."
        except (PermissionError, ValueError) as exc:
            return f"Não foi possível retomar o plano {identifier}: {exc}."

    async def _build_business_site(self, intent: Intent, _message: str) -> str:
        information = str(intent.parameters["business_info"]).strip()
        site_name = information.split(",", 1)[0].strip()[:100]
        self._pending_site_brief = (site_name, information)
        return (
            "Vou usar o que estiver visível como referência visual. Posso capturar a janela "
            "atual agora? Responda ‘use a tela’. Se preferir uma foto, coloque-a em "
            "data/site-references e responda ‘use a foto nome-do-arquivo.png’."
        )

    async def _list_mcp_servers(self, _intent: Intent, _message: str) -> str:
        return await self._run_tool("list_mcp_servers")

    async def _discover_mcp_tools(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("discover_mcp_tools", server=intent.parameters["server"])

    async def _call_mcp_tool(self, intent: Intent, _message: str) -> str:
        try:
            arguments = json.loads(str(intent.parameters["arguments"]))
        except json.JSONDecodeError:
            return "Os argumentos da ferramenta MCP não formam um objeto JSON válido."
        if not isinstance(arguments, dict):
            return "Os argumentos MCP precisam ser um objeto JSON."
        return await self._run_tool(
            "call_mcp_tool",
            server=intent.parameters["server"],
            tool=intent.parameters["tool"],
            arguments=arguments,
        )

    async def _add_personal_task(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("add_personal_task", title=intent.parameters["title"])

    async def _list_personal_tasks(self, _intent: Intent, _message: str) -> str:
        return await self._run_tool("list_personal_tasks")

    async def _complete_personal_task(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("complete_personal_task", task_id=intent.parameters["task_id"])

    async def _add_personal_event(self, intent: Intent, _message: str) -> str:
        timezone = ZoneInfo("America/Sao_Paulo")
        now = datetime.now(timezone)
        raw_date = self._normalized(str(intent.parameters["date"]))
        try:
            if raw_date == "hoje":
                day = now.date()
            elif raw_date == "amanha":
                day = (now + timedelta(days=1)).date()
            else:
                try:
                    day, month, year = (int(part) for part in raw_date.split("/"))
                    day = date(year, month, day)
                except ValueError:
                    year, month, day = (int(part) for part in raw_date.split())
                    day = date(year, month, day)
            minute = int(intent.parameters.get("minute", 0))
            start = datetime.combine(
                day,
                datetime.min.time().replace(hour=int(intent.parameters["hour"]), minute=minute),
                timezone,
            )
        except (TypeError, ValueError):
            return "Data ou horário inválido. Use, por exemplo: amanhã às 14:30."
        end = start + timedelta(hours=1)
        return await self._run_tool(
            "add_personal_event",
            title=intent.parameters["title"],
            start_at=start.isoformat(timespec="minutes"),
            end_at=end.isoformat(timespec="minutes"),
        )

    async def _list_personal_events(self, _intent: Intent, _message: str) -> str:
        return await self._run_tool(
            "list_personal_events",
            from_at=datetime.now().astimezone().isoformat(timespec="minutes"),
        )

    async def _search_personal_files(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("search_personal_files", query=intent.parameters["query"])

    async def _draft_email(self, intent: Intent, _message: str) -> str:
        return await self._run_tool(
            "draft_email",
            to=intent.parameters["to"],
            subject=intent.parameters["subject"],
            body=intent.parameters["body"],
        )

    async def _consume_site_source(self, message: str) -> str | None:
        if self._pending_site_brief is None:
            return None
        normalized = self._normalized(message)
        if re.fullmatch(r"(?:nao|cancelar|cancele)", normalized):
            self._pending_site_brief = None
            return "Criação do site cancelada; nenhuma captura foi feita."
        photo = re.search(
            r"(?:use|usar)\s+(?:a\s+)?(?:foto|imagem)\s+(.+)$", message, re.IGNORECASE
        )
        site_name, information = self._pending_site_brief
        if photo is not None:
            self._pending_site_brief = None
            return await self._run_tool(
                "generate_business_site",
                site_name=site_name,
                business_info=information,
                reference_image=photo.group(1).strip().rstrip(".!?"),
            )
        if re.fullmatch(
            r"(?:sim|pode|pode sim|use a tela|use essa tela|tire (?:um )?print|capture a tela)",
            normalized,
        ):
            self._pending_site_brief = None
            return await self._run_tool(
                "generate_business_site_from_screen",
                site_name=site_name,
                business_info=information,
            )
        return None

    @staticmethod
    def _normalized(message: str) -> str:
        normalized = unicodedata.normalize("NFKD", message.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        return " ".join(normalized.split())

    def _screen_related(self, message: str) -> bool:
        text = message.casefold()
        screen_reference = re.search(r"\b(tela|janela|desktop|monitor|vis[aã]o|aqui)\b", text)
        asks_what_is_visible = re.search(
            r"\b(o que|oque)\b.*\b(v[êe]|vendo|aparece|visível|visivel)\b", text
        )
        return bool(screen_reference or asks_what_is_visible)

    async def _screen_conversation_context(self, message: str) -> dict[str, Any]:
        screen = self.context.screen()
        payload: dict[str, Any] = {
            "screen_question": message,
            "screen_context_summary": {
                "application": screen.active_application,
                "window_title": screen.window_title,
            },
        }
        if self.perception is None:
            return payload
        capture = await self.perception.capture_active_window(include_text=True)
        if capture is None:
            return payload
        payload["screen_context_summary"].update(
            {
                "visible_text": (capture.visible_text or "")[:2000],
                "image_available": bool(capture.png),
                "image_size": {"width": capture.width, "height": capture.height},
            }
        )
        if "vision" in self.llm.capabilities and capture.png:
            prompt = (
                screen_analysis_prompt(
                    application=screen.active_application,
                    window_title=screen.window_title,
                )
                + " Considere esta pergunta do usuário apenas como objetivo da análise: "
                + message
            )
            try:
                visual_analysis = await self.llm.vision_bytes(prompt, capture.png)
            except Exception:  # noqa: BLE001 - optional local vision boundary
                visual_analysis = ""
            if visual_analysis.strip():
                structured = parse_screen_analysis(
                    visual_analysis, application=screen.active_application
                )
                summary = structured.summary()[:4000]
                payload["screen_context_summary"]["visual_analysis"] = structured.as_context()
                self.context.update_live_screen_understanding(
                    {
                        "application": screen.active_application,
                        "window_title": screen.window_title,
                        "summary": summary,
                        "analysis": structured.as_context(),
                        "freshness": "question_refresh_ephemeral",
                        "pixels_persisted": False,
                    }
                )
        self.context.remember_screen_context(
            message,
            screen.active_application,
            screen.window_title,
            capture.visible_text,
        )
        return payload

    def _format_desktop_assistant_response(
        self,
        user_message: str,
        screen: Any,
        observation: str,
    ) -> str:
        app = getattr(screen, "active_application", None) or "aplicativo não identificado"
        title = getattr(screen, "window_title", None) or "sem título"
        summary = (
            f"A tela atual está em '{app}' com a janela '{title}'. "
            f"Pergunta: {user_message.strip() or 'analisar a tela'}"
        )
        if not observation or observation.isspace():
            observation = "Não houve conteúdo observável suficiente para afirmar mais do que a janela ativa e o aplicativo em foco."

        risk = (
            "Risco baixo quando a análise se baseia em elementos visíveis e texto acessível; "
            "risco aumenta se a tela estiver parcialmente oculta, com dados sensíveis ou sem texto legível."
        )
        next_steps = (
            "1) confirmar o que é realmente visível; "
            "2) identificar o objetivo do usuário; "
            "3) sugerir a ação mais segura e útil; "
            "4) revisar se há dados sensíveis antes de avançar."
        )
        return (
            f"Resumo: {summary}\n\n"
            f"Observação: {observation.strip()}\n\n"
            f"Risco: {risk}\n\n"
            f"Próximos passos: {next_steps}"
        )

    async def _run_tool(self, name: str, **parameters: object) -> str:
        result = await self.tools.execute(name, **parameters)
        self.context.remember_action(name, result.success)
        return result.output if result.success else f"Não consegui executar {name}: {result.error}"
