from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.context import ContextManager
from app.memory import MemoryEngine, MemoryKind
from app.models import ScreenContext


def test_all_memory_kinds_and_metadata_are_persisted(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    for kind in MemoryKind:
        engine.remember(kind, f"conteúdo {kind.value}", metadata={"source": "test"})
    results = engine.search("conteúdo", limit=10)
    assert {item.kind for item in results} == set(MemoryKind)
    assert all(item.metadata == {"source": "test"} for item in results)
    engine.close()


def test_lexical_relevance_importance_and_recency_rank_results(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    engine.remember(MemoryKind.SEMANTIC, "Python usa tipagem dinâmica", importance=0.9)
    engine.remember(MemoryKind.SEMANTIC, "Receita de bolo", importance=1.0)
    results = engine.search("tipagem Python")
    assert results[0].content == "Python usa tipagem dinâmica"
    assert results[0].score > results[1].score


def test_expired_memories_are_hidden_and_purged(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    past = datetime.now(UTC) - timedelta(seconds=1)
    identifier = engine.remember(MemoryKind.EPISODIC, "já expirou", expires_at=past)
    assert engine.search("expirou") == []
    assert engine.purge_expired() == 1
    assert engine.forget(identifier) is False


class TinyEmbeddings:
    def embed(self, texts):
        return [[1.0, 0.0] if "gato" in text else [0.0, 1.0] for text in texts]


def test_embedding_provider_is_optional_and_contributes_to_score(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db", embedding_provider=TinyEmbeddings())
    engine.remember(MemoryKind.SEMANTIC, "gato")
    engine.remember(MemoryKind.SEMANTIC, "cão")
    assert engine.search("gato")[0].content == "gato"


def test_context_manager_surfaces_relevant_memory(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    engine.remember(MemoryKind.PREFERENCE, "Prefere tema escuro", importance=0.9)
    context = ContextManager(lambda: ScreenContext(), engine)
    assembled = context.assemble("Qual tema eu prefiro?")
    assert assembled["relevant_memories"][0]["content"] == "Prefere tema escuro"
    context.remember_action("open_url", True)
    assert engine.search("open_url", kinds=[MemoryKind.WORKING])
