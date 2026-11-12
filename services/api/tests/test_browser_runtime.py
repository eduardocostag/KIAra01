import asyncio
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from kiara_api.browser_runtime import browser_task, run_browser


def test_browser_runs_directly_when_loop_supports_subprocesses(monkeypatch):
    monkeypatch.setattr("kiara_api.browser_runtime._needs_browser_loop", lambda: False)

    async def verify():
        loop = asyncio.get_running_loop()

        async def operation():
            assert asyncio.get_running_loop() is loop
            return 42

        assert await run_browser(operation) == 42

    asyncio.run(verify())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows event loop compatibility")
def test_selector_database_loop_can_run_real_browser_subprocess():
    async def verify():
        parent_loop = asyncio.get_running_loop()
        parent_thread = threading.get_ident()

        @browser_task
        async def operation(value):
            assert isinstance(asyncio.get_running_loop(), asyncio.ProactorEventLoop)
            assert threading.get_ident() != parent_thread
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "print('browser-driver-ok')", stdout=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            return value, process.returncode, stdout.strip()

        assert await operation(42) == (42, 0, b"browser-driver-ok")
        assert asyncio.get_running_loop() is parent_loop
        assert isinstance(parent_loop, asyncio.SelectorEventLoop)

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(verify())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows event loop compatibility")
def test_cancelling_browser_runs_cleanup_on_its_own_loop():
    started, cleaned = threading.Event(), threading.Event()

    async def operation():
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            cleaned.set()

    async def verify():
        task = asyncio.create_task(run_browser(operation))
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(verify())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows event loop compatibility")
def test_browser_errors_reach_the_caller():
    async def operation():
        raise ValueError("browser failed")

    async def verify():
        with pytest.raises(ValueError, match="browser failed"):
            await run_browser(operation)

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(verify())
