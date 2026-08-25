from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ConversationStore:
    """Small local JSON store for chat threads, independent from semantic memory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"conversations": []}
        self._load()
        if not self._data["conversations"]:
            self.create("Nova conversa")

    def list(self) -> list[dict[str, Any]]:
        return list(self._data["conversations"])

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        return next(
            (item for item in self._data["conversations"] if item["id"] == conversation_id),
            None,
        )

    def create(self, title: str = "Nova conversa") -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        conversation = {
            "id": f"conversation-{int(datetime.now(UTC).timestamp() * 1_000_000)}",
            "title": title,
            "updated_at": now,
            "messages": [],
        }
        self._data["conversations"].insert(0, conversation)
        self._save()
        return conversation

    def add_message(self, conversation_id: str, author: str, text: str) -> None:
        conversation = self.get(conversation_id)
        if conversation is None:
            return
        clean = text.strip()
        if not clean:
            return
        conversation["messages"].append(
            {"author": author, "text": clean, "created_at": datetime.now(UTC).isoformat()}
        )
        if conversation["title"] == "Nova conversa" and author == "Você":
            conversation["title"] = clean[:42]
        conversation["updated_at"] = datetime.now(UTC).isoformat()
        self._data["conversations"].sort(
            key=lambda item: item.get("updated_at", ""), reverse=True
        )
        self._save()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("conversations"), list):
                self._data = payload
        except (OSError, ValueError, TypeError):
            self._data = {"conversations": []}

    def _save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)
