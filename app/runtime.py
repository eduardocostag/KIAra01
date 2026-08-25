from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

from app.automation.engine import AutomationEngine, AutomationStore
from app.config import Settings
from app.core.context import ContextManager
from app.core.event_bus import EventBus
from app.integrations.obsidian import ObsidianSyncService, ObsidianVaultIndex
from app.perception import PerceptionOptions, ScreenPerception
from app.perception.understanding import LiveScreenUnderstanding
from app.proactivity import ProactivityLevel, ProactivityPolicy, ProactivityService
from app.providers.llm import LLMProvider
from app.tools.registry import ToolRegistry


class BackgroundServices:
    """Owns one durable asyncio loop for monitors and schedulers."""

    def __init__(
        self,
        settings: Settings,
        tools: ToolRegistry,
        *,
        screen: ScreenPerception | None = None,
        provider: LLMProvider | None = None,
        context: ContextManager | None = None,
        obsidian: ObsidianVaultIndex | None = None,
    ) -> None:
        self.bus = screen.event_bus if screen is not None else EventBus()
        self.screen = screen or ScreenPerception(
            self.bus, PerceptionOptions.from_settings(settings)
        )
        self.proactivity = ProactivityService(
            self.bus,
            ProactivityPolicy(ProactivityLevel(settings.get("proactivity.level", "low"))),
        )
        self.automations = AutomationEngine(
            AutomationStore(
                settings.root / settings.get("automation.database", "data/automations.db")
            ),
            tools=tools,
            event_bus=self.bus,
            tick_seconds=float(settings.get("automation.tick_seconds", 1.0)),
        )
        self.screen_understanding = (
            LiveScreenUnderstanding(
                self.screen,
                provider,
                context,
                min_interval_seconds=float(
                    settings.get("screen.understanding_interval_seconds", 8.0)
                ),
            )
            if provider is not None
            and context is not None
            and settings.get("screen.continuous_understanding_enabled", False)
            else None
        )
        self.obsidian = (
            ObsidianSyncService(
                obsidian,
                interval_seconds=float(
                    settings.get("integrations.obsidian.sync_interval_seconds", 10.0)
                ),
            )
            if obsidian is not None
            else None
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._startup_error = None
        self._thread = threading.Thread(target=self._run, name="kiara-background", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("Serviços de fundo não inicializaram no prazo.")
        if self._startup_error is not None:
            raise RuntimeError("Falha ao iniciar serviços de fundo.") from self._startup_error

    def stop(self) -> None:
        if self._loop is None or self._thread is None:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._stop_async(), self._loop)
            future.result(timeout=5)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("Thread de serviços de fundo não encerrou.")
            self._loop = self._thread = None
            self._ready.clear()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_async())
        except Exception as exc:  # noqa: BLE001 - propagate startup adapters to caller
            self._startup_error = exc
            self._ready.set()
            self._loop.close()
            return
        self._ready.set()
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    async def astart(self) -> None:
        await self._start_async()

    async def astop(self) -> None:
        await self._stop_async()

    async def _start_async(self) -> None:
        self.proactivity.start()
        if self.screen_understanding is not None:
            self.screen_understanding.start()
        if self.obsidian is not None:
            self.obsidian.start()
        await self.screen.start()
        await self.automations.start()

    async def _stop_async(self) -> None:
        await self.screen.stop()
        if self.screen_understanding is not None:
            await self.screen_understanding.stop()
        if self.obsidian is not None:
            await self.obsidian.stop()
        await self.automations.stop()
        self.proactivity.stop()

    def set_proactive_notifier(self, callback: Callable[[dict[str, Any]], None] | None) -> None:
        self.proactivity.set_notifier(callback)
