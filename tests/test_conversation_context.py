from __future__ import annotations

import json

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import GeneralistSpecialist
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.models import ScreenContext
from app.providers.llm import LLMProvider


class RecordingProvider(LLMProvider):
    def __init__(self) -> None:
        self.prompts: list[dict] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(json.loads(prompt))
        return f"resposta {len(self.prompts)}"


class NoTools:
    async def execute(self, name: str, **parameters: object):  # pragma: no cover
        raise AssertionError((name, parameters))


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
