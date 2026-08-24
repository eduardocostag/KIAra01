from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.core.event_bus import EventBus
from app.tools.registry import ToolRegistry


class TriggerKind(StrEnum):
    SCHEDULED = "scheduled"
    RECURRING = "recurring"
    EVENT = "event"
    CONDITION = "condition"


class RunState(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(slots=True)
class AutomationSpec:
    name: str
    trigger_kind: TriggerKind
    action: str
    action_parameters: dict[str, Any]
    id: str = ""
    trigger_value: str = ""
    interval_seconds: float | None = None
    enabled: bool = True
    next_run_at: str | None = None
    max_retries: int = 2
    retry_delay_seconds: float = 0.25

    def __post_init__(self) -> None:
        self.id = self.id or str(uuid.uuid4())
        if not 0 <= self.max_retries <= 5:
            raise ValueError("max_retries must be between 0 and 5")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")


AutomationHandler = Callable[[AutomationSpec], Awaitable[Any]]


class AutomationStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS automations (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS automation_runs (
                    automation_id TEXT NOT NULL,
                    run_key TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    PRIMARY KEY (automation_id, run_key)
                );
                CREATE INDEX IF NOT EXISTS idx_automation_runs_state
                    ON automation_runs(state);
                PRAGMA user_version=1;
                """
            )
            # Interrupted actions stay non-repeatable; their outcome is unknown and must be reviewed.
            db.execute(
                """UPDATE automation_runs SET state='failed', last_error='interrupted',
                   finished_at=? WHERE state='running'""",
                (datetime.now(UTC).isoformat(),),
            )

    def save(self, spec: AutomationSpec) -> None:
        payload = json.dumps(asdict(spec), ensure_ascii=False, sort_keys=True)
        with self._connect() as db:
            db.execute(
                """INSERT INTO automations(id,payload,updated_at) VALUES (?,?,?)
                   ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,
                   updated_at=excluded.updated_at""",
                (spec.id, payload, datetime.now(UTC).isoformat()),
            )

    def list(self) -> list[AutomationSpec]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM automations ORDER BY id").fetchall()
        result = []
        for row in rows:
            payload = json.loads(row["payload"])
            payload["trigger_kind"] = TriggerKind(payload["trigger_kind"])
            result.append(AutomationSpec(**payload))
        return result

    def get(self, automation_id: str) -> AutomationSpec | None:
        return next((item for item in self.list() if item.id == automation_id), None)

    def delete(self, automation_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        return cursor.rowcount > 0

    def claim(self, automation_id: str, run_key: str) -> bool:
        try:
            with self._connect() as db:
                db.execute(
                    """INSERT INTO automation_runs
                       (automation_id,run_key,state,started_at) VALUES (?,?,?,?)""",
                    (automation_id, run_key, RunState.RUNNING.value, datetime.now(UTC).isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def finish(
        self, automation_id: str, run_key: str, state: RunState, attempts: int, error: str | None
    ) -> None:
        with self._connect() as db:
            db.execute(
                """UPDATE automation_runs SET state=?, attempts=?, last_error=?, finished_at=?
                   WHERE automation_id=? AND run_key=?""",
                (
                    state.value,
                    attempts,
                    error,
                    datetime.now(UTC).isoformat(),
                    automation_id,
                    run_key,
                ),
            )

    def run(self, automation_id: str, run_key: str) -> sqlite3.Row | None:
        with self._connect() as db:
            return db.execute(
                "SELECT * FROM automation_runs WHERE automation_id=? AND run_key=?",
                (automation_id, run_key),
            ).fetchone()

    def list_runs(self, automation_id: str | None = None, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return bounded execution history without exposing a live database cursor."""
        limit = min(500, max(1, int(limit)))
        query = "SELECT * FROM automation_runs"
        parameters: tuple[Any, ...] = ()
        if automation_id:
            query += " WHERE automation_id=?"
            parameters = (automation_id,)
        query += " ORDER BY COALESCE(finished_at, started_at) DESC, rowid DESC LIMIT ?"
        parameters += (limit,)
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, parameters).fetchall()]


