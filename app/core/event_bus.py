from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event: str, handler: EventHandler) -> Callable[[], None]:
        self._handlers[event].append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers[event]:
                self._handlers[event].remove(handler)

        return unsubscribe

    async def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        handlers = tuple(self._handlers.get(event, ()))
        if handlers:
            await asyncio.gather(*(handler(payload or {}) for handler in handlers))
