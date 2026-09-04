import sqlite3

from app.consumers import ConsumerStore
from app.knowledge.store import KnowledgeStore
from app.leads import LeadStore


def _plan(connection: sqlite3.Connection, sql: str, parameters: tuple[object, ...]) -> str:
    return " ".join(
        str(row[3])
        for row in connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters).fetchall()
    )


def test_lead_dashboard_and_due_action_queries_use_covering_indexes(tmp_path):
    store = LeadStore(tmp_path / "leads.db")

    unfiltered = _plan(
        store._connection,
        "SELECT * FROM leads ORDER BY score DESC, updated_at DESC LIMIT ?",
        (100,),
    )
    filtered = _plan(
        store._connection,
        "SELECT * FROM leads WHERE stage=? ORDER BY score DESC, updated_at DESC LIMIT ?",
        ("novo", 100),
    )
    due = _plan(
        store._connection,
        """SELECT * FROM leads WHERE next_action_at != '' AND next_action_at <= ?
           AND stage NOT IN ('convertido','perdido')
           ORDER BY next_action_at ASC, score DESC LIMIT ?""",
        ("2099-01-01T00:00:00+00:00", 100),
    )

    assert "idx_leads_score_updated" in unfiltered
    assert "idx_leads_stage_score_updated" in filtered
    assert "idx_leads_due_actions" in due
    store.close()


def test_consumer_listing_and_retention_queries_use_indexes(tmp_path):
    store = ConsumerStore(tmp_path / "consumers.db")

    listing = _plan(
        store._db,
        "SELECT * FROM consumer_people ORDER BY updated_at DESC LIMIT ?",
        (100,),
    )
    retention = _plan(
        store._db,
        "DELETE FROM consumer_people WHERE retained_until<>'' AND retained_until<=?",
        ("2099-01-01T00:00:00+00:00",),
    )

    assert "idx_consumer_people_updated" in listing
    assert "idx_consumer_people_retention" in retention
    store.close()


def test_knowledge_store_enforces_declared_foreign_keys(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")

    assert store._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with store._connection:
        try:
            store._connection.execute(
                """INSERT INTO chunks(document_id, chunk_index, content, chunk_hash)
                   VALUES (?, ?, ?, ?)""",
                (999, 0, "orphan", "orphan-hash"),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("an orphan chunk was accepted")
    store.close()
