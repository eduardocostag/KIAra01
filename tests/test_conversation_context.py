from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import GeneralistSpecialist
from app.automation import AutomationEngine, AutomationStore
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.feedback import CorrectionInbox
from app.models import ScreenContext, ToolResult
from app.providers.llm import LLMProvider


class RecordingProvider(LLMProvider):
    def __init__(self) -> None:
        self.prompts: list[dict] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(json.loads(prompt))
        return f"resposta {len(self.prompts)}"


class VisionRecordingProvider(RecordingProvider):
    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate", "vision"})

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        assert "pergunta do usuário" in prompt.casefold()
        assert image == b"frame-atual"
        return "O editor mostra um erro de importação no arquivo atual."


class CurrentScreenPerception:
    async def capture_active_window(self, *, include_text: bool = False):
        assert include_text is True
        return SimpleNamespace(
            png=b"frame-atual",
            width=800,
            height=600,
            visible_text="ModuleNotFoundError",
        )


class NoTools:
    async def execute(self, name: str, **parameters: object):  # pragma: no cover
        raise AssertionError((name, parameters))


class DiagnosticTools:
    def __init__(self) -> None:
        self.snapshots = iter(({"problem_count": 1}, {"problem_count": 0}))

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        assert name == "system_diagnostics"
        assert parameters["category"] == "drivers"
        return ToolResult(
            True,
            output="coletado",
            metadata={"snapshot": next(self.snapshots), "verified": True},
        )


class CapturingTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        return ToolResult(True, output="aberto")


class LearningStore:
    def __init__(self, tmp_path) -> None:
        self.path = tmp_path / "aprendizado.md"
        self.saved = []

    def save(self, user_message: str, assistant_response: str):
        self.saved.append((user_message, assistant_response))
        return self.path


@pytest.mark.asyncio
async def test_chat_prepares_recurring_automation_disabled_for_review(tmp_path) -> None:
    provider = RecordingProvider()
    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), lambda _spec: None)
    core = AgentCore(
        NoTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
        background=SimpleNamespace(automations=engine),
    )

    response = await core.handle(
        "crie uma automação para abrir https://example.com a cada 2 horas"
    )

    saved = engine.store.list()
    assert len(saved) == 1
    assert saved[0].action == "open_url"
    assert saved[0].interval_seconds == 7200
    assert saved[0].enabled is False
    assert "salva desativada" in response

    listed = await core.handle("liste minhas automações")
    assert "Abrir https://example.com" in listed
    assert "desativada" in listed


@pytest.mark.asyncio
async def test_open_chrome_new_tab_is_normalized_to_allowlisted_action() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    await core.handle("abra o chrome numa nova aba agora")

    assert tools.calls == [("open_application", {"application": "chrome", "new_tab": True})]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "url"),
    (
        ("abra o google", "https://www.google.com"),
        ("abra o instagram agora", "https://www.instagram.com"),
        ("abra o whatsapp", "https://web.whatsapp.com"),
        ("abra o whats", "https://web.whatsapp.com"),
        ("abra o telegram", "https://web.telegram.org"),
        ("abra o windy", "https://www.windy.com"),
        ("abra a vercel", "https://vercel.com"),
    ),
)
async def test_named_sites_are_routed_to_safe_https_urls(command: str, url: str) -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    await core.handle(command)

    assert tools.calls == [("open_url", {"url": url})]


@pytest.mark.asyncio
async def test_kiara_social_profile_uses_persistent_browser_tool() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    await core.handle("abra o instagram da kiara")

    assert tools.calls == [("browser_navigate", {"url": "https://www.instagram.com"})]


@pytest.mark.asyncio
async def test_search_is_encoded_as_google_https_url() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    await core.handle("pesquise por memória RAM com erro")

    assert tools.calls == [
        (
            "browser_navigate",
            {"url": "https://www.google.com/search?q=mem%C3%B3ria+RAM+com+erro"},
        )
    ]


