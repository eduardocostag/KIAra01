from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from app.core.context import ContextManager
from app.perception.analysis import parse_screen_analysis, screen_analysis_prompt
from app.perception.screen import ScreenPerception
from app.providers.llm import LLMProvider


class LiveScreenUnderstanding:
    """Turns changing ephemeral frames into a bounded semantic screen context."""

    def __init__(
        self,
        perception: ScreenPerception,
        provider: LLMProvider,
        context: ContextManager,
        *,
        min_interval_seconds: float = 8.0,
    ) -> None:
        self.perception = perception
        self.provider = provider
        self.context = context
        self.min_interval_seconds = max(2.0, min_interval_seconds)
        self._last_analysis_at = float("-inf")
        self._analysis_task: asyncio.Task[None] | None = None
        self._unsubscribe: list[Callable[[], None]] = []

    def start(self) -> None:
        if self._unsubscribe or "vision" not in self.provider.capabilities:
            return
        for event in (ScreenPerception.CONTEXT_CHANGED, ScreenPerception.SCREEN_CHANGED):
            self._unsubscribe.append(self.perception.event_bus.subscribe(event, self._schedule))

    async def stop(self) -> None:
        for unsubscribe in self._unsubscribe:
            unsubscribe()
        self._unsubscribe.clear()
        if self._analysis_task is not None:
            self._analysis_task.cancel()
            await asyncio.gather(self._analysis_task, return_exceptions=True)
            self._analysis_task = None

    async def _schedule(self, payload: dict[str, Any]) -> None:
        if self._analysis_task is not None and not self._analysis_task.done():
            return
        self._analysis_task = asyncio.create_task(
            self._analyze(payload), name="live-screen-understanding"
        )

    async def _analyze(self, payload: dict[str, Any]) -> None:
        delay = self.min_interval_seconds - (time.monotonic() - self._last_analysis_at)
        if delay > 0:
            await asyncio.sleep(delay)
        capture = await self.perception.latest_capture(max_age_seconds=2.0)
        if capture is None:
            return
        prompt = screen_analysis_prompt(
            application=payload.get("active_application"),
            window_title=payload.get("window_title"),
        )
        try:
            raw = await self.provider.vision_bytes(prompt, capture.png)
        except Exception:  # noqa: BLE001 - optional visual provider boundary
            return
        analysis = parse_screen_analysis(raw, application=payload.get("active_application"))
        self._last_analysis_at = time.monotonic()
        self.context.update_live_screen_understanding(
            {
                "application": payload.get("active_application"),
                "window_title": payload.get("window_title"),
                "summary": analysis.summary()[:4000],
                "analysis": analysis.as_context(),
                "freshness": "live_ephemeral",
                "pixels_persisted": False,
            }
        )
        if analysis.visible_errors:
            await self.perception.event_bus.publish(
                "SCREEN_IMPORTANT_CHANGE",
                {
                    "active_application": payload.get("active_application"),
                    "importance": 0.9,
                    "state": "visible_error_detected",
                    "details_persisted": False,
                },
            )
