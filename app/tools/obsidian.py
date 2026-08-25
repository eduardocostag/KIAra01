from __future__ import annotations

import asyncio
import re
import webbrowser
from datetime import UTC, datetime
from typing import Any

from app.integrations.obsidian import ObsidianVaultIndex
from app.knowledge import KnowledgeStore
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class SyncObsidianTool(Tool):
    name = "sync_obsidian"
    description = "Sincroniza notas autorizadas do Obsidian com a base local."
    permission_level = PermissionLevel.READ_ONLY

    def __init__(self, index: ObsidianVaultIndex) -> None:
        self.index = index

    async def execute(self, **_: Any) -> ToolResult:
        report = self.index.sync()
        return ToolResult(
            True,
            output=(
                f"Obsidian sincronizado: {report.indexed} atualizadas, "
                f"{report.unchanged} inalteradas e {report.removed} removidas."
            ),
        )


class SearchObsidianTool(Tool):
    name = "search_obsidian"
    description = "Pesquisa somente nas notas indexadas do Obsidian."
    permission_level = PermissionLevel.READ_ONLY

    def __init__(self, knowledge: KnowledgeStore) -> None:
        self.knowledge = knowledge

    async def execute(self, *, query: str, **_: Any) -> ToolResult:
        results = [
            item
            for item in self.knowledge.search(query, limit=20)
            if item.metadata.get("integration") == "obsidian"
        ][:5]
        if not results:
            return ToolResult(True, output="Nenhuma nota relevante encontrada no Obsidian.")
        lines = [
            f"- {item.metadata.get('relative_path')}: {item.content[:300]}\n"
            f"  {item.metadata.get('obsidian_uri')}"
            for item in results
        ]
        return ToolResult(True, output="Resultados do Obsidian:\n" + "\n".join(lines))


class OpenObsidianNoteTool(Tool):
    name = "open_obsidian_note"
    description = "Abre uma nota existente no Obsidian."
    permission_level = PermissionLevel.SAFE_ACTION

    def __init__(self, index: ObsidianVaultIndex) -> None:
        self.index = index

    async def execute(self, *, note: str, **_: Any) -> ToolResult:
        requested = note.strip().casefold().removesuffix(".md")
        matches = [
            path
            for path in self.index._markdown_files()
            if path.stem.casefold() == requested
            or path.relative_to(self.index.vault).as_posix().casefold().removesuffix(".md")
            == requested
        ]
        if len(matches) != 1:
            return ToolResult(False, error="Informe o nome exato de uma única nota.")
        relative = matches[0].relative_to(self.index.vault).as_posix()
        uri = self.index.note_uri(relative)
        opened = await asyncio.to_thread(webbrowser.open, uri)
        return ToolResult(bool(opened), output=f"Nota aberta: {relative}", metadata={"uri": uri})


class SaveObsidianNoteTool(Tool):
    name = "save_obsidian_note"
    description = "Salva uma nota no Obsidian somente após confirmação."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(self, index: ObsidianVaultIndex) -> None:
        self.index = index

    def validate(self, parameters: dict[str, Any]) -> None:
        content = str(parameters.get("content", "")).strip()
        if not content or len(content) > 20_000:
            raise ValueError("O conteúdo deve ter entre 1 e 20.000 caracteres.")

    async def execute(self, *, content: str, title: str | None = None, **_: Any) -> ToolResult:
        safe_title = re.sub(r'[<>:"/\\|?*]+', "-", title or "Nota da Kiara").strip(" .-")
        safe_title = safe_title[:100] or "Nota da Kiara"
        folder = self.index.vault / "00 - Caixa de entrada"
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / f"{safe_title}.md"
        if destination.exists():
            destination = folder / f"{safe_title} - {datetime.now(UTC):%Y%m%d-%H%M%S}.md"
        temporary = destination.with_suffix(".md.tmp")
        temporary.write_text(content.strip() + "\n", encoding="utf-8")
        temporary.replace(destination)
        self.index.sync()
        relative = destination.relative_to(self.index.vault).as_posix()
        return ToolResult(
            True,
            output=f"Nota salva: {relative}",
            metadata={"uri": self.index.note_uri(relative)},
        )
