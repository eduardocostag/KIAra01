from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.factory import build_llm_provider
from app.providers.llm import FallbackProvider, LLMProvider, LocalFallbackProvider
from app.providers.remote import (
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    ProviderConfigurationError,
)
from app.providers.router import ModelRouter


class FakeResponses:
    def __init__(self) -> None:
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="resposta")


@pytest.mark.asyncio
async def test_openai_text_and_vision_payloads_without_network(tmp_path: Path) -> None:
    responses = FakeResponses()
    provider = OpenAIProvider(
        "test-model", "test-key", client=SimpleNamespace(responses=responses)
    )
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    assert await provider.generate("olá") == "resposta"
    assert await provider.vision("descreva", image) == "resposta"
    assert provider.capabilities == frozenset({"generate", "vision"})
    assert responses.calls[0] == {"model": "test-model", "input": "olá"}
    image_url = responses.calls[1]["input"][0]["content"][1]["image_url"]
    assert image_url.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_ollama_uses_injected_transport_without_network(tmp_path: Path) -> None:
    calls = []

    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"response": "local"}

    provider = OllamaProvider(
        "llava",
        vision_enabled=True,
        generation_options={"temperature": 0.2, "num_ctx": 8192},
        keep_alive="10m",
        transport=transport,
    )
    image = tmp_path / "screen.png"
    image.write_bytes(b"png")

    assert await provider.generate("oi") == "local"
    assert await provider.vision("veja", image) == "local"
    assert calls[0][0] == "http://127.0.0.1:11434/api/generate"
    assert calls[0][1]["options"] == {"temperature": 0.2, "num_ctx": 8192}
    assert calls[0][1]["keep_alive"] == "10m"
    assert calls[1][0].endswith("/api/chat")
    assert calls[1][1]["messages"][0]["images"]
    assert "vision" in provider.capabilities


@pytest.mark.asyncio
async def test_openai_compatible_provider_supports_text_and_vision() -> None:
    calls = []

    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"choices": [{"message": {"content": "remoto"}}]}

    provider = OpenAICompatibleProvider(
        "llama-3.1-8b-instant", "test-key", "https://api.groq.com/openai/v1", transport=transport
    )
    assert await provider.generate("oi") == "remoto"
    assert await provider.vision_bytes("veja", b"png") == "remoto"
    assert calls[0][0].endswith("/chat/completions")
    assert calls[0][1]["max_tokens"] == 2048
    assert calls[1][1]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png")


@pytest.mark.asyncio
async def test_fallback_provider_uses_second_provider_after_failure() -> None:
    class Failing(LLMProvider):
        async def generate(self, _prompt):
            raise RuntimeError("limite")

    class Working(LLMProvider):
        async def generate(self, _prompt):
            return "fallback"

    assert await FallbackProvider([Failing(), Working()]).generate("oi") == "fallback"


@pytest.mark.asyncio
async def test_fallback_provider_streams_from_second_provider_before_any_delta() -> None:
    class Failing(LLMProvider):
        async def generate(self, _prompt):
            raise RuntimeError("limite")

        async def stream(self, _prompt):
            raise RuntimeError("limite")
            yield  # pragma: no cover

    class Working(LLMProvider):
        async def generate(self, _prompt):
            return "fallback"

        async def stream(self, _prompt):
            yield "fall"
            yield "back"

    chunks = [chunk async for chunk in FallbackProvider([Failing(), Working()]).stream("oi")]
    assert chunks == ["fall", "back"]


@pytest.mark.asyncio
async def test_injected_transports_keep_stream_generate_compatibility() -> None:
    ollama = OllamaProvider("local", transport=lambda *_: {"response": "inteira"})
    compatible = OpenAICompatibleProvider(
        "remote", "key", "https://example.test/v1",
        transport=lambda *_: {"choices": [{"message": {"content": "remota"}}]},
    )
    assert [part async for part in ollama.stream("oi")] == ["inteira"]
    assert [part async for part in compatible.stream("oi")] == ["remota"]


