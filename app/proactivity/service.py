from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from app.core.event_bus import EventBus
from app.proactivity.policy import ProactivityPolicy


class ProactivityService:
    NOTIFICATION = "assistant.proactive_notification"
    SOURCES: ClassVar[dict[str, float]] = {
        "ERROR_DETECTED": 0.95,
        "NOTIFICATION_RECEIVED": 0.7,
        "PROCESS_STOPPED": 0.6,
        "AUTOMATION_FAILED": 0.9,
        "APP_NOT_RESPONDING": 0.95,
        "SCREEN_IMPORTANT_CHANGE": 0.85,
    }

    def __init__(
        self,
        bus: EventBus,
        policy: ProactivityPolicy,
        notify: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.bus, self.policy = bus, policy
        self.notify = notify
        self._unsubscribe: list[Callable[[], None]] = []

    def start(self) -> None:
        if self._unsubscribe:
            return
        for event, importance in self.SOURCES.items():

            async def receive(payload: dict[str, Any], *, source=event, score=importance) -> None:
                if self.policy.should_notify(importance=float(payload.get("importance", score))):
                    offers = {
                        "ERROR_DETECTED": "Percebi um possível erro na tela. Quer que eu analise e proponha uma solução?",
                        "APP_NOT_RESPONDING": "O aplicativo atual parece não estar respondendo. Quer que eu faça um diagnóstico seguro?",
                        "SCREEN_IMPORTANT_CHANGE": "Percebi uma mudança importante na tela. Quer que eu analise o que aconteceu?",
                        "AUTOMATION_FAILED": "Uma automação falhou. Quer que eu investigue e prepare uma alternativa?",
                    }
                    notice = {
                        "source": source,
                        "payload": payload,
                        "offer_text": offers.get(
                            source, "Percebi uma mudança relevante. Quer que eu analise?"
                        ),
                        "mode": "offer_help_only",
                    }
                    await self.bus.publish(self.NOTIFICATION, notice)
                    if self.notify is not None:
                        self.notify(notice)

            self._unsubscribe.append(self.bus.subscribe(event, receive))

    def stop(self) -> None:
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        self._unsubscribe.clear()

    def set_notifier(self, notify: Callable[[dict[str, Any]], None] | None) -> None:
        self.notify = notify
