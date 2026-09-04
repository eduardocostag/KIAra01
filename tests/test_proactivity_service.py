import pytest

from app.core.event_bus import EventBus
from app.proactivity import ProactivityLevel, ProactivityPolicy, ProactivityService


@pytest.mark.asyncio
async def test_proactivity_emits_rate_limited_notification():
    bus = EventBus()
    service = ProactivityService(bus, ProactivityPolicy(ProactivityLevel.LOW))
    received = []

    async def collect(payload):
        received.append(payload)

    bus.subscribe(service.NOTIFICATION, collect)
    service.start()
    await bus.publish("ERROR_DETECTED", {"message": "service down"})
    await bus.publish("ERROR_DETECTED", {"message": "duplicate"})
    assert len(received) == 1
    assert received[0]["source"] == "ERROR_DETECTED"


@pytest.mark.asyncio
async def test_proactivity_calls_user_notifier():
    bus = EventBus()
    notices = []
    service = ProactivityService(
        bus, ProactivityPolicy(ProactivityLevel.HIGH), notify=notices.append
    )
    service.start()
    await bus.publish("NOTIFICATION_RECEIVED", {"message": "alert"})
    assert notices[0]["payload"]["message"] == "alert"


@pytest.mark.asyncio
async def test_proactive_error_only_offers_help_and_never_requests_action():
    bus = EventBus()
    notices = []
    service = ProactivityService(
        bus, ProactivityPolicy(ProactivityLevel.HIGH), notify=notices.append
    )
    service.start()
    await bus.publish("APP_NOT_RESPONDING", {"active_application": "Editor"})
    assert notices[0]["mode"] == "offer_help_only"
    assert "Quer que eu" in notices[0]["offer_text"]
    assert set(notices[0]) == {"source", "payload", "offer_text", "mode"}