class AutomationEngine:
    def __init__(
        self,
        store: AutomationStore,
        handler: AutomationHandler | None = None,
        *,
        tools: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
        tick_seconds: float = 1.0,
    ) -> None:
        if handler is None and tools is None:
            raise ValueError("AutomationEngine requires a handler or ToolRegistry")
        self.store = store
        self.handler = handler
        self.tools = tools
        self.event_bus = event_bus
        self.tick_seconds = tick_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._subscriptions: dict[str, Callable[[], None]] = {}

    def add(self, spec: AutomationSpec) -> str:
        self.preview(spec)
        self.store.save(spec)
        self._subscribe(spec)
        return spec.id

    def preview(self, spec: AutomationSpec) -> dict[str, Any]:
        """Validate and describe a workflow without saving or executing it."""
        if not spec.name.strip():
            raise ValueError("Automation name is required")
        if not spec.action.strip():
            raise ValueError("Automation action is required")
        tool_names = getattr(self.tools, "names", None)
        if callable(tool_names) and spec.action not in tool_names():
            raise ValueError(f"Unknown automation action: {spec.action}")
        if spec.trigger_kind == TriggerKind.RECURRING:
            if spec.interval_seconds is None or spec.interval_seconds < 1:
                raise ValueError("Recurring automation requires a minimum one-second interval")
            spec.next_run_at = spec.next_run_at or (
                datetime.now(UTC) + timedelta(seconds=spec.interval_seconds)
            ).isoformat()
        if spec.trigger_kind == TriggerKind.SCHEDULED:
            if not spec.next_run_at:
                raise ValueError("Scheduled automation requires next_run_at")
            datetime.fromisoformat(spec.next_run_at)
        self._validate_trigger(spec)
        return {
            "id": spec.id, "name": spec.name, "trigger": spec.trigger_kind.value,
            "trigger_value": spec.trigger_value, "interval_seconds": spec.interval_seconds,
            "next_run_at": spec.next_run_at, "action": spec.action,
            "parameters": spec.action_parameters, "enabled": spec.enabled,
            "max_attempts": spec.max_retries + 1,
            "effect": "validate_and_save_only; execution waits for its trigger",
        }

    async def retry_failed(self, automation_id: str, run_key: str) -> bool:
        """Explicitly retry a failed run under a new idempotency key."""
        spec = self.store.get(automation_id)
        previous = self.store.run(automation_id, run_key)
        if spec is None or previous is None or previous["state"] != RunState.FAILED.value:
            return False
        return await self._execute(spec, f"manual-retry:{run_key}:{uuid.uuid4()}")

    def set_enabled(self, automation_id: str, enabled: bool) -> bool:
        spec = self.store.get(automation_id)
        if spec is None:
            return False
        spec.enabled = bool(enabled)
        self.store.save(spec)
        if spec.enabled:
            self._subscribe(spec)
        return True

    def remove(self, automation_id: str) -> bool:
        return self.store.delete(automation_id)

    async def emit(
        self, event: str, payload: Mapping[str, Any] | None = None, *, event_id: str | None = None
    ) -> int:
        payload = payload or {}
        event_id = event_id or str(uuid.uuid4())
        matching = [
            item
            for item in self.store.list()
            if item.enabled and self._matches_event(item, event, payload)
        ]
        results = await asyncio.gather(
            *(self._execute(item, f"event:{event_id}") for item in matching),
            return_exceptions=True,
        )
        return sum(result is True for result in results)

    async def tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        due = [
            item
            for item in self.store.list()
            if item.enabled
            and item.trigger_kind in {TriggerKind.SCHEDULED, TriggerKind.RECURRING}
            and item.next_run_at
            and datetime.fromisoformat(item.next_run_at) <= now
        ]
        executed = 0
        for item in due:
            scheduled_for = str(item.next_run_at)
            if await self._execute(item, f"schedule:{scheduled_for}"):
                executed += 1
            if item.trigger_kind == TriggerKind.RECURRING and item.interval_seconds:
                previous = datetime.fromisoformat(scheduled_for)
                while previous <= now:
                    previous += timedelta(seconds=item.interval_seconds)
                item.next_run_at = previous.isoformat()
            else:
                item.enabled = False
            self.store.save(item)
        return executed

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        for item in self.store.list():
            self._subscribe(item)
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="automation-engine")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        for unsubscribe in self._subscriptions.values():
            unsubscribe()
        self._subscriptions.clear()

    async def _loop(self) -> None:
        while not self._stop.is_set():
            await self.tick()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=max(0.25, self.tick_seconds))
            except TimeoutError:
                pass

    async def _execute(self, spec: AutomationSpec, run_key: str) -> bool:
        if not self.store.claim(spec.id, run_key):
            return False
        error = None
        attempts = 0
        for attempts in range(1, spec.max_retries + 2):
            try:
                if self.handler is not None:
                    outcome = await self.handler(spec)
                    success = getattr(outcome, "success", True)
                    error = getattr(outcome, "error", None)
                else:
                    assert self.tools is not None
                    outcome = await self.tools.execute(spec.action, **spec.action_parameters)
                    success, error = outcome.success, outcome.error
                if success:
                    self.store.finish(spec.id, run_key, RunState.SUCCEEDED, attempts, None)
                    return True
                error = error or "action returned unsuccessful result"
            except Exception as exc:  # noqa: BLE001 - workflow isolation boundary
                error = f"{type(exc).__name__}: {exc}"
            if attempts <= spec.max_retries and spec.retry_delay_seconds:
                await asyncio.sleep(spec.retry_delay_seconds)
        self.store.finish(spec.id, run_key, RunState.FAILED, attempts, error)
        # A failure-handler that itself fails must not recursively emit the same
        # event forever and exhaust the core loop.
        if self.event_bus is not None and self._event_name(spec) != "AUTOMATION_FAILED":
            await self.event_bus.publish(
                "AUTOMATION_FAILED",
                {"automation_id": spec.id, "name": spec.name, "error": error, "importance": 0.9},
            )
        return False

    def _subscribe(self, spec: AutomationSpec) -> None:
        event = self._event_name(spec)
        if not self.event_bus or not spec.enabled or not event or event in self._subscriptions:
            return

        async def receive(payload: dict[str, Any]) -> None:
            event_id = str(payload.get("event_id") or uuid.uuid4())
            await self.emit(event, payload, event_id=event_id)

        self._subscriptions[event] = self.event_bus.subscribe(event, receive)

    @staticmethod
    def _event_name(spec: AutomationSpec) -> str | None:
        if spec.trigger_kind == TriggerKind.EVENT:
            return spec.trigger_value
        if spec.trigger_kind == TriggerKind.CONDITION:
            return str(json.loads(spec.trigger_value).get("event", ""))
        return None

    @classmethod
    def _matches_event(cls, spec: AutomationSpec, event: str, payload: Mapping[str, Any]) -> bool:
        if spec.trigger_kind == TriggerKind.EVENT:
            return spec.trigger_value == event
        if spec.trigger_kind != TriggerKind.CONDITION:
            return False
        condition = json.loads(spec.trigger_value)
        if condition.get("event") != event:
            return False
        current: Any = payload
        for part in str(condition["field"]).split("."):
            if not isinstance(current, Mapping) or part not in current:
                return False
            current = current[part]
        return current == condition.get("equals")

    @classmethod
    def _validate_trigger(cls, spec: AutomationSpec) -> None:
        if spec.trigger_kind == TriggerKind.EVENT and not spec.trigger_value:
            raise ValueError("Event automation requires trigger_value")
        if spec.trigger_kind == TriggerKind.CONDITION:
            condition = json.loads(spec.trigger_value)
            if not condition.get("event") or not condition.get("field"):
                raise ValueError("Condition requires event and field")
