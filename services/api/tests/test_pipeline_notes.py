from __future__ import annotations

import pytest
from pydantic import ValidationError

from kiara_api.adapters.pipeline_memory import InMemoryPipelineRepository
from kiara_api.http.routes.pipeline import PipelineUpdate


@pytest.mark.asyncio
async def test_notes_are_saved_on_the_consumer_and_isolated_by_organization() -> None:
    entries = [
        {
            "id": "entry-a",
            "organization_id": "org-a",
            "consumer": {"id": "consumer-a", "display_name": "Cliente A", "instagram_username": None},
            "stage": "new",
            "next_action": None,
            "version": 1,
            "updated_at": "2026-09-23T12:00:00Z",
        },
        {
            "id": "entry-b",
            "organization_id": "org-b",
            "consumer": {"id": "consumer-b", "display_name": "Cliente B", "instagram_username": None},
            "stage": "new",
            "next_action": None,
            "version": 1,
            "updated_at": "2026-09-23T12:00:00Z",
        },
    ]
    repository = InMemoryPipelineRepository(entries)

    outcome, saved = await repository.update_entry("org-a", "entry-a", "notes-save-00001", 1, {"notes": "  Retornar sexta.  "})

    assert outcome == "updated"
    assert saved is not None
    assert saved["consumer"]["notes"] == "Retornar sexta."
    assert saved["version"] == 2
    assert (await repository.list_entries("org-b"))[0]["consumer"].get("notes") is None


@pytest.mark.asyncio
async def test_notes_can_be_cleared_without_changing_other_consumer_fields() -> None:
    entries = [{
        "id": "entry-a",
        "organization_id": "org-a",
        "consumer": {"id": "consumer-a", "display_name": "Cliente A", "instagram_username": "cliente.a", "notes": "Antiga"},
        "stage": "qualified",
        "next_action": "Ligar",
        "version": 3,
        "updated_at": "2026-09-23T12:00:00Z",
    }]
    repository = InMemoryPipelineRepository(entries)

    _, saved = await repository.update_entry("org-a", "entry-a", "notes-clear-0001", 3, {"notes": None})

    assert saved is not None
    assert saved["consumer"]["notes"] is None
    assert saved["consumer"]["instagram_username"] == "cliente.a"
    assert saved["stage"] == "qualified"
    assert saved["next_action"] == "Ligar"


def test_notes_have_a_server_side_length_limit() -> None:
    with pytest.raises(ValidationError):
        PipelineUpdate(notes="x" * 5001)
