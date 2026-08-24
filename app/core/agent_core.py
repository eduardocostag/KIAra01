from __future__ import annotations

from collections.abc import Awaitable, Callable
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
            "active_window": self._active_window, "open_application": self._open_application,
            "powershell": self._powershell, "screen_context": self._screen_context,
            "screen_capability": self._screen_capability,
            "open_url": self._open_url, "conversation": self._conversation,
            "complex_task": self._complex_task,
        }

    async def handle(self, message: str) -> str:
        intent = self.router.route(message)
        return await self._handlers.get(intent.name, self._conversation)(intent, message)

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
        return await self._run_tool("open_application", application=intent.parameters["application"])

    async def _powershell(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("execute_powershell", command=intent.parameters["command"])

    async def _open_url(self, intent: Intent, _message: str) -> str:
        return await self._run_tool("open_url", url=intent.parameters["url"])

    async def _screen_context(self, _intent: Intent, message: str) -> str:
        screen = self.context.screen()
        if "vision" not in self.llm.capabilities:
            return f"Janela: {screen.window_title}. Aplicativo: {screen.active_application}. O modelo visual local ainda não está disponível; não consigo confirmar o conteúdo dos pixels."
        if self.perception is None:
            return "A captura visual segura não está disponível nesta sessão."
        capture = await self.perception.capture_virtual_desktop()
        self.context.remember_action("analyze_screen_ephemeral", capture is not None)
        if capture is None:
            return "Não consegui capturar o desktop autorizado para análise."
        prompt = (
            "Analise cuidadosamente esta captura atual do desktop do usuário. "
            "Descreva apenas o que estiver realmente visível nos pixels, em português do Brasil. "
            "Diferencie fatos observados de inferências e diga claramente quando algo estiver "
            "ilegível, oculto ou incerto. Não invente conteúdo. Pergunta do usuário: " + message
        )
        try:
            return await self.llm.vision_bytes(prompt, capture.png)
        except Exception as exc:  # noqa: BLE001 - provider failure becomes an honest response
            return f"Capturei a tela, mas a análise visual local falhou ({type(exc).__name__})."

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
        return await self.agent_router.respond(message, self.context.assemble(message))

    async def _complex_task(self, _intent: Intent, message: str) -> str:
        if self.task_planner is None:
            return "O planejamento com execução está desativado por segurança."
        return await self.task_planner.run(message, self.context.assemble(message))

    async def _run_tool(self, name: str, **parameters: object) -> str:
        result = await self.tools.execute(name, **parameters)
        self.context.remember_action(name, result.success)
        return result.output if result.success else f"Não consegui executar {name}: {result.error}"
