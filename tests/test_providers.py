from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.factory import build_llm_provider
from app.providers.llm import LocalFallbackProvider
from app.providers.remote import OllamaProvider, OpenAIProvider, ProviderConfigurationError


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
