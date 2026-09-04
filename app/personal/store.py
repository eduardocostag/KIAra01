from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PersonalTask:
    id: str
    title: str
    due_at: str | None
    completed: bool
    created_at: str


@dataclass(frozen=True, slots=True)
class PersonalEvent:
    id: str
    title: str
    start_at: str
    end_at: str
    location: str | None
    created_at: str


class PersonalOrganizerStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS personal_tasks(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, due_at TEXT,
              completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_personal_tasks_due ON personal_tasks(completed,due_at);
            CREATE TABLE IF NOT EXISTS personal_events(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, start_at TEXT NOT NULL,
              end_at TEXT NOT NULL, location TEXT, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_personal_events_start ON personal_events(start_at);
            """
        )
        self._db.commit()

    def add_task(self, title: str, due_at: str | None = None) -> PersonalTask:
        clean_title = " ".join(title.split())[:500]
        if not clean_title:
            raise ValueError("A tarefa precisa de um título.")
        due = self._optional_datetime(due_at)
        identifier = str(uuid.uuid4())
        created = datetime.now(UTC).isoformat()
        self._db.execute(
            "INSERT INTO personal_tasks(id,title,due_at,completed,created_at) VALUES(?,?,?,0,?)",
            (identifier, clean_title, due, created),
        )
        self._db.commit()
        return PersonalTask(identifier, clean_title, due, False, created)

    def list_tasks(self, *, include_completed: bool = False, limit: int = 50) -> list[PersonalTask]:
        where = "" if include_completed else "WHERE completed=0"
        rows = self._db.execute(
            f"SELECT * FROM personal_tasks {where} "
            "ORDER BY due_at IS NULL,due_at,created_at LIMIT ?",
            (min(200, max(1, limit)),),
        ).fetchall()
        return [
            PersonalTask(
                row["id"], row["title"], row["due_at"], bool(row["completed"]), row["created_at"]
            )
            for row in rows
        ]

    def complete_task(self, identifier: str) -> bool:
        cursor = self._db.execute(
            "UPDATE personal_tasks SET completed=1 WHERE id=? AND completed=0",
            (identifier,),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def add_event(
        self, title: str, start_at: str, end_at: str, location: str | None = None
    ) -> PersonalEvent:
        clean_title = " ".join(title.split())[:500]
        start = self._required_datetime(start_at)
        end = self._required_datetime(end_at)
        if not clean_title or datetime.fromisoformat(end) <= datetime.fromisoformat(start):
            raise ValueError("Evento inválido: confira título, início e fim.")
        clean_location = " ".join((location or "").split())[:300] or None
        identifier = str(uuid.uuid4())
        created = datetime.now(UTC).isoformat()
        self._db.execute(
            "INSERT INTO personal_events(id,title,start_at,end_at,location,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (identifier, clean_title, start, end, clean_location, created),
        )
        self._db.commit()
        return PersonalEvent(identifier, clean_title, start, end, clean_location, created)

    def list_events(self, *, from_at: str, limit: int = 50) -> list[PersonalEvent]:
        start = self._required_datetime(from_at)
        rows = self._db.execute(
            "SELECT * FROM personal_events WHERE end_at>=? ORDER BY start_at LIMIT ?",
            (start, min(200, max(1, limit))),
        ).fetchall()
        return [
            PersonalEvent(
                row["id"],
                row["title"],
                row["start_at"],
                row["end_at"],
                row["location"],
                row["created_at"],
            )
            for row in rows
        ]

    def close(self) -> None:
        self._db.close()

    @classmethod
    def _optional_datetime(cls, value: str | None) -> str | None:
        return cls._required_datetime(value) if value else None

    @staticmethod
    def _required_datetime(value: str | None) -> str:
        if not value:
            raise ValueError("Data e hora são obrigatórias.")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Data e hora precisam de fuso horário.")
        return parsed.isoformat(timespec="minutes")
