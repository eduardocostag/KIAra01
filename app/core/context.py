from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app.knowledge import KnowledgeStore
from app.memory import MemoryEngine, MemoryKind
from app.models import ScreenContext


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    content: str


class ConversationSession:
    """Bounded, deterministic conversation state owned by the core."""

    def __init__(
        self,
        *,
        max_recent_turns: int = 8,
        max_recent_chars: int = 8_000,
        max_summary_chars: int = 4_000,
    ) -> None:
        if max_recent_turns < 1 or max_recent_chars < 1 or max_summary_chars < 1:
            raise ValueError("Conversation limits must be positive")
        self.max_recent_turns = max_recent_turns
        self.max_recent_chars = max_recent_chars
        self.max_summary_chars = max_summary_chars
        self._recent: list[ConversationTurn] = []
        self._summary_lines: list[str] = []
        self._lock = threading.Lock()

    def record_exchange(self, user_message: str, assistant_message: str) -> None:
        turns = (
            ConversationTurn("user", self._normalize(user_message)),
            ConversationTurn("assistant", self._normalize(assistant_message)),
        )
        with self._lock:
            self._recent.extend(turn for turn in turns if turn.content)
            self._compact()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "summary": "\n".join(self._summary_lines),
                "recent_turns": [asdict(turn) for turn in self._recent],
            }

    def clear(self) -> None:
        with self._lock:
            self._recent.clear()
            self._summary_lines.clear()

    def _compact(self) -> None:
        while (
            len(self._recent) > self.max_recent_turns
            or sum(len(turn.content) for turn in self._recent) > self.max_recent_chars
        ):
            removed = self._recent.pop(0)
            label = "Usuário" if removed.role == "user" else "Kiara"
            self._summary_lines.append(f"{label}: {removed.content}")
        while len("\n".join(self._summary_lines)) > self.max_summary_chars:
            if len(self._summary_lines) > 1:
                self._summary_lines.pop(0)
            else:
                self._summary_lines[0] = self._summary_lines[0][-self.max_summary_chars :]

    @staticmethod
    def _normalize(content: str) -> str:
        return " ".join(content.split())


class ContextManager:
    def __init__(
        self,
        screen_reader: Callable[[], ScreenContext],
        memory: MemoryEngine | None = None,
        knowledge: KnowledgeStore | None = None,
        conversation: ConversationSession | None = None,
        knowledge_max_chars: int = 6_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._screen_reader = screen_reader
        self._memory = memory
        self._knowledge = knowledge
        self._conversation = conversation or ConversationSession()
        self._knowledge_max_chars = max(500, knowledge_max_chars)
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._recent_actions: list[dict[str, Any]] = []
        self._live_screen_understanding: dict[str, Any] | None = None
        self._live_screen_lock = threading.Lock()

    def update_live_screen_understanding(self, understanding: dict[str, Any] | None) -> None:
        """Keep only the latest semantic screen reading; pixels are never stored here."""
        with self._live_screen_lock:
            self._live_screen_understanding = dict(understanding) if understanding else None

    def live_screen_understanding(self) -> dict[str, Any] | None:
        with self._live_screen_lock:
            return (
                dict(self._live_screen_understanding)
                if self._live_screen_understanding is not None
                else None
            )

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

    def remember_exchange(self, user_message: str, assistant_message: str) -> None:
        self._conversation.record_exchange(user_message, assistant_message)

    def clear_conversation(self) -> None:
        self._conversation.clear()

    def remember_screen_context(
        self,
        user_message: str,
        application: str | None,
        window_title: str | None,
        visible_text: str | None,
    ) -> None:
        if self._memory is None:
            return
        summary = (
            f"Contexto de tela: usuário pediu '{user_message}'. "
            f"Aplicativo: {application or 'não identificado'}. "
            f"Janela: {window_title or 'sem título'}. "
            "O conteúdo textual visível foi tratado de forma efêmera e não foi persistido."
        )
        self._memory.remember(
            MemoryKind.WORKING,
            summary,
            metadata={
                "type": "screen_context",
                "application": application,
                "window_title": window_title,
                "visible_text_available": bool(visible_text),
            },
            importance=0.7,
        )

    def assemble(self, user_message: str) -> dict[str, Any]:
        current_screen = self.screen()
        relevant = []
        if self._memory is not None:
            relevant = [asdict(item) for item in self._memory.search(user_message)]
        knowledge = []
        if self._knowledge is not None:
            remaining = self._knowledge_max_chars
            for item in self._knowledge.search(user_message, limit=5):
                if remaining <= 0:
                    break
                payload = asdict(item)
                content = str(payload["content"])[:remaining]
                payload["content"] = content
                payload["trust"] = "untrusted_retrieved_content"
                knowledge.append(payload)
                remaining -= len(content)
        assembled = {
            "user_message": user_message,
            "runtime_facts": {
                "local_datetime": self._clock().isoformat(timespec="seconds"),
                "source": "trusted_system_clock",
            },
            "active_screen": asdict(current_screen),
            "recent_actions": list(self._recent_actions),
            "relevant_memories": relevant,
            "relevant_knowledge": knowledge,
        }
        conversation = self._conversation.snapshot()
        assembled["conversation_history"] = conversation["recent_turns"]
        if conversation["summary"]:
            assembled["conversation_summary"] = conversation["summary"]
        live_screen = self.live_screen_understanding()
        if live_screen is not None and self._matches_current_screen(live_screen, current_screen):
            assembled["live_screen_understanding"] = live_screen
        return assembled

    @staticmethod
    def _matches_current_screen(understanding: dict[str, Any], screen: ScreenContext) -> bool:
        return (
            understanding.get("application") == screen.active_application
            and understanding.get("window_title") == screen.window_title
        )
