from __future__ import annotations

import re
import unicodedata
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Any, Protocol

from app.agents.router import AgentRouter
from app.core.context import ContextManager
from app.core.intents import Intent, IntentRouter
from app.helpdesk import compare_snapshots
from app.perception import ScreenPerception
from app.perception.analysis import parse_screen_analysis, screen_analysis_prompt
from app.planning import TaskPlanner
from app.providers.llm import LLMProvider
from app.tools.registry import ToolRegistry

IntentHandler = Callable[[Intent, str], Awaitable[str]]


class FeedbackLearningStore(Protocol):
    def save(self, user_message: str, assistant_response: str) -> Any: ...


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
        feedback_prompt: str = "Te auxiliei?",
    ) -> None:
        self.tools, self.llm, self.context = tools, llm, context
        self.router = router or IntentRouter()
        self.agent_router = agent_router or AgentRouter(llm)
        self.background = background
        self.resources = resources or []
        self.task_planner = task_planner
        self.perception = perception
        self.feedback_learning = feedback_learning
        self.feedback_prompt = feedback_prompt.strip() or "Te auxiliei?"
        self._pending_feedback: tuple[str, str] | None = None
        self._diagnostic_baselines: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, IntentHandler] = {
            "active_window": self._active_window,
            "open_application": self._open_application,
            "powershell": self._powershell,
            "screen_context": self._screen_context,
            "screen_capability": self._screen_capability,
            "open_url": self._open_url,
            "conversation": self._conversation,
            "complex_task": self._complex_task,
            "sync_obsidian": self._sync_obsidian,
            "search_obsidian": self._search_obsidian,
            "open_obsidian_note": self._open_obsidian_note,
            "save_obsidian_note": self._save_obsidian_note,
            "helpdesk_diagnostic": self._helpdesk_diagnostic,
            "helpdesk_verify": self._helpdesk_verify,
            "current_datetime": self._current_datetime,
        }

    async def handle(self, message: str) -> str:
        feedback = self._consume_feedback(message)
        if feedback is not None:
            return feedback
        self._pending_feedback = None
        intent = self.router.route(message)
        response = await self._handlers.get(intent.name, self._conversation)(intent, message)
        displayed = self._request_feedback(message, response)
        # The feedback question belongs to the UI, not to future model context.
        self.context.remember_exchange(message, response)
        return displayed

    async def handle_stream(self, message: str) -> AsyncIterator[str]:
        """Stream ordinary conversation while preserving safe handlers for actions."""
        feedback = self._consume_feedback(message)
        if feedback is not None:
            yield feedback
            return
        self._pending_feedback = None
        intent = self.router.route(message)
        if intent.name != "conversation":
            response = await self._handlers.get(intent.name, self._conversation)(intent, message)
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
        if self.feedback_learning is None:
            return response
        self._pending_feedback = (user_message, response)
        return f"{response.rstrip()}\n\n{self.feedback_prompt}"

    def _consume_feedback(self, message: str) -> str | None:
        if self.feedback_learning is None or self._pending_feedback is None:
            return None
        normalized = unicodedata.normalize("NFKD", message.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
        normalized = " ".join(normalized.split())
        positive = normalized in {
            "sim",
            "sim ajudou",
            "ajudou",
            "resolveu",
            "com certeza",
        }
        negative = normalized in {
            "nao",
            "nao ajudou",
            "nao resolveu",
            "ainda nao",
        }
        if not positive and not negative:
            return None
        pending = self._pending_feedback
        if negative:
            self._pending_feedback = None
            return "Certo. Não guardei esta conversa no Obsidian."
        try:
            destination = self.feedback_learning.save(*pending)
        except Exception as exc:  # noqa: BLE001 - local integration boundary
            return f"Não consegui guardar o aprendizado no Obsidian ({type(exc).__name__})."
        self._pending_feedback = None
        return f"Perfeito. Guardei este aprendizado no Obsidian: {destination.name}."

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
        return await self._run_tool(
            "open_application", application=intent.parameters["application"]
        )

    async def _powershell(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("execute_powershell", command=intent.parameters["command"])

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
        prompt = (
            "Analise cuidadosamente esta captura da janela ativa do usuário. "
            "Descreva somente o que estiver visível na imagem e no texto acessível, em português do Brasil. "
            "Diferencie fatos observados de inferências e informe claramente quando algo estiver ilegível, oculto ou incerto. "
            f"Aplicativo: {screen.active_application or 'não identificado'}. "
            f"Título da janela: {screen.window_title or 'sem título'}. "
            f"Texto visível acessível: {visible_text[:2000] if visible_text else 'nenhum texto acessível detectado.'} "
            "Não invente conteúdo. Pergunta do usuário: " + message
        )
        try:
            analysis = await self.llm.vision_bytes(prompt, capture.png)
            return self._format_desktop_assistant_response(message, screen, analysis)
        except Exception as exc:  # noqa: BLE001 - provider failure becomes an honest response
            return self._format_desktop_assistant_response(
                message,
                screen,
                f"Capturei a tela, mas a análise visual local falhou ({type(exc).__name__}).",
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
            "identify_active_window": self.perception is not None,
            "analyze_screen_pixels_locally": (
                self.perception is not None and "vision" in self.llm.capabilities
            ),
            "system_diagnostics_read_only": "system_diagnostics" in tool_names,
            "execute_actions_with_confirmation": bool(tool_names),
            "current_date_time_from_system_clock": True,
        }
        return context

    async def _complex_task(self, _intent: Intent, message: str) -> str:
        if self.task_planner is None:
            return "O planejamento com execução está desativado por segurança."
        return await self.task_planner.run(message, self.context.assemble(message))

    def _screen_related(self, message: str) -> bool:
        patterns = (
            r"\b(olha|olhe|analise|descreva|explique|observe|mostra|mostre)\b",
            r"\b(tela|janela|desktop|vis[aã]o)\b",
            r"\b(o que|oque)\b.*\b(v[êe]|vendo|v[ea])\b",
        )
        text = message.casefold()
        return any(re.search(pattern, text) for pattern in patterns)

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
