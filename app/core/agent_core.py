from __future__ import annotations

import re
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.agents.router import AgentRouter
from app.core.context import ContextManager
from app.core.intents import Intent, IntentRouter
from app.perception import ScreenPerception
from app.planning import TaskPlanner
from app.providers.llm import LLMProvider
from app.tools.registry import ToolRegistry

IntentHandler = Callable[[Intent, str], Awaitable[str]]


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
    ) -> None:
        self.tools, self.llm, self.context = tools, llm, context
        self.router = router or IntentRouter()
        self.agent_router = agent_router or AgentRouter(llm)
        self.background = background
        self.resources = resources or []
        self.task_planner = task_planner
        self.perception = perception
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
        }

    async def handle(self, message: str) -> str:
        intent = self.router.route(message)
        response = await self._handlers.get(intent.name, self._conversation)(intent, message)
        self.context.remember_exchange(message, response)
        return response

    async def handle_stream(self, message: str) -> AsyncIterator[str]:
        """Stream ordinary conversation while preserving safe handlers for actions."""
        intent = self.router.route(message)
        if intent.name != "conversation":
            yield await self.handle(message)
            return
        context = self.context.assemble(message)
        if self._screen_related(message):
            context.update(await self._screen_conversation_context(message))
        chunks: list[str] = []
        async for delta in self.agent_router.stream_respond(message, context):
            chunks.append(delta)
            yield delta
        self.context.remember_exchange(message, "".join(chunks))

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
        context = self.context.assemble(message)
        if self._screen_related(message):
            context.update(await self._screen_conversation_context(message))
        return await self.agent_router.respond(message, context)

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
        payload: dict[str, Any] = {
            "screen_question": message,
            "screen_context_summary": {
                "application": self.context.screen().active_application,
                "window_title": self.context.screen().window_title,
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
        self.context.remember_screen_context(
            message,
            self.context.screen().active_application,
            self.context.screen().window_title,
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
