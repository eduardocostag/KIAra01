from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from app.config import Settings
from app.memory import MemoryEngine, MemoryKind
from app.runtime import BackgroundServices


class Tools:
    async def execute(self, name, **parameters):
        return None


class FailingScreen:
    async def start(self):
        raise RuntimeError("boom")

    async def stop(self):
        return None


def test_background_start_propagates_failure(tmp_path: Path) -> None:
    settings = Settings(
        raw={"screen": {"enabled": False}, "automation": {"tick_seconds": 0.25}},
        root=tmp_path,
    )
    services = BackgroundServices(settings, Tools())
    services.screen = FailingScreen()
    with pytest.raises(RuntimeError, match="Falha ao iniciar"):
        services.start()


@pytest.mark.asyncio
async def test_async_background_lifecycle_uses_callers_loop(tmp_path: Path) -> None:
    settings = Settings(
        raw={"screen": {"enabled": False}, "automation": {"tick_seconds": 0.25}},
        root=tmp_path,
    )
    services = BackgroundServices(settings, Tools())
    current = asyncio.get_running_loop()
    await services.astart()
    assert services.automations._task is not None
    assert services.automations._task.get_loop() is current
    await services.astop()


def test_memory_connection_can_move_to_serialized_owner_thread(tmp_path: Path) -> None:
    memory = MemoryEngine(tmp_path / "memory.db")
    memory.remember(MemoryKind.SEMANTIC, "conteúdo")
    result = []
    thread = threading.Thread(target=lambda: result.extend(memory.search("conteúdo")))
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result[0].content == "conteúdo"
    memory.close()


def test_request_worker_reuses_one_event_loop() -> None:
    pytest.importorskip("PySide6")
    from app.ui.desktop import RequestWorker

    class Core:
        def __init__(self):
            self.loops = []

        async def astart(self):
            return None

        async def handle(self, message):
            self.loops.append(asyncio.get_running_loop())
            return message

        async def aclose(self):
            return None

    core = Core()
    worker = RequestWorker(core)
    try:
        worker.handle("um")
        worker.handle("dois")
        deadline = time.monotonic() + 2
        while len(core.loops) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(core.loops) == 2
        assert core.loops[0] is core.loops[1]
    finally:
        worker.shutdown()
