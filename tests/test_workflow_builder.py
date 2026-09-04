from __future__ import annotations

import pytest

from app.agents.router import AgentRouter
from app.agents.specialists import GeneralistSpecialist
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.models import ScreenContext
from app.workflows import ConversationalWorkflowBuilder, WorkflowStore
from tests.test_conversation_context import NoTools, RecordingProvider


def test_builder_collects_context_and_saves_only_after_confirmation(tmp_path) -> None:
    store = WorkflowStore(tmp_path / "workflows.db")
    builder = ConversationalWorkflowBuilder(store)

    first = builder.begin("crie um fluxo complexo de atendimento pelo whatsapp")
    assert "O que o cliente" in first
    assert "Como a Kiara" in builder.consume("Cliente informa produto, defeito e urgência")
    assert "quais ações" in builder.consume("Seja cordial e confirme o entendimento")
    assert "Quando ela deve" in builder.consume("Consultar pedido e preparar diagnóstico")
    preview = builder.consume("Escalar cobranças e qualquer risco para uma pessoa")
    assert "Revise o fluxo" in preview
    assert store.list() == []

    saved = builder.consume("confirmar fluxo")

    assert "salvo como pronto" in saved
    workflows = store.list()
    assert len(workflows) == 1
    assert workflows[0].channel == "whatsapp"
    assert workflows[0].status == "ready"
    assert workflows[0].enabled is False


def test_builder_can_cancel_without_persisting(tmp_path) -> None:
    store = WorkflowStore(tmp_path / "workflows.db")
    builder = ConversationalWorkflowBuilder(store)
    builder.begin("automatize suporte de hardware")

    assert "nenhuma automação foi salva" in builder.consume("cancelar fluxo")
    assert store.list() == []


@pytest.mark.asyncio
async def test_core_conducts_complete_whatsapp_workflow_conversation(tmp_path) -> None:
    provider = RecordingProvider()
    builder = ConversationalWorkflowBuilder(WorkflowStore(tmp_path / "workflows.db"))
    core = AgentCore(
        NoTools(),
        provider,
        ContextManager(lambda: ScreenContext()),
        agent_router=AgentRouter(provider, specialists=(), generalist=GeneralistSpecialist()),
        workflow_builder=builder,
    )

    start = await core.handle("monte uma automação complexa de atendimento pelo whatsapp")
    assert "Te auxiliei?" not in start
    await core.handle("O cliente descreve a necessidade e informa nome e número do pedido")
    await core.handle("Cumprimente, entenda o pedido e não prometa prazo sem consultar")
    await core.handle("Consultar pedido, preparar resposta e pedir aprovação antes de enviar")
    preview = await core.handle("Transferir para humano em pagamento, risco ou cliente irritado")
    assert "Revise o fluxo" in preview
    result = await core.handle("confirmar fluxo")

    assert "salvo como pronto" in result
    assert builder.store.list()[0].response_policy.startswith("Cumprimente")


def test_workflow_intents_cover_support_domains() -> None:
    from app.core.intents import IntentRouter

    router = IntentRouter()
    assert router.route("automatize o atendimento por whatsapp").name == "start_workflow_design"
    assert router.route("crie um fluxo complexo de suporte de hardware").name == (
        "start_workflow_design"
    )
    assert router.route("liste meus fluxos de atendimento").name == "list_workflows"
