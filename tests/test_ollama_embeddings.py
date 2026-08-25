from __future__ import annotations

import json

from app.memory.embeddings import OllamaEmbeddingProvider


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({"embeddings": [[1.0, 0.0], [0.0, 1.0]]}).encode()


def test_ollama_embedding_provider_batches_locally(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaEmbeddingProvider("embedding-model", timeout_seconds=12)

    assert provider.embed(["rede", "impressora"]) == [[1.0, 0.0], [0.0, 1.0]]
    body = json.loads(calls[0][0].data.decode())
    assert body == {"model": "embedding-model", "input": ["rede", "impressora"]}
    assert calls[0][0].full_url == "http://127.0.0.1:11434/api/embed"
    assert calls[0][1] == 12
