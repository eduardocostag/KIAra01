from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.planning.models import GoalStatus, PersistentGoal, PlanStep, TaskPlan


class PlanStore:
    """Crash-safe journal for bounded, explicitly resumable goals."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY, goal TEXT NOT NULL,
              plan TEXT NOT NULL, status TEXT NOT NULL, next_step INTEGER NOT NULL DEFAULT 0,
              risk TEXT NOT NULL, estimated_cost REAL NOT NULL,
              estimated_duration_seconds INTEGER NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS goal_observations (id INTEGER PRIMARY KEY,
              goal_id INTEGER NOT NULL, step_index INTEGER NOT NULL, observation TEXT NOT NULL,
              created_at TEXT NOT NULL, FOREIGN KEY(goal_id) REFERENCES goals(id));
        """)
        self._connection.commit()

    def create(
        self,
        plan: TaskPlan,
        *,
        risk: str,
        estimated_cost: float = 0,
        estimated_duration_seconds: int = 0,
    ) -> int:
        if (
            risk not in {"low", "medium", "high"}
            or estimated_cost < 0
            or estimated_duration_seconds < 0
        ):
            raise ValueError("Invalid goal estimate")
        now = datetime.now(UTC).isoformat()
        payload = {
            "goal": plan.goal,
            "specialists": list(plan.specialists),
            "steps": [asdict(step) for step in plan.steps],
        }
        cursor = self._connection.execute(
            "INSERT INTO goals(goal,plan,status,risk,estimated_cost,estimated_duration_seconds,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                plan.goal,
                json.dumps(payload, ensure_ascii=False),
                GoalStatus.PENDING.value,
                risk,
                estimated_cost,
                estimated_duration_seconds,
                now,
                now,
            ),
        )
        self._connection.commit()
        return int(cursor.lastrowid)

    def get(self, identifier: int) -> PersistentGoal | None:
        row = self._connection.execute("SELECT * FROM goals WHERE id=?", (identifier,)).fetchone()
        if row is None:
            return None
        payload = json.loads(row["plan"])
        plan = TaskPlan(
            payload["goal"],
            tuple(PlanStep(**step) for step in payload["steps"]),
            tuple(payload["specialists"]),
        )
        return PersistentGoal(
            int(row["id"]),
            str(row["goal"]),
            plan,
            GoalStatus(row["status"]),
            int(row["next_step"]),
            str(row["risk"]),
            float(row["estimated_cost"]),
            int(row["estimated_duration_seconds"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    def set_status(self, identifier: int, status: GoalStatus) -> None:
        current = self.get(identifier)
        if current is None:
            raise KeyError(identifier)
        allowed = {
            GoalStatus.PENDING: {GoalStatus.RUNNING, GoalStatus.PAUSED},
            GoalStatus.RUNNING: {GoalStatus.PAUSED, GoalStatus.COMPLETED, GoalStatus.STOPPED},
            GoalStatus.PAUSED: {GoalStatus.RUNNING, GoalStatus.STOPPED},
            GoalStatus.COMPLETED: set(),
            GoalStatus.STOPPED: set(),
        }
        if status not in allowed[current.status]:
            raise ValueError(f"Invalid transition: {current.status} -> {status}")
        self._connection.execute(
            "UPDATE goals SET status=?,updated_at=? WHERE id=?",
            (status.value, datetime.now(UTC).isoformat(), identifier),
        )
        self._connection.commit()

    def checkpoint(self, identifier: int, next_step: int, observation: dict) -> None:
        current = self.get(identifier)
        if current is None or current.status is not GoalStatus.RUNNING:
            raise ValueError("Goal must be running")
        if not current.next_step <= next_step <= len(current.plan.steps):
            raise ValueError("Invalid checkpoint")
        now = datetime.now(UTC).isoformat()
        with self._connection:
            self._connection.execute(
                "INSERT INTO goal_observations(goal_id,step_index,observation,created_at) VALUES(?,?,?,?)",
                (
                    identifier,
                    next_step - 1,
                    json.dumps(observation, ensure_ascii=False, default=str),
                    now,
                ),
            )
            self._connection.execute(
                "UPDATE goals SET next_step=?,updated_at=? WHERE id=?", (next_step, now, identifier)
            )

    def close(self) -> None:
        self._connection.close()
