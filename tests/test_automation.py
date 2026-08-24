from datetime import UTC, datetime, timedelta

import pytest

from app.automation import AutomationTeacher, automation_template
from app.automation.engine import AutomationEngine, AutomationSpec, AutomationStore, TriggerKind
from app.core.event_bus import EventBus
from app.models import ToolResult


@pytest.mark.asyncio
async def test_event_automation_runs_matching_handler(tmp_path):
    received = []

    async def handler(spec):
        received.append(spec.name)

    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), handler)
    engine.add(AutomationSpec("alerta", TriggerKind.EVENT, "notify", {}, trigger_value="SERVICE_DOWN"))
    assert await engine.emit("SERVICE_DOWN") == 1
    assert received == ["alerta"]


@pytest.mark.asyncio
async def test_scheduled_automation_is_disabled_after_run(tmp_path):
    received = []

    async def handler(spec):
        received.append(spec.id)

    store = AutomationStore(tmp_path / "automations.db")
    engine = AutomationEngine(store, handler)
    past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    engine.add(AutomationSpec("once", TriggerKind.SCHEDULED, "notify", {}, next_run_at=past))
    assert await engine.tick() == 1
    assert received and not store.list()[0].enabled


def test_recurring_requires_safe_interval(tmp_path):
    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), lambda _: None)
    with pytest.raises(ValueError):
        engine.add(AutomationSpec("bad", TriggerKind.RECURRING, "notify", {}, interval_seconds=0))


async def test_event_is_idempotent_with_persistent_event_id(tmp_path):
    calls = 0

    async def handler(_):
        nonlocal calls
        calls += 1

    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), handler)
    engine.add(AutomationSpec("alerta", TriggerKind.EVENT, "notify", {}, trigger_value="alert"))
    assert await engine.emit("alert", event_id="stable-id") == 1
    assert await engine.emit("alert", event_id="stable-id") == 0
    assert calls == 1


async def test_retry_is_limited_and_persisted(tmp_path):
    calls = 0

    async def handler(_):
        nonlocal calls
        calls += 1
        raise RuntimeError("temporary")

    store = AutomationStore(tmp_path / "automations.db")
    engine = AutomationEngine(store, handler)
    spec = AutomationSpec(
        "retry", TriggerKind.EVENT, "notify", {}, trigger_value="alert",
        max_retries=2, retry_delay_seconds=0,
    )
    engine.add(spec)
    assert await engine.emit("alert", event_id="evt") == 0
    assert calls == 3
    run = store.run(spec.id, "event:evt")
    assert run is not None
    assert run["state"] == "failed"
    assert run["attempts"] == 3


async def test_condition_and_event_bus_lifecycle(tmp_path):
    calls = []

    async def handler(spec):
        calls.append(spec.name)

    bus = EventBus()
    engine = AutomationEngine(
        AutomationStore(tmp_path / "automations.db"), handler, event_bus=bus, tick_seconds=0.01
    )
    condition = '{"event":"health","field":"service.status","equals":"down"}'
    engine.add(AutomationSpec("health-check", TriggerKind.CONDITION, "notify", {}, trigger_value=condition))
    await engine.start()
    await bus.publish("health", {"event_id": "1", "service": {"status": "up"}})
    await bus.publish("health", {"event_id": "2", "service": {"status": "down"}})
    await engine.stop()
    assert calls == ["health-check"]
    await bus.publish("health", {"event_id": "3", "service": {"status": "down"}})
    assert calls == ["health-check"]


async def test_tool_registry_path_executes_narrow_action(tmp_path):
    class FakeRegistry:
        async def execute(self, name, **parameters):
            assert name == "open_url"
            assert parameters == {"url": "https://example.com"}
            return ToolResult(True, output="ok")

    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), tools=FakeRegistry())
    engine.add(
        AutomationSpec(
            "site", TriggerKind.EVENT, "open_url", {"url": "https://example.com"},
            trigger_value="go",
        )
    )
    assert await engine.emit("go", event_id="tool-1") == 1


def test_preview_does_not_persist_and_teaching_draft_is_disabled(tmp_path):
    store = AutomationStore(tmp_path / "automations.db")
    engine = AutomationEngine(store, lambda _spec: None)
    draft = AutomationTeacher().prepare(name="Ensinar abertura", action="open_url", parameters={"url": "https://example.com"})
    preview = engine.preview(draft)
    assert preview["enabled"] is False
    assert store.list() == []


def test_template_returns_independent_disabled_copy():
    first = automation_template("abrir_portal_diariamente", url="https://kiara.local")
    second = automation_template("abrir_portal_diariamente")
    assert first.enabled is False and first.id != second.id
    assert first.action_parameters["url"] == "https://kiara.local"
    assert second.action_parameters["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_history_and_explicit_failed_retry(tmp_path):
    attempts = 0
    async def handler(_spec):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
    store = AutomationStore(tmp_path / "automations.db")
    engine = AutomationEngine(store, handler)
    spec = AutomationSpec("retry", TriggerKind.EVENT, "notify", {}, trigger_value="go", max_retries=0)
    engine.add(spec)
    assert await engine.emit("go", event_id="original") == 0
    assert await engine.retry_failed(spec.id, "event:original") is True
    assert [item["state"] for item in store.list_runs(spec.id)] == ["succeeded", "failed"]


@pytest.mark.asyncio
async def test_failed_failure_handler_does_not_republish_recursively(tmp_path):
    calls = 0

    async def handler(_spec):
        nonlocal calls
        calls += 1
        raise RuntimeError("still broken")

    bus = EventBus()
    engine = AutomationEngine(AutomationStore(tmp_path / "automations.db"), handler, event_bus=bus)
    engine.add(
        AutomationSpec(
            "failure handler",
            TriggerKind.EVENT,
            "notify",
            {},
            trigger_value="AUTOMATION_FAILED",
            max_retries=0,
        )
    )
    await engine.start()
    await bus.publish("AUTOMATION_FAILED", {"event_id": "root-failure"})
    await engine.stop()
    assert calls == 1
