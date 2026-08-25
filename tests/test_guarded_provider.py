from __future__ import annotations

import json

import pytest

from app.providers.guarded import CircuitOpenError, CloudUsageLimitError, GuardedRemoteProvider
from app.providers.llm import LLMProvider


class RecordingProvider(LLMProvider):
    def __init__(self, *, fail: bool = False) -> None:
        self.prompts: list[str] = []
        self.fail = fail

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("remote failure")
        return "remote"


@pytest.mark.asyncio
async def test_guard_removes_private_local_context_before_remote_call(tmp_path) -> None:
    remote = RecordingProvider()
    guarded = GuardedRemoteProvider(remote, name="groq:test", ledger_path=tmp_path / "usage.json")
    prompt = json.dumps(
        {
            "user_message": "ajude",
            "active_screen": {"title": "Banco"},
            "screen_context_summary": {"visual_analysis": "saldo confidencial"},
            "relevant_memories": [{"content": "segredo"}],
            "relevant_knowledge": [{"content": "nota privada"}],
            "live_screen_understanding": {"text": "senha"},
            "context": {
                "active_screen": {"title": "Banco"},
                "relevant_knowledge": [{"content": "segredo aninhado"}],
            },
        }
    )

    assert await guarded.generate(prompt) == "remote"
    sent = json.loads(remote.prompts[0])
    assert sent["user_message"] == "ajude"
    assert "active_screen" not in sent
    assert "screen_context_summary" not in sent
    assert "relevant_memories" not in sent
    assert "relevant_knowledge" not in sent
    assert "live_screen_understanding" not in sent
    assert sent["context"] == {}


@pytest.mark.asyncio
async def test_guard_enforces_persistent_daily_limit(tmp_path) -> None:
    ledger = tmp_path / "usage.json"
    first = GuardedRemoteProvider(
        RecordingProvider(), name="groq:test", ledger_path=ledger, daily_request_limit=1
    )
    assert await first.generate("oi") == "remote"
    restarted = GuardedRemoteProvider(
        RecordingProvider(), name="groq:test", ledger_path=ledger, daily_request_limit=1
    )
    with pytest.raises(CloudUsageLimitError):
        await restarted.generate("outra")


@pytest.mark.asyncio
async def test_guard_opens_circuit_after_repeated_failures(tmp_path) -> None:
    guarded = GuardedRemoteProvider(
        RecordingProvider(fail=True),
        name="groq:test",
        ledger_path=tmp_path / "usage.json",
        failure_threshold=2,
        daily_request_limit=10,
    )
    with pytest.raises(RuntimeError):
        await guarded.generate("um")
    with pytest.raises(RuntimeError):
        await guarded.generate("dois")
    with pytest.raises(CircuitOpenError):
        await guarded.generate("tres")
