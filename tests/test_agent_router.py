from __future__ import annotations

import json

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import SoftwareSpecialist
from app.providers.llm import LLMProvider


class RecordingProvider(LLMProvider):
    def __init__(self) -> None:
        self.prompts: list[dict] = []

    async def generate(self, prompt: str) -> str:
        parsed = json.loads(prompt)
        self.prompts.append(parsed)
        return f"resposta-{len(self.prompts)}"


def test_selects_domain_specialist_and_generalist_fallback() -> None:
    router = AgentRouter(RecordingProvider())
    selected = router.select("Ajude a corrigir este bug no código Python")
    assert [item.name for item in selected] == ["engenharia_de_software"]
    assert router.select("Olá, tudo bem?")[0].name == "generalista"


def test_selects_multiple_relevant_specialists() -> None:
    router = AgentRouter(RecordingProvider())
    selected = router.select("Investigue riscos de segurança neste código e compare evidências")
    assert {item.name for item in selected} == {
        "engenharia_de_software",
        "seguranca",
        "pesquisa",
    }


@pytest.mark.asyncio
async def test_composes_multi_specialist_answers() -> None:
    provider = RecordingProvider()
    router = AgentRouter(provider)
    answer = await router.respond(
        "Planeje testes de segurança do código",
        {"user_message": "x", "recent_actions": [], "active_screen": {"secret": "hidden"}},
    )
    assert answer == "resposta-4"
    coordinator = provider.prompts[-1]
    assert coordinator["role"] == "coordenador_de_especialistas"
    assert len(coordinator["specialist_analyses"]) == 3
    assert all("active_screen" not in prompt["context"] for prompt in provider.prompts[:-1])


@pytest.mark.asyncio
async def test_specialists_never_receive_tools_or_claim_execution() -> None:
    provider = RecordingProvider()
    router = AgentRouter(provider)
    await router.respond("Revise este código", {"user_message": "Revise"})
    prompt = provider.prompts[0]
    assert "constraint" in prompt
    assert "Não afirme que vê tela" in prompt["constraint"]
    assert "tools" not in prompt
    assert prompt["response_policy"]["identity"].startswith("Você é Kiara")
    assert "material de referência" in prompt["context_policy"]


class FailingProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_returns_degraded_answer_when_all_specialists_fail() -> None:
    router = AgentRouter(FailingProvider(), specialists=(SoftwareSpecialist(),))
    answer = await router.respond("corrija o codigo", {"user_message": "x"})
    assert "Não consegui consultar um especialista" in answer
