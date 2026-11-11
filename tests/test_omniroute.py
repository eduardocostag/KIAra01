from __future__ import annotations

import json

import pytest

from app.providers.omniroute import OmniRouteProvider
from app.providers.remote import ProviderConfigurationError


@pytest.mark.parametrize("url", [
    "http://example.test/v1", "https://secret@example.test/v1",
    "https://example.test/v1?key=secret", "file:///v1",
    "http://localhost:20128/home", "http://localhost:20128/v1#token",
    "http://localhost:70000/v1", "http://localhost:bad/v1",
])
def test_rejects_unsafe_endpoint_without_network(url):
    with pytest.raises(ProviderConfigurationError):
        OmniRouteProvider("test-key", "selected-model", base_url=url)


@pytest.mark.parametrize(("key", "model"), [("", "selected"), (" ", "selected"), ("key", ""), ("key", " ")])
def test_requires_explicit_credentials_and_model(key, model):
    with pytest.raises(ProviderConfigurationError):
        OmniRouteProvider(key, model)


@pytest.mark.asyncio
async def test_text_contract_preserves_roles_and_bounded_generation():
    calls = []

    def transport(url, payload, timeout):
        calls.append((url, payload, timeout))
        return {"choices": [{"message": {"content": json.dumps({"text": "Resposta fictícia", "handoff": True})}}]}

    provider = OmniRouteProvider("test-key", "selected-free-combo", transport=transport, max_output_tokens=300)
    messages = [{"role": "system", "content": "Somente fatos cadastrados."}, {"role": "user", "content": "Quanto custa?"}]
    result = await provider.chat(messages)
    assert json.loads(result)["handoff"] is True
    url, payload, timeout = calls[0]
    assert url == "http://127.0.0.1:20128/v1/chat/completions"
    assert payload == {"model": "selected-free-combo", "messages": messages, "stream": False, "max_tokens": 300}
    assert timeout == 45
    assert provider.capabilities == frozenset({"generate"})
    assert provider.follow_redirects is False


@pytest.mark.asyncio
async def test_chat_rejects_tool_roles_and_non_text_before_network():
    calls = []
    provider = OmniRouteProvider("key", "selected", transport=lambda *args: calls.append(args))
    for messages in ([], [{"role": "tool", "content": "secret"}], [{"role": "user", "content": [{"type": "image_url"}]}]):
        with pytest.raises(ValueError):
            await provider.chat(messages)
    assert not calls


@pytest.mark.asyncio
async def test_malformed_completion_fails_closed():
    provider = OmniRouteProvider("key", "selected", transport=lambda *_: {"choices": []})
    with pytest.raises(RuntimeError):
        await provider.generate("synthetic")
