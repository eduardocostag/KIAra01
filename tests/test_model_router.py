from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.observability import MetricsRegistry
from app.providers.llm import LLMProvider
from app.providers.router import LocalProfilePolicy, ModelRouter


class StubProvider(LLMProvider):
    def __init__(self, name: str, *, vision: bool = False, fails: bool = False) -> None:
        self.name, self.has_vision, self.fails = name, vision, fails

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate", "vision"} if self.has_vision else {"generate"})

    async def generate(self, prompt: str) -> str:
        if self.fails:
            raise RuntimeError("failure")
        return f"{self.name}:{prompt}"

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield self.name
        yield prompt

    async def vision_bytes(self, prompt: str, image: bytes, *, media_type="image/png") -> str:
        return f"{self.name}:{len(image)}:{media_type}:{prompt}"


@pytest.mark.asyncio
async def test_model_router_selects_fast_and_reasoning_deterministically():
    metrics = MetricsRegistry()
    router = ModelRouter(
        {"fast": StubProvider("fast"), "reasoning": StubProvider("reasoning")},
        metrics=metrics,
    )
    assert (await router.generate("Olá")) == "fast:Olá"
    assert (await router.generate("Analise esta arquitetura")) == "reasoning:Analise esta arquitetura"
    assert metrics.count("model_router.route.fast") == 1
    assert metrics.count("model_router.route.reasoning") == 1
    assert metrics.summary("model_router.latency.fast").count == 1


@pytest.mark.asyncio
async def test_internal_stage_can_explicitly_use_fast_profile():
    router = ModelRouter(
        {"fast": StubProvider("fast"), "reasoning": StubProvider("reasoning")}
    )

    answer = await router.generate_for_profile("fast", "Analise esta arquitetura")

    assert answer == "fast:Analise esta arquitetura"
    assert router.last_decision is not None
    assert router.last_decision.reason == "explicit_internal_stage"


def test_policy_reads_user_message_in_structured_specialist_prompt():
    policy = LocalProfilePolicy()
    decision = policy.select_text('{"role":"helpdesk","user_message":"diagnostique o erro"}')
    assert decision.profile == "reasoning"
    assert decision.reason == "complexity_marker"
    assert policy.select_text(
        '{"role":"generalista","user_message":"explique como funciona a memória"}'
    ).profile == "reasoning"
    assert policy.select_text(
        '{"user_message":"qual é a diferença entre memória RAM e armazenamento?"}'
    ).profile == "reasoning"
    assert policy.select_text(
        '{"user_message":"Quais hipóteses você investigaria neste diagnóstico?"}'
    ).profile == "reasoning"


@pytest.mark.asyncio
async def test_stream_and_vision_keep_provider_capabilities():
    router = ModelRouter(
        {
            "fast": StubProvider("fast"),
            "reasoning": StubProvider("reasoning"),
            "vision": StubProvider("vision", vision=True),
        }
    )
    assert [part async for part in router.stream("oi")] == ["fast", "oi"]
    assert "vision" in router.capabilities
    assert await router.vision_bytes("veja", b"123") == "vision:3:image/png:veja"


@pytest.mark.asyncio
async def test_errors_are_counted_and_propagated():
    metrics = MetricsRegistry()
    router = ModelRouter(
        {"fast": StubProvider("fast", fails=True), "reasoning": StubProvider("reasoning")},
        metrics=metrics,
    )
    with pytest.raises(RuntimeError, match="failure"):
        await router.generate("oi")
    assert metrics.count("model_router.error.fast") == 1


def test_profiles_are_explicitly_opt_in():
    with pytest.raises(ValueError, match="reasoning"):
        ModelRouter({"fast": StubProvider("fast")})