@pytest.mark.asyncio
async def test_ollama_can_use_a_separate_local_vision_model() -> None:
    calls = []

    def transport(url, payload, timeout):
        calls.append(payload)
        return {"response": "pixels analisados"}

    provider = OllamaProvider(
        "kiara-stable:latest",
        vision_enabled=True,
        vision_model="qwen2.5vl:3b",
        transport=transport,
    )

    assert await provider.vision_bytes("o que há?", b"png") == "pixels analisados"
    assert calls[0]["model"] == "qwen2.5vl:3b"
    assert calls[0]["messages"][0]["images"]


def test_factory_defaults_to_safe_local_provider() -> None:
    settings = Settings(raw={"llm": {"provider": "local"}}, root=Path.cwd())
    assert isinstance(build_llm_provider(settings, {}), LocalFallbackProvider)


def test_factory_never_reads_openai_secret_from_yaml() -> None:
    settings = Settings(
        raw={"llm": {"provider": "openai", "model": "test", "api_key": "yaml-secret"}},
        root=Path.cwd(),
    )
    with pytest.raises(ProviderConfigurationError, match="OPENAI_API_KEY"):
        build_llm_provider(settings, {})


def test_factory_rejects_unknown_provider() -> None:
    settings = Settings(raw={"llm": {"provider": "mystery"}}, root=Path.cwd())
    with pytest.raises(ProviderConfigurationError, match="desconhecido"):
        build_llm_provider(settings, {})


def test_factory_builds_opt_in_local_model_router() -> None:
    settings = Settings(
        raw={
            "llm": {
                "provider": "ollama",
                "model": "fast-default",
                "routing": {
                    "enabled": True,
                    "fast_model": "fast-local",
                    "reasoning_model": "reasoning-local",
                },
            }
        },
        root=Path.cwd(),
    )

    provider = build_llm_provider(settings, {})

    assert isinstance(provider, ModelRouter)
    assert provider.profiles["fast"].model == "fast-local"
    assert provider.profiles["reasoning"].model == "reasoning-local"


def test_factory_builds_hybrid_profiles_and_keeps_vision_local(tmp_path) -> None:
    settings = Settings(
        raw={
            "llm": {
                "provider": "ollama",
                "model": "local-fast",
                "vision_enabled": True,
                "vision_model": "local-vision",
                "routing": {
                    "enabled": True,
                    "mode": "hybrid",
                    "fast_model": "local-fast",
                    "reasoning_model": "local-reasoning",
                    "fast": {"provider": "groq", "model": "openai/gpt-oss-20b"},
                    "reasoning": {
                        "provider": "groq",
                        "model": "openai/gpt-oss-120b",
                    },
                },
            }
        },
        root=tmp_path,
    )

    provider = build_llm_provider(settings, {"GROQ_API_KEY": "test-key"})

    assert isinstance(provider, ModelRouter)
    assert isinstance(provider.profiles["fast"], FallbackProvider)
    assert isinstance(provider.profiles["reasoning"], FallbackProvider)
    assert isinstance(provider.profiles["vision"], OllamaProvider)
    assert "vision" in provider.capabilities


def test_factory_rejects_nonofficial_groq_endpoint() -> None:
    settings = Settings(
        raw={"llm": {"provider": "groq", "model": "openai/gpt-oss-120b"}},
        root=Path.cwd(),
    )
    with pytest.raises(ProviderConfigurationError, match="não autorizado"):
        build_llm_provider(
            settings,
            {"GROQ_API_KEY": "test-key", "KIARA_LLM_BASE_URL": "https://evil.test/v1"},
        )


