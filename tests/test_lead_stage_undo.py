from concurrent.futures import ThreadPoolExecutor

from app.leads import LeadStage, LeadStore


def test_undo_last_stage_change_survives_restart_and_is_single_use(tmp_path) -> None:
    path = tmp_path / "leads.db"
    store = LeadStore(path)
    identifier = store.upsert(company="Clínica Horizonte", whatsapp="51999990000")
    assert store.update(identifier, stage=LeadStage.QUALIFIED)
    store.close()

    reopened = LeadStore(path)
    assert reopened.undo_last_stage_change(identifier)
    assert reopened.list()[0].stage is LeadStage.NEW
    assert not reopened.undo_last_stage_change(identifier)
    event = reopened._connection.execute(
        "SELECT * FROM lead_events WHERE lead_id=? ORDER BY id DESC LIMIT 1", (identifier,)
    ).fetchone()
    assert event["event_type"] == "stage_change_undone"
    assert event["from_stage"] == LeadStage.QUALIFIED.value
    assert event["to_stage"] == LeadStage.NEW.value
    assert '"compensates_event_id": 1' in event["payload"]
    reopened.close()


def test_undo_rejects_missing_history_and_divergent_current_stage(tmp_path) -> None:
    store = LeadStore(tmp_path / "leads.db")
    identifier = store.upsert(company="Empresa sem histórico")
    assert not store.undo_last_stage_change(identifier)
    assert not store.undo_last_stage_change("lead-inexistente")

    assert store.update(identifier, stage=LeadStage.CONTACTED)
    store._connection.execute(
        "UPDATE leads SET stage=?,updated_at=? WHERE id=?",
        (LeadStage.REPLIED.value, "versao-concorrente", identifier),
    )
    store._connection.commit()
    assert not store.undo_last_stage_change(identifier)
    assert store.list()[0].stage is LeadStage.REPLIED
    store.close()


def test_only_one_concurrent_store_can_compensate_the_transition(tmp_path) -> None:
    path = tmp_path / "leads.db"
    first = LeadStore(path)
    identifier = first.upsert(company="Empresa concorrente")
    assert first.update(identifier, stage=LeadStage.PROPOSAL)
    second = LeadStore(path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda store: store.undo_last_stage_change(identifier),
                                (first, second)))

    assert sorted(results) == [False, True]
    assert first.list()[0].stage is LeadStage.NEW
    count = first._connection.execute(
        "SELECT COUNT(*) FROM lead_events WHERE lead_id=? AND event_type='stage_change_undone'",
        (identifier,),
    ).fetchone()[0]
    assert count == 1
    first.close()
    second.close()
