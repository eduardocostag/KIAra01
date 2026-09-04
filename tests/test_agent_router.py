from __future__ import annotations

import json

import pytest

from app.agents.contracts import SpecialistResult
from app.agents.router import AgentRouter
from app.agents.specialists import (
    DataSystemsSpecialist,
    HelpdeskSpecialist,
    InfrastructureSpecialist,
    SalesDevelopmentSpecialist,
    SoftwareSpecialist,
)
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


def test_router_normalizes_accents_avoids_substring_false_positive_and_reports_confidence() -> None:
    router = AgentRouter(RecordingProvider())
    assert router.select("Preciso revisar a arquitetura do programa")[0].name == (
        "engenharia_de_software"
    )
    assert router.select("Qual é a capital do Brasil?")[0].name == "generalista"
    decision = router.decide("Existe uma vulnerabilidade de segurança nesta senha")
    assert decision.confidence > 0
    assert decision.scores["seguranca"] >= 2


def test_selects_multiple_relevant_specialists() -> None:
    router = AgentRouter(RecordingProvider())
    selected = router.select("Investigue riscos de segurança neste código e compare evidências")
    assert {item.name for item in selected} == {
        "engenharia_de_software",
        "seguranca",
        "pesquisa",
    }


def test_selects_helpdesk_for_software_and_hardware_support() -> None:
    router = AgentRouter(RecordingProvider())
    assert "helpdesk" in {
        item.name for item in router.select("Meu Windows está lento e o driver de áudio falhou")
    }
    assert "helpdesk" in {
        item.name for item in router.select("O monitor e a porta USB não funcionam")
    }


def test_selects_sdr_specialist_for_prospecting_and_webscraping_requests() -> None:
    router = AgentRouter(RecordingProvider())
    selected = router.select(
        "Quero prospectar clínicas em Porto Alegre e extrair leads sem site e com WhatsApp"
    )
    assert "sdr_profissional" in {item.name for item in selected}


def test_sdr_specialist_instructions_require_ranked_lead_output() -> None:
    instructions = SalesDevelopmentSpecialist().instructions()
    assert "lista de leads" in instructions.lower()
    assert "ranking" in instructions.lower()
    assert "tabela" in instructions.lower()


@pytest.mark.parametrize(
    "question",
    (
        "O que é DHCP?",
        "Qual a diferença entre IPv4 e IPv6?",
        "Snapshot pode substituir backup? Por quê?",
        "Como funciona RAID 5?",
        "Como testar a porta 443 usando PowerShell?",
        "Por que clientes de Active Directory devem utilizar o DNS do domínio?",
        "Um script funciona manualmente, mas falha pelo RMM. Quais causas investigar?",
        "Como visualizar logs de um serviço usando journalctl?",
        "Qual a diferença entre S3 e EBS?",
        "Qual a diferença entre Terraform e Ansible?",
    ),
)
def test_infrastructure_questions_never_fall_back_to_generalist(question: str) -> None:
    selected = AgentRouter(RecordingProvider()).select(question)
    assert "infraestrutura_ti" in {item.name for item in selected}


def test_infrastructure_prompt_requires_evidence_driven_diagnosis() -> None:
    instructions = InfrastructureSpecialist().instructions()
    assert "hipóteses" in instructions
    assert "resultado esperado" in instructions
    assert "snapshot nunca" in instructions.casefold()
    assert "Nunca recomende desativar ou contornar firewall" in instructions
    assert "Get-NetTCPConnection" in instructions
    assert "Test-NetConnection -Port testa TCP, não UDP" in instructions


def test_database_specialist_rejects_generic_tuning_and_requires_evidence() -> None:
    specialist = DataSystemsSpecialist()
    selected = AgentRouter(RecordingProvider()).select(
        "Uma consulta SQL ficou lenta com milhões de registros"
    )
    assert selected[0].name == "dados_e_bancos"
    assert "EXPLAIN" in specialist.instructions()
    assert "Nunca recomende SHRINK" in specialist.instructions()


def test_dominant_specialist_avoids_redundant_local_model_contention() -> None:
    selected = AgentRouter(RecordingProvider()).select(
        "Investigue esta consulta SQL em uma tabela com milhões de registros"
    )
    assert [item.name for item in selected] == ["dados_e_bancos"]


@pytest.mark.asyncio
async def test_helpdesk_receives_live_screen_understanding() -> None:
    provider = RecordingProvider()
    router = AgentRouter(provider, specialists=(HelpdeskSpecialist(),))
    await router.respond(
        "Ajude com este erro de driver",
        {
            "user_message": "Ajude com este erro de driver",
            "live_screen_understanding": {
                "summary": "Gerenciador de Dispositivos mostra código 10 no adaptador",
                "pixels_persisted": False,
            },
        },
    )
    assert provider.prompts[0]["context"]["live_screen_understanding"]["pixels_persisted"] is False


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
async def test_long_specialist_answers_are_composed_with_their_conclusions() -> None:
    provider = RecordingProvider()
    router = AgentRouter(provider)
    content = "premissa " + ("detalhe " * 700) + "SLO rollback conclusão"
    answer = await router._compose(
        "Defina arquitetura, SLO e rollback",
        (
            SpecialistResult("arquitetura", content),
            SpecialistResult("operações", content),
            SpecialistResult("qualidade", content),
        ),
    )
    assert answer == "resposta-1"
    analyses = provider.prompts[0]["specialist_analyses"]
    assert all("SLO rollback conclusão" in item["content"] for item in analyses)
    assert all(len(item["content"]) < 4100 for item in analyses)


@pytest.mark.asyncio
async def test_specialists_never_receive_tools_or_claim_execution() -> None:
    provider = RecordingProvider()
    router = AgentRouter(provider)
    await router.respond("Revise este código", {"user_message": "Revise"})
    prompt = provider.prompts[0]
    assert "constraint" in prompt
    assert "assistant_capabilities" in prompt["constraint"]
    assert "não invente acesso" in prompt["constraint"]
    assert "tools" not in prompt
    assert prompt["response_policy"]["identity"].startswith("Você é Kiara")
    assert "material de referência" in prompt["context_policy"]


@pytest.mark.asyncio
async def test_screen_context_reaches_specialist_for_visual_conversation() -> None:
    provider = RecordingProvider()
    router = AgentRouter(provider, specialists=(SoftwareSpecialist(),))
    payload = {
        "user_message": "olha minha tela e me explica",
        "active_screen": {"active_application": "Google Chrome", "window_title": "Dashboard"},
        "screen_context_summary": {
            "application": "Google Chrome",
            "window_title": "Dashboard",
            "visible_text": "Relatório de vendas",
        },
    }
    await router.respond("olha minha tela e me explica", payload)
    prompt = provider.prompts[0]
    assert "screen_context_summary" in prompt["context"]
    assert prompt["context"]["screen_context_summary"]["window_title"] == "Dashboard"


class FailingProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_returns_degraded_answer_when_all_specialists_fail() -> None:
    router = AgentRouter(FailingProvider(), specialists=(SoftwareSpecialist(),))
    answer = await router.respond("corrija o codigo", {"user_message": "x"})
    assert "Não consegui consultar um especialista" in answer
