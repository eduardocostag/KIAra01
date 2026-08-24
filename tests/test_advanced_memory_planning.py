from __future__ import annotations

import sqlite3
import threading

import pytest

from app.memory import MemoryEngine, MemoryKind, MemoryProfile
from app.planning import GoalStatus, PlanStep, PlanStore, TaskPlan


def test_memory_profiles_revision_provenance_and_explanation(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    old = engine.remember(MemoryKind.PREFERENCE, "Tema claro", profile=MemoryProfile.WORK,
                          provenance="settings")
    new = engine.revise(old, "Tema escuro")
    results = engine.search("tema", profile=MemoryProfile.WORK)
    assert [item.id for item in results] == [new]
    assert results[0].version == 2
    assert results[0].parent_id == old
    assert results[0].provenance == "user_correction"
    assert results[0].retrieval_explanation["total"] == results[0].score
    assert engine.search("tema", profile=MemoryProfile.PERSONAL) == []


def test_safe_consolidation_preserves_sources_as_version_history(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    first = engine.remember(MemoryKind.FACT, "Projeto usa Python", profile=MemoryProfile.WORK)
    second = engine.remember(MemoryKind.FACT, "Projeto usa SQLite", profile=MemoryProfile.WORK)
    consolidated = engine.consolidate([first, second], "Projeto usa Python e SQLite")
    active = engine.search("Projeto", profile=MemoryProfile.WORK)
    assert [item.id for item in active] == [consolidated]
    records = {item.id: item for item in engine.list_records()}
    assert records[first].superseded_by == consolidated
    assert records[second].superseded_by == consolidated


def test_v1_database_is_migrated_without_data_loss(tmp_path) -> None:
    path = tmp_path / "memory.db"
    connection = sqlite3.connect(path)
    connection.executescript("""
      CREATE TABLE memories (id INTEGER PRIMARY KEY, kind TEXT NOT NULL
      CHECK(kind IN ('working','episodic','semantic','preference','project')),
      content TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', importance REAL NOT NULL,
      created_at TEXT NOT NULL, accessed_at TEXT NOT NULL, expires_at TEXT, embedding TEXT);
      INSERT INTO memories VALUES(1,'semantic','legado','{}',.5,
      '2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00',NULL,NULL);
    """)
    connection.close()
    engine = MemoryEngine(path)
    assert engine.list_records()[0].content == "legado"
    assert engine.remember(MemoryKind.DOCUMENT, "novo") == 2


def test_memory_shared_connection_serializes_ui_and_core_threads(tmp_path) -> None:
    engine = MemoryEngine(tmp_path / "memory.db")
    errors: list[Exception] = []

    def worker(identifier: int) -> None:
        try:
            for index in range(30):
                engine.remember(MemoryKind.FACT, f"{identifier}-{index}")
                engine.search(str(index), limit=2)
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - capture thread failures
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(identifier,)) for identifier in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert engine.count() == 120


def test_v2_database_is_not_remigrated_on_reopen(tmp_path) -> None:
    path = tmp_path / "memory.db"
    engine = MemoryEngine(path)
    original = engine.remember(
        MemoryKind.PREFERENCE,
        "Tema claro",
        profile=MemoryProfile.WORK,
        provenance="settings",
    )
    revised = engine.revise(original, "Tema escuro")
    engine.close()

    reopened = MemoryEngine(path)
    records = {item.id: item for item in reopened.list_records()}
    assert records[original].superseded_by == revised
    assert records[revised].profile is MemoryProfile.WORK
    assert records[revised].version == 2
    assert records[revised].parent_id == original
    assert records[revised].provenance == "user_correction"


def test_plan_store_persists_pause_resume_and_checkpoint(tmp_path) -> None:
    path = tmp_path / "plans.db"
    plan = TaskPlan("objetivo longo", (PlanStep("read", {}, {"output_contains": "ok"}),))
    store = PlanStore(path)
    identifier = store.create(plan, risk="low", estimated_cost=1.5, estimated_duration_seconds=30)
    store.set_status(identifier, GoalStatus.RUNNING)
    store.checkpoint(identifier, 1, {"validated": True})
    store.set_status(identifier, GoalStatus.PAUSED)
    store.close()

    reopened = PlanStore(path)
    recovered = reopened.get(identifier)
    assert recovered is not None and recovered.status is GoalStatus.PAUSED
    assert recovered.next_step == 1 and recovered.estimated_cost == 1.5
    reopened.set_status(identifier, GoalStatus.RUNNING)
    reopened.set_status(identifier, GoalStatus.COMPLETED)
    with pytest.raises(ValueError):
        reopened.set_status(identifier, GoalStatus.RUNNING)
