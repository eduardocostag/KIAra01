from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import GeneralistSpecialist
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
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


class LearningStore:
    def __init__(self, tmp_path) -> None:
        self.path = tmp_path / "aprendizado.md"
        self.saved = []

    def save(self, user_message: str, assistant_response: str):
        self.saved.append((user_message, assistant_response))
        return self.path


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

    assert provider.prompts[0]["context"]["diagnostic_snapshot"]["data"] == {
        "problem_count": 1
    }
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
