import pytest

from app.core.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_delivers_payload():
    bus = EventBus()
    received = []
    bus.subscribe("TEST", lambda payload: _append(received, payload))
    await bus.publish("TEST", {"ok": True})
    assert received == [{"ok": True}]


async def _append(target, value):
    target.append(value)
