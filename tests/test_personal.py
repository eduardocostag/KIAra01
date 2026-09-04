from datetime import UTC, datetime, timedelta

import pytest

from app.personal import PersonalOrganizerStore
from app.tools.personal import (
    AddPersonalEventTool,
    AddPersonalTaskTool,
    CompletePersonalTaskTool,
    SearchPersonalFilesTool,
)


def test_personal_tasks_persist_and_complete(tmp_path) -> None:
    path = tmp_path / "personal.db"
    store = PersonalOrganizerStore(path)
    task = store.add_task("  Comprar   leite  ")
    store.close()

    reopened = PersonalOrganizerStore(path)
    assert reopened.list_tasks()[0].title == "Comprar leite"
    assert reopened.complete_task(task.id)
    assert reopened.list_tasks() == []
    reopened.close()


def test_personal_events_require_timezone_and_valid_range(tmp_path) -> None:
    store = PersonalOrganizerStore(tmp_path / "personal.db")
    with pytest.raises(ValueError, match="fuso"):
        store.add_event("Consulta", "2026-09-01T14:00", "2026-09-01T15:00")
    with pytest.raises(ValueError, match="Evento"):
        store.add_event("Consulta", "2026-09-01T15:00-03:00", "2026-09-01T14:00-03:00")
    store.close()


@pytest.mark.asyncio
async def test_personal_tools_manage_tasks_and_events(tmp_path) -> None:
    store = PersonalOrganizerStore(tmp_path / "personal.db")
    created = await AddPersonalTaskTool(store).execute(title="Revisar proposta")
    prefix = str(created.metadata["id"])[:8]
    completed = await CompletePersonalTaskTool(store).execute(task_id=prefix)
    assert completed.success

    start = datetime.now(UTC) + timedelta(days=1)
    event = await AddPersonalEventTool(store).execute(
        title="Reunião",
        start_at=start.isoformat(),
        end_at=(start + timedelta(hours=1)).isoformat(),
    )
    assert event.success
    store.close()


@pytest.mark.asyncio
async def test_file_search_is_name_only_and_stays_in_allowed_root(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    hidden = allowed / ".hidden"
    outside = tmp_path / "outside"
    allowed.mkdir()
    hidden.mkdir()
    outside.mkdir()
    (allowed / "contrato-cliente.pdf").write_text("segredo", encoding="utf-8")
    (allowed / "outro.txt").write_text("contrato no conteúdo", encoding="utf-8")
    (hidden / "contrato-oculto.txt").write_text("x", encoding="utf-8")
    (outside / "contrato-fora.txt").write_text("x", encoding="utf-8")

    result = await SearchPersonalFilesTool([allowed]).execute(query="contrato")
    assert result.success
    assert "contrato-cliente.pdf" in result.output
    assert "outro.txt" not in result.output
    assert "contrato-oculto.txt" not in result.output
    assert "contrato-fora.txt" not in result.output


def test_personal_audit_parameters_do_not_expose_private_text(tmp_path) -> None:
    store = PersonalOrganizerStore(tmp_path / "personal.db")
    task_audit = AddPersonalTaskTool(store).audit_parameters({"title": "Consulta médica"})
    file_audit = SearchPersonalFilesTool([tmp_path]).audit_parameters({"query": "imposto-renda"})
    assert "Consulta" not in str(task_audit)
    assert "imposto" not in str(file_audit)
    store.close()