@pytest.mark.parametrize(
    ("provider_name", "model", "key_name", "expected_host"),
    [
        (
            "nvidia",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "NVIDIA_API_KEY",
            "integrate.api.nvidia.com",
        ),
        ("antling", "Ling-3.0-flash", "ANT_LING_API_KEY", "api.ant-ling.com"),
        ("tokenra", "stealth/ox-alpha", "TOKENRA_API_KEY", "tokenra.io"),
        (
            "vercel-gateway",
            "inclusionai/ling-3.0-flash",
            "AI_GATEWAY_API_KEY",
            "ai-gateway.vercel.sh",
        ),
    ],
)
def test_factory_builds_verified_free_tier_compatible_providers(
    provider_name, model, key_name, expected_host
) -> None:
    settings = Settings(
        raw={"llm": {"provider": provider_name, "model": model}},
        root=Path.cwd(),
    )

    provider = build_llm_provider(settings, {key_name: "test-key"})

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == model
    assert expected_host in provider.base_url


def test_hybrid_candidates_skip_missing_keys_and_preserve_declared_order(tmp_path) -> None:
    settings = Settings(
        raw={
            "llm": {
                "provider": "ollama",
                "model": "local",
                "routing": {
                    "enabled": True,
                    "mode": "hybrid",
                    "fast_model": "local",
                    "reasoning_model": "local",
                    "fast": {
                        "candidates": [
                            {"provider": "antling", "model": "Ling-3.0-flash"},
                            {
                                "provider": "nvidia",
                                "model": "nvidia/nemotron-3-ultra-550b-a55b",
                            },
                        ]
                    },
                    "reasoning": {
                        "candidates": [
                            {
                                "provider": "nvidia",
                                "model": "nvidia/nemotron-3-ultra-550b-a55b",
                            }
                        ]
                    },
                },
            }
        },
        root=tmp_path,
    )

    router = build_llm_provider(
        settings, {"NEMOTRON_3_ULTRA_550B_API_KEY": "test-key"}
    )

    assert isinstance(router, ModelRouter)
    fast = router.profiles["fast"]
    assert isinstance(fast, FallbackProvider)
    assert fast.providers[0].name.startswith("nvidia:")
    assert isinstance(fast.providers[-1], OllamaProvider)


def test_one_openrouter_key_activates_all_declared_models(tmp_path) -> None:
    models = [
        "inclusionai/ling-3.0-flash",
        "stealth/ox-alpha",
        "nvidia/nemotron-3-ultra-550b-a55b",
    ]
    settings = Settings(
        raw={
            "llm": {
                "provider": "ollama",
                "model": "local",
                "routing": {
                    "enabled": True,
                    "mode": "hybrid",
                    "fast_model": "local",
                    "reasoning_model": "local",
                    "fast": {
                        "candidates": [
                            {"provider": "openrouter", "model": model}
                            for model in models
                        ]
                    },
                    "reasoning": {"candidates": []},
                },
            }
        },
        root=tmp_path,
    )

    router = build_llm_provider(settings, {"OPENROUTER_API_KEY": "test-key"})

    assert isinstance(router, ModelRouter)
    fast = router.profiles["fast"]
    assert isinstance(fast, FallbackProvider)
    assert [provider.name for provider in fast.providers[:-1]] == [
        f"openrouter:{model}" for model in models
    ]
    assert isinstance(fast.providers[-1], OllamaProvider)


def test_shipped_config_uses_capability_first_fallback_order() -> None:
    import yaml

    raw = yaml.safe_load((Path.cwd() / "config" / "kiara.yaml").read_text(encoding="utf-8"))
    expected = [
        ("nvidia", "nvidia/nemotron-3-ultra-550b-a55b"),
        ("nvidia", "nvidia/nemotron-3-super-120b-a12b"),
        ("gemini", "gemini-3.1-flash-lite"),
        ("openrouter", "openrouter/free"),
    ]
    for profile in ("fast", "reasoning"):
        candidates = raw["llm"]["routing"][profile]["candidates"]
        assert [(item["provider"], item["model"]) for item in candidates] == expected
    assert "Nvidia" in (Path.cwd() / "scripts" / "configure_cloud_ai.ps1").read_text(
        encoding="utf-8"
    )
