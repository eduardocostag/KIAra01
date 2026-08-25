from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from app.core.context import ContextManager, ConversationSession
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


def test_context_manager_remembers_desktop_screen_context_for_session_memory(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    context = ContextManager(
        lambda: ScreenContext(active_application="Google Chrome", window_title="Dashboard"),
        engine,
    )
    context.remember_screen_context(
        "olha minha tela",
        "Google Chrome",
        "Dashboard",
        "Relatório de vendas",
    )
    records = engine.search("Dashboard", kinds=[MemoryKind.WORKING])
    assert records
    assert any("Dashboard" in record.content for record in records)
    assert all("Relatório de vendas" not in record.content for record in records)
    assert all("visible_text" not in record.metadata for record in records)
    assert records[0].metadata["visible_text_available"] is True


def test_context_drops_live_understanding_after_active_window_changes() -> None:
    current = ScreenContext(active_application="Editor", window_title="Arquivo")
    context = ContextManager(lambda: current)
    context.update_live_screen_understanding(
        {
            "application": "Editor",
            "window_title": "Arquivo",
            "summary": "Erro visível",
        }
    )

    assert "live_screen_understanding" in context.assemble("ajude")
    current.window_title = "Outra janela"
    assert "live_screen_understanding" not in context.assemble("continue")


def test_context_includes_trusted_current_local_datetime() -> None:
    fixed = datetime(2026, 8, 25, 14, 30, tzinfo=timezone(timedelta(hours=-3)))
    context = ContextManager(lambda: ScreenContext(), clock=lambda: fixed)

    runtime = context.assemble("que dia é hoje")["runtime_facts"]

    assert runtime == {
        "local_datetime": "2026-08-25T14:30:00-03:00",
        "source": "trusted_system_clock",
    }


def test_configurable_working_ttl_and_default_retrieval_limit(tmp_path) -> None:
    engine = MemoryEngine(
        tmp_path / "memory.db",
        default_ttl={MemoryKind.WORKING: timedelta(hours=2)},
        retrieval_limit=2,
    )
    identifiers = [
        engine.remember(MemoryKind.WORKING, f"registro configurado {index}")
        for index in range(3)
    ]

    records = engine.search("registro configurado")

    assert len(records) == 2
    all_records = {record.id: record for record in engine.list_records()}
    expected_expiry = all_records[identifiers[0]].created_at + timedelta(hours=2)
    assert all_records[identifiers[0]].expires_at == expected_expiry


def test_conversation_session_keeps_recent_turns_and_summarizes_evicted_ones() -> None:
    session = ConversationSession(max_recent_turns=2, max_recent_chars=100, max_summary_chars=100)
    context = ContextManager(lambda: ScreenContext(), conversation=session)

    context.remember_exchange("primeira pergunta", "primeira resposta")
    context.remember_exchange("segunda pergunta", "segunda resposta")

    assembled = context.assemble("continue")
    assert assembled["conversation_history"] == [
        {"role": "user", "content": "segunda pergunta"},
        {"role": "assistant", "content": "segunda resposta"},
    ]
    assert assembled["conversation_summary"] == (
        "Usuário: primeira pergunta\nKiara: primeira resposta"
    )


def test_conversation_session_applies_deterministic_character_limits() -> None:
    session = ConversationSession(max_recent_turns=10, max_recent_chars=8, max_summary_chars=12)
    session.record_exchange("abcde", "fghij")

    snapshot = session.snapshot()
    assert snapshot["recent_turns"] == [{"role": "assistant", "content": "fghij"}]
    assert len(snapshot["summary"]) <= 12
    assert snapshot["summary"].endswith("abcde")