@pytest.mark.asyncio
async def test_unknown_application_falls_back_to_safe_google_search() -> None:
    class MissingApplicationTools(CapturingTools):
        async def execute(self, name: str, **parameters: object) -> ToolResult:
            self.calls.append((name, parameters))
            if name == "open_application":
                return ToolResult(False, error="não instalado")
            return ToolResult(True, output="pesquisa aberta")

    tools = MissingApplicationTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    response = await core.handle("abra o aplicativo desconhecido")

    assert tools.calls == [
        ("open_application", {"application": "desconhecido", "new_tab": False}),
        ("open_url", {"url": "https://www.google.com/search?q=desconhecido"}),
    ]
    assert "pesquisa segura" in response


@pytest.mark.asyncio
async def test_inter_search_expands_known_club_alias() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    response = await core.handle("pesquise sobre o inter")

    assert tools.calls == [
        (
            "browser_navigate",
            {"url": "https://www.google.com/search?q=Sport+Club+Internacional"},
        )
    ]
    assert "Sport Club Internacional" in response
    assert "segundo plano" in response


@pytest.mark.asyncio
async def test_social_message_reaches_critical_tool_with_explicit_fields() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    await core.handle("envie mensagem no telegram para @joao dizendo reunião às 10h")

    assert tools.calls == [
        (
            "send_social_message",
            {"platform": "telegram", "recipient": "@joao", "text": "reunião às 10h"},
        )
    ]


@pytest.mark.asyncio
async def test_site_request_asks_before_capture_then_uses_current_screen() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    question = await core.handle(
        "crie um site para Café Aurora, cafeteria artesanal aberta das 8h às 18h"
    )
    assert "Posso capturar a janela atual" in question
    assert tools.calls == []

    await core.handle("use a tela")

    assert tools.calls == [
        (
            "generate_business_site_from_screen",
            {
                "site_name": "Café Aurora",
                "business_info": ("Café Aurora, cafeteria artesanal aberta das 8h às 18h"),
            },
        )
    ]


@pytest.mark.asyncio
async def test_site_request_can_use_photo_only_after_user_selects_it() -> None:
    tools = CapturingTools()
    core = AgentCore(tools, RecordingProvider(), ContextManager(lambda: ScreenContext()))

    await core.handle("crie um site para Loja Horizonte, roupas femininas")
    await core.handle("use a foto loja.png")

    assert tools.calls == [
        (
            "generate_business_site",
            {
                "site_name": "Loja Horizonte",
                "business_info": "Loja Horizonte, roupas femininas",
                "reference_image": "loja.png",
            },
        )
    ]


@pytest.mark.asyncio
async def test_agent_core_adds_completed_exchange_to_next_request_context() -> None:
    provider = RecordingProvider()
    context = ContextManager(lambda: ScreenContext())
    router = AgentRouter(
        provider,
        specialists=(),
        generalist=GeneralistSpecialist(),
    )
    core = AgentCore(NoTools(), provider, context, agent_router=router)

    assert await core.handle("Meu nome é Eduardo") == "resposta 1"
    assert await core.handle("Qual é meu nome?") == "resposta 2"

    first_context = provider.prompts[0]["context"]
    second_context = provider.prompts[1]["context"]
    assert first_context["conversation_history"] == []
    assert second_context["conversation_history"] == [
        {"role": "user", "content": "Meu nome é Eduardo"},
        {"role": "assistant", "content": "resposta 1"},
    ]


@pytest.mark.asyncio
async def test_feedback_yes_saves_last_exchange_and_no_discards(tmp_path) -> None:
    provider = RecordingProvider()
    learning = LearningStore(tmp_path)
    core = AgentCore(
        NoTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
        feedback_learning=learning,
    )

    first = await core.handle("Como resolvo o erro?")
    approved = await core.handle("sim")
    second = await core.handle("Outra pergunta")
    rejected = await core.handle("não")

    assert first.endswith("Te auxiliei?")
    assert learning.saved == [("Como resolvo o erro?", "resposta 1")]
    assert "Guardei" in approved
    assert second.endswith("Te auxiliei?")
    assert "Não guardei" in rejected
    assert len(learning.saved) == 1
    assert provider.prompts[1]["context"]["conversation_history"][-1] == {
        "role": "assistant",
        "content": "resposta 1",
    }


