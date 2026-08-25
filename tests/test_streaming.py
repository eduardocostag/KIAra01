from __future__ import annotations

import pytest

from app.core.agent_core import AgentCore
from app.core.context import ContextManager
from app.core.streaming import provider_stream_events
from app.models import ScreenContext
from app.providers.llm import LLMProvider


class DeltaProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        return prompt

    async def stream(self, prompt: str):
        yield prompt[:2]
        yield prompt[2:]


@pytest.mark.asyncio
async def test_core_stream_contract_has_lifecycle_deltas_and_final_text() -> None:
    events = [event async for event in provider_stream_events(DeltaProvider(), "Kiara")]
    assert [event.kind for event in events] == ["started", "text_delta", "text_delta", "completed"]
    assert [event.delta for event in events[1:3]] == ["Ki", "ara"]
    assert events[-1].text == "Kiara"


class ConversationProvider(LLMProvider):
    async def generate(self, prompt: str) -> str:
        return "Olá mundo"

    async def stream(self, prompt: str):
        yield "Olá "
        yield "mundo"


class NoTools:
    async def execute(self, name, **parameters):
        raise AssertionError((name, parameters))


@pytest.mark.asyncio
async def test_agent_core_streams_and_records_the_completed_exchange() -> None:
    context = ContextManager(lambda: ScreenContext())
    core = AgentCore(NoTools(), ConversationProvider(), context)

    chunks = [chunk async for chunk in core.handle_stream("olá")]

    assert "".join(chunks) == "Olá mundo"
    assert context.assemble("continue")["conversation_history"][-2:] == [
        {"role": "user", "content": "olá"},
        {"role": "assistant", "content": "Olá mundo"},
    ]


@pytest.mark.asyncio
async def test_agent_core_appends_feedback_question_after_stream(tmp_path) -> None:
    class Learning:
        def save(self, user_message, assistant_response):
            return tmp_path / "ok.md"

    core = AgentCore(
        NoTools(),
        ConversationProvider(),
        ContextManager(lambda: ScreenContext()),
        feedback_learning=Learning(),
    )

    chunks = [chunk async for chunk in core.handle_stream("olá")]

    assert "".join(chunks) == "Olá mundo\n\nTe auxiliei?"
