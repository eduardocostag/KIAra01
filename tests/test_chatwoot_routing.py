import pytest

from app.bootstrap import build_app
from app.config import Settings
from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.intents import IntentRouter
from app.integrations.operational_skills import OperationalSkills
from app.models import ScreenContext, ToolResult


@pytest.mark.parametrize(("message", "expected"), [
    ("liste as caixas de entrada do Chatwoot", {"action": "inboxes"}),
    ("Kiara, liste conversas abertas no Chatwoot", {"action": "conversations", "status": "open"}),
    ("mostre conversas resolvidas no Chatwoot", {"action": "conversations", "status": "resolved"}),
    ("consulte conversas pendentes no Chatwoot", {"action": "conversations", "status": "pending"}),
    ("leia mensagens da conversa 42 no Chatwoot", {"action": "messages", "conversation_id": 42}),
    ("responda no Chatwoot na conversa 42 dizendo Olá! Tudo bem?",
     {"action": "send", "conversation_id": 42, "content": "Olá! Tudo bem?"}),
    ("envie no Chatwoot conversa #42: Tudo certo.",
     {"action": "send", "conversation_id": 42, "content": "Tudo certo."}),
    ("responda no Chatwoot para Maria", {"action": "help"}),
])
def test_explicit_chatwoot_commands(message, expected):
    intent = IntentRouter().route(message)
    assert intent.name == "chatwoot_operation"
    assert intent.parameters == expected


@pytest.mark.parametrize("message", [
    "como o Chatwoot funciona?", "não envie nada no Chatwoot",
    "liste conversas do WhatsApp", "quero implementar Chatwoot",
])
def test_other_requests_do_not_trigger_chatwoot_action(message):
    assert IntentRouter().route(message).name != "chatwoot_operation"


def test_chatwoot_skill_selected():
    assert OperationalSkills().relevant("consulte o atendimento no Chatwoot")[0]["name"] == (
        "kiara-chatwoot"
    )


class NoRemoteModel:
    async def generate(self, _prompt):
        raise AssertionError("Chatwoot customer data must not call a model")


class FakeTools:
    def __init__(self, configured=True):
        self.configured = configured
        self.calls = []

    def names(self):
        return ("chatwoot_read", "chatwoot_send_message") if self.configured else ()

    async def execute(self, name, **parameters):
        self.calls.append((name, parameters))
        return ToolResult(True, output="Private customer message")


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_customer_content_not_forwarded_to_model_history_or_learning(streaming):
    tools = FakeTools()
    context = ContextManager(lambda: ScreenContext())
    core = AgentCore(tools, NoRemoteModel(), context)
    command = "responda no Chatwoot na conversa 42 dizendo Private reply"
    result = "".join([chunk async for chunk in core.handle_stream(command)]) if streaming else (
        await core.handle(command)
    )
    assert result == "Private customer message"
    assert tools.calls == [("chatwoot_send_message", {
        "conversation_id": 42, "content": "Private reply",
    })]
    assert "Private" not in str(context.assemble("próxima pergunta"))
    assert core._pending_feedback is None


@pytest.mark.asyncio
async def test_unconfigured_chatwoot_provides_setup_guidance_without_call():
    tools = FakeTools(configured=False)
    core = AgentCore(tools, NoRemoteModel(), ContextManager(lambda: ScreenContext()))
    assert "Configure" in await core.handle("liste as caixas do Chatwoot")
    assert tools.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_bootstrap_registers_chatwoot_only_when_enabled(tmp_path, monkeypatch, enabled):
    monkeypatch.setenv("CHATWOOT_API_ACCESS_TOKEN", "synthetic-token")
    monkeypatch.setenv("CHATWOOT_BASE_URL", "http://127.0.0.1:3005")
    monkeypatch.setenv("CHATWOOT_ACCOUNT_ID", "7")
    monkeypatch.setenv("KIARA_LLM_PROVIDER", "local")
    monkeypatch.delenv("KIARA_LLM_FALLBACK_PROVIDER", raising=False)
    core, _ = build_app(Settings(root=tmp_path, raw={
        "integrations": {"chatwoot": {"enabled": enabled}},
        "memory": {"enabled": False}, "knowledge": {"enabled": False},
        "personal": {"enabled": False}, "web_studio": {"enabled": False},
    }))
    try:
        assert ("chatwoot_read" in core.tools.names()) == enabled
        assert ("chatwoot_send_message" in core.tools.names()) == enabled
        if enabled:
            assert core.tools._tools["chatwoot_read"].client.account_id == 7
    finally:
        await core.aclose()