@pytest.mark.asyncio
async def test_feedback_no_queues_exchange_and_reports_location(tmp_path) -> None:
    provider = RecordingProvider()
    learning = LearningStore(tmp_path)
    inbox = CorrectionInbox(tmp_path / "correction-inbox.jsonl")
    core = AgentCore(
        NoTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
        feedback_learning=learning,
        correction_inbox=inbox,
    )

    await core.handle("Resposta difícil")
    rejected = await core.handle("não")
    location = await core.handle("onde estão as correções?")

    assert "1 pendente" in rejected
    assert learning.saved == []
    record = json.loads(inbox.path.read_text(encoding="utf-8"))
    assert record["user_message"] == "Resposta difícil"
    assert record["assistant_response"] == "resposta 1"
    assert str(inbox.path) in location
    assert "não é enviado automaticamente" in location


@pytest.mark.asyncio
async def test_feedback_no_with_explanation_is_consumed_instead_of_sent_to_model(tmp_path) -> None:
    provider = RecordingProvider()
    inbox = CorrectionInbox(tmp_path / "correction-inbox.jsonl")
    core = AgentCore(
        NoTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
        correction_inbox=inbox,
    )

    await core.handle("Explique DNS")
    response = await core.handle("não, você abriu o Google e não abriu o site")

    assert "Registrei a resposta" in response
    assert len(provider.prompts) == 1


@pytest.mark.asyncio
async def test_new_request_discards_unanswered_feedback(tmp_path) -> None:
    provider = RecordingProvider()
    learning = LearningStore(tmp_path)
    core = AgentCore(
        NoTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
        feedback_learning=learning,
    )

    await core.handle("Primeira")
    await core.handle("Nova pergunta sem responder sim ou não")
    await core.handle("sim")

    assert learning.saved == [("Nova pergunta sem responder sim ou não", "resposta 2")]


@pytest.mark.asyncio
async def test_screen_related_conversation_refreshes_local_visual_analysis() -> None:
    provider = VisionRecordingProvider()
    screen = ScreenContext(active_application="Editor", window_title="app.py")
    context = ContextManager(lambda: screen)
    core = AgentCore(
        NoTools(),
        provider,
        context,
        agent_router=AgentRouter(provider),
        perception=CurrentScreenPerception(),
    )

    await core.handle("Há algo nesta janela relacionado ao bug?")

    specialist_context = provider.prompts[-1]["context"]
    summary = specialist_context["screen_context_summary"]
    assert "erro de importação" in summary["visual_analysis"]["subject"]
    assert context.live_screen_understanding()["freshness"] == "question_refresh_ephemeral"


def test_explain_request_without_screen_reference_does_not_trigger_vision() -> None:
    core = AgentCore(NoTools(), RecordingProvider(), ContextManager(lambda: ScreenContext()))

    assert core._screen_related("Explique consistência eventual em sistemas distribuídos") is False
    assert core._screen_related("Explique o que aparece nesta tela") is True


@pytest.mark.asyncio
async def test_helpdesk_compares_before_and_after_without_claiming_resolution() -> None:
    provider = RecordingProvider()
    core = AgentCore(
        DiagnosticTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider),
    )

    await core.handle("faça um diagnóstico dos drivers")
    await core.handle("verifique se resolveu o driver")

    assert provider.prompts[0]["context"]["diagnostic_snapshot"]["data"] == {"problem_count": 1}
    comparison = provider.prompts[1]["context"]["diagnostic_comparison"]
    assert comparison["changed"] is True
    assert comparison["resolution_confirmed"] is True


@pytest.mark.asyncio
async def test_current_date_is_answered_without_calling_the_model() -> None:
    provider = RecordingProvider()
    core = AgentCore(NoTools(), provider, ContextManager(lambda: ScreenContext()))

    answer = await core.handle("qual é a data de hoje?")

    assert answer.startswith("Hoje é ")
    assert str(datetime.now(UTC).astimezone().year) in answer
    assert provider.prompts == []
