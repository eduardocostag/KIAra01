from __future__ import annotations

import asyncio
import json

from app.integrations.obsidian import ObsidianSyncService, ObsidianVaultIndex
from app.knowledge import KnowledgeStore
from app.tools.obsidian import SaveObsidianNoteTool, SearchObsidianTool, SyncObsidianTool


def test_indexes_vault_incrementally_with_obsidian_citations(tmp_path) -> None:
    vault = tmp_path / "Meu Vault"
    vault.mkdir()
    note = vault / "Helpdesk" / "Driver de áudio.md"
    note.parent.mkdir()
    note.write_text("# Driver\nReinstale o driver de áudio.", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")
    index = ObsidianVaultIndex(vault, store, tmp_path / "obsidian-state.json")

    first = index.sync()
    second = index.sync()
    result = store.search("reinstale driver áudio")[0]

    assert (first.indexed, second.unchanged) == (1, 1)
    assert result.metadata["integration"] == "obsidian"
    assert result.metadata["relative_path"] == "Helpdesk/Driver de áudio.md"
    assert result.metadata["obsidian_uri"].startswith("obsidian://open?vault=Meu%20Vault")
    assert "%2F" in result.metadata["obsidian_uri"]


def test_modified_and_deleted_notes_replace_stale_knowledge(tmp_path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "procedimento.md"
    note.write_text("procedimento antigo de roteador", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")
    index = ObsidianVaultIndex(vault, store, tmp_path / "state.json")
    index.sync()

    note.write_text("procedimento novo de impressora", encoding="utf-8")
    changed = index.sync()

    assert changed.indexed == 1
    assert all(
        "antigo" not in result.content for result in store.search("procedimento antigo roteador")
    )
    assert store.search("procedimento novo impressora")

    note.unlink()
    removed = index.sync()
    assert removed.removed == 1
    assert store.search("procedimento novo impressora") == []


def test_private_and_obsidian_internal_notes_are_not_indexed(tmp_path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "privada.md").write_text(
        "---\nkiara_index: false\n---\nsegredo privado", encoding="utf-8"
    )
    internal = vault / ".obsidian"
    internal.mkdir()
    (internal / "config.md").write_text("configuração interna", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")

    report = ObsidianVaultIndex(vault, store, tmp_path / "state.json").sync()

    assert report.private_skipped == 1
    assert store.document_count() == 0
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["files"] == {}


def test_rejects_missing_vault(tmp_path) -> None:
    store = KnowledgeStore(tmp_path / "knowledge.db")

    try:
        ObsidianVaultIndex(tmp_path / "missing", store, tmp_path / "state.json")
    except ValueError as error:
        assert "vault" in str(error).casefold()
    else:
        raise AssertionError("missing vault should be rejected")


def test_private_directory_is_excluded_without_frontmatter(tmp_path) -> None:
    vault = tmp_path / "vault"
    private = vault / "90 - Privado"
    private.mkdir(parents=True)
    (private / "senha.md").write_text("conteúdo confidencial", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")

    report = ObsidianVaultIndex(vault, store, tmp_path / "state.json").sync()

    assert report.scanned == 0
    assert store.document_count() == 0


async def test_sync_search_and_confirmable_save_tools(tmp_path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "rede.md").write_text("reinicie o roteador da sala", encoding="utf-8")
    store = KnowledgeStore(tmp_path / "knowledge.db")
    index = ObsidianVaultIndex(vault, store, tmp_path / "state.json")

    synced = await SyncObsidianTool(index).execute()
    searched = await SearchObsidianTool(store).execute(query="roteador sala")
    saved = await SaveObsidianNoteTool(index).execute(title="Nova solução", content="teste")

    assert synced.success
    assert "rede.md" in searched.output
    assert saved.success
    assert (vault / "00 - Caixa de entrada" / "Nova solução.md").exists()


async def test_automatic_sync_service_indexes_changes(tmp_path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    store = KnowledgeStore(tmp_path / "knowledge.db")
    index = ObsidianVaultIndex(vault, store, tmp_path / "state.json")
    service = ObsidianSyncService(index, interval_seconds=2)

    service.start()
    await asyncio.sleep(0)
    await service.stop()

    assert (tmp_path / "state.json").exists()
