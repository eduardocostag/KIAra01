from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, ClassVar

from app.models import PermissionLevel, ToolResult
from app.personal import PersonalOrganizerStore
from app.tools.base import Tool


class AddPersonalTaskTool(Tool):
    name = "add_personal_task"
    description = "Adiciona uma tarefa pessoal local."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"title": {"type": "string"}, "due_at": {"type": ["string", "null"]}},
        "required": ["title"],
    }

    def __init__(self, store: PersonalOrganizerStore) -> None:
        self.store = store

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) - {"title", "due_at"} or "title" not in parameters:
            raise ValueError("Informe title e, opcionalmente, due_at.")
        if not isinstance(parameters["title"], str) or not parameters["title"].strip():
            raise ValueError("Título de tarefa inválido.")

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "title_chars": len(str(parameters.get("title", ""))),
            "due_at_provided": bool(parameters.get("due_at")),
        }

    async def execute(self, *, title: str, due_at: str | None = None, **_: Any) -> ToolResult:
        task = self.store.add_task(title, due_at)
        return ToolResult(
            True, output=f"Tarefa criada: {task.title} (ID {task.id[:8]}).", metadata=asdict(task)
        )


class ListPersonalTasksTool(Tool):
    name = "list_personal_tasks"
    description = "Lista tarefas pessoais pendentes."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {"properties": {}, "required": []}

    def __init__(self, store: PersonalOrganizerStore) -> None:
        self.store = store

    async def execute(self, **_: Any) -> ToolResult:
        tasks = self.store.list_tasks()
        lines = [
            f"{item.id[:8]} — {item.title}" + (f" — {item.due_at}" if item.due_at else "")
            for item in tasks
        ]
        return ToolResult(
            True,
            output="\n".join(lines) if lines else "Nenhuma tarefa pendente.",
            metadata={"items": [asdict(item) for item in tasks]},
        )


class CompletePersonalTaskTool(Tool):
    name = "complete_personal_task"
    description = "Marca uma tarefa pessoal como concluída."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    }

    def __init__(self, store: PersonalOrganizerStore) -> None:
        self.store = store

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"task_id"} or not isinstance(parameters["task_id"], str):
            raise ValueError("Informe somente task_id.")

    async def execute(self, *, task_id: str, **_: Any) -> ToolResult:
        matches = [item for item in self.store.list_tasks(limit=200) if item.id.startswith(task_id)]
        if len(matches) != 1 or not self.store.complete_task(matches[0].id):
            return ToolResult(False, error="Tarefa não encontrada ou ID ambíguo.")
        return ToolResult(True, output=f"Tarefa concluída: {matches[0].title}.")


class AddPersonalEventTool(Tool):
    name = "add_personal_event"
    description = "Adiciona compromisso ao calendário pessoal local."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "title": {"type": "string"},
            "start_at": {"type": "string"},
            "end_at": {"type": "string"},
            "location": {"type": ["string", "null"]},
        },
        "required": ["title", "start_at", "end_at"],
    }

    def __init__(self, store: PersonalOrganizerStore) -> None:
        self.store = store

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) - {"title", "start_at", "end_at", "location"}:
            raise ValueError("Parâmetros de evento desconhecidos.")
        if not all(isinstance(parameters.get(key), str) for key in ("title", "start_at", "end_at")):
            raise ValueError("Título, início e fim são obrigatórios.")

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "title_chars": len(str(parameters.get("title", ""))),
            "start_at": parameters.get("start_at"),
            "end_at": parameters.get("end_at"),
            "location_provided": bool(parameters.get("location")),
        }

    async def execute(self, **parameters: Any) -> ToolResult:
        event = self.store.add_event(**parameters)
        return ToolResult(
            True,
            output=f"Compromisso criado: {event.title}, {event.start_at}.",
            metadata=asdict(event),
        )


class ListPersonalEventsTool(Tool):
    name = "list_personal_events"
    description = "Lista os próximos compromissos pessoais locais."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "from_at": {"type": "string"},
            "to_at": {"type": ["string", "null"]},
        },
        "required": ["from_at"],
    }

    def __init__(self, store: PersonalOrganizerStore) -> None:
        self.store = store

    async def execute(self, *, from_at: str, to_at: str | None = None, **_: Any) -> ToolResult:
        events = self.store.list_events(from_at=from_at)
        if to_at:
            events = [item for item in events if item.start_at <= to_at]
        lines = [f"{item.start_at} — {item.title}" for item in events]
        return ToolResult(
            True,
            output="\n".join(lines) if lines else "Nenhum compromisso futuro.",
            metadata={"items": [asdict(item) for item in events]},
        )


class SearchPersonalFilesTool(Tool):
    name = "search_personal_files"
    description = "Busca arquivos por nome dentro de pastas pessoais autorizadas."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"],
    }
    EXCLUDED = frozenset({".git", ".venv", "node_modules", "__pycache__", "browser-profile"})

    def __init__(self, roots: list[Path]) -> None:
        self.roots = tuple(path.resolve() for path in roots if path.is_dir())

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) - {"query", "limit"} or "query" not in parameters:
            raise ValueError("Informe query e, opcionalmente, limit.")
        query = parameters["query"]
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 200:
            raise ValueError("Busca deve ter entre 2 e 200 caracteres.")

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "query_chars": len(str(parameters.get("query", ""))),
            "limit": parameters.get("limit", 20),
        }

    async def execute(self, *, query: str, limit: int = 20, **_: Any) -> ToolResult:
        needle = query.casefold().strip()
        maximum = min(100, max(1, int(limit)))
        matches: list[str] = []
        for root in self.roots:
            for current, directories, filenames in os.walk(root, followlinks=False):
                directories[:] = [
                    name
                    for name in directories
                    if name not in self.EXCLUDED and not name.startswith(".")
                ]
                for filename in filenames:
                    if filename.startswith(".") or needle not in filename.casefold():
                        continue
                    path = (Path(current) / filename).resolve()
                    if path.is_relative_to(root):
                        matches.append(str(path))
                    if len(matches) >= maximum:
                        break
                if len(matches) >= maximum:
                    break
            if len(matches) >= maximum:
                break
        return ToolResult(
            True,
            output="\n".join(matches) if matches else "Nenhum arquivo encontrado.",
            metadata={"count": len(matches)},
        )
