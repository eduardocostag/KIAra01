from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from app.knowledge import KnowledgeStore
from app.memory import MemoryEngine, MemoryKind
from app.models import ScreenContext


class ContextManager:
    def __init__(
        self,
        screen_reader: Callable[[], ScreenContext],
        memory: MemoryEngine | None = None,
        knowledge: KnowledgeStore | None = None,
    ) -> None:
        self._screen_reader = screen_reader
        self._memory = memory
        self._knowledge = knowledge
        self._recent_actions: list[dict[str, Any]] = []

    def screen(self) -> ScreenContext:
        return self._screen_reader()

    def remember_action(self, tool: str, success: bool) -> None:
        action = {"tool": tool, "success": success}
        self._recent_actions.append(action)
        del self._recent_actions[:-10]
        if self._memory is not None:
            self._memory.remember(
                MemoryKind.WORKING,
                f"Ferramenta {tool}: {'sucesso' if success else 'falha'}",
                metadata=action,
                importance=0.3,
            )

    def assemble(self, user_message: str) -> dict[str, Any]:
        relevant = []
        if self._memory is not None:
            relevant = [asdict(item) for item in self._memory.search(user_message, limit=5)]
        knowledge = []
        if self._knowledge is not None:
            knowledge = [
                {**asdict(item), "trust": "untrusted_retrieved_content"}
                for item in self._knowledge.search(user_message, limit=5)
            ]
        return {
            "user_message": user_message,
            "active_screen": asdict(self.screen()),
            "recent_actions": list(self._recent_actions),
            "relevant_memories": relevant,
            "relevant_knowledge": knowledge,
        }
