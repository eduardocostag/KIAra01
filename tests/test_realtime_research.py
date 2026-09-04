from __future__ import annotations

import json

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import GeneralistSpecialist
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.models import ScreenContext, ToolResult
from app.providers.llm import LLMProvider


class ResearchProvider(LLMProvider):
    def __init__(self) -> None:
        self.prompt: dict | None = None

    async def generate(self, prompt: str) -> str:
        self.prompt = json.loads(prompt)
        return "Análise atual com ressalvas."


class ResearchTools:
    def __init__(self, *, blocked: bool = False) -> None:
        self.blocked = blocked
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, name: str, **parameters: object) -> ToolResult:
        self.calls.append((name, parameters))
        if name == "browser_navigate" and not self.blocked:
            return ToolResult(
                True,
                output="Resultados — Google",
                metadata={"text": "resultado esportivo verificado " * 20},
            )
        if name == "browser_navigate":
            return ToolResult(False, error="bloqueado")
        return ToolResult(True, output="aberto")


def make_core(tools: ResearchTools, provider: ResearchProvider) -> AgentCore:
    return AgentCore(
        tools,
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
    )


@pytest.mark.asyncio
async def test_lineup_research_expands_inter_and_grounds_answer() -> None:
    tools, provider = ResearchTools(), ResearchProvider()

    response = await make_core(tools, provider).handle("qual a escalação do inter hoje?")

    assert response == "Análise atual com ressalvas."
    assert "Sport+Club+Internacional" in str(tools.calls[0][1]["url"])
    assert provider.prompt is not None
    assert provider.prompt["role"] == "pesquisador_de_informacoes_atuais"
    assert "Não invente" in provider.prompt["instructions"]


@pytest.mark.asyncio
async def test_betting_research_requires_risk_language() -> None:
    tools, provider = ResearchTools(), ResearchProvider()

    await make_core(tools, provider).handle("palpites de aposta para os jogos de hoje")

    assert provider.prompt is not None
    assert "não prometa lucro" in provider.prompt["instructions"]
    assert "limite de perda" in provider.prompt["instructions"]


@pytest.mark.asyncio
async def test_blocked_research_stays_in_background_without_inventing() -> None:
    tools, provider = ResearchTools(blocked=True), ResearchProvider()

    response = await make_core(tools, provider).handle("qual a escalação do inter hoje?")

    assert [call[0] for call in tools.calls] == ["browser_navigate"]
    assert provider.prompt is None
    assert "segundo plano" in response
    assert "Não vou inventar" in response
