"""Run browser subprocesses without replacing psycopg's Windows Selector loop."""
from __future__ import annotations

import asyncio
import concurrent.futures
import sys
import threading
from collections.abc import Awaitable, Callable
from functools import wraps


def _needs_browser_loop() -> bool:
    return sys.platform == "win32" and isinstance(
        asyncio.get_running_loop(), asyncio.SelectorEventLoop,
    )


async def run_browser[T](operation: Callable[[], Awaitable[T]]) -> T:
    """Keep all browser objects on one Proactor loop; propagate cancellation.

    The factory is called on the browser thread, so no coroutine or browser
    resource is created on the database loop. Other platforms run directly.
    """
    if not _needs_browser_loop():
        return await operation()

    completed: concurrent.futures.Future[T] = concurrent.futures.Future()
    lock = threading.Lock()
    cancelled = threading.Event()
    state: dict[str, object] = {}

    async def invoke() -> T:
        with lock:
            state["loop"] = asyncio.get_running_loop()
            state["task"] = asyncio.current_task()
        if cancelled.is_set():
            raise asyncio.CancelledError
        return await operation()

    def worker() -> None:
        try:
            with asyncio.Runner(loop_factory=asyncio.ProactorEventLoop) as runner:
                result = runner.run(invoke())
        except BaseException as error:  # noqa: BLE001 - thread boundary must forward cancellation too
            completed.set_exception(error)
        else:
            completed.set_result(result)

    threading.Thread(target=worker, name="kiara-browser", daemon=True).start()
    future = asyncio.wrap_future(completed)
    try:
        return await asyncio.shield(future)
    except asyncio.CancelledError:
        cancelled.set()
        with lock:
            loop, task = state.get("loop"), state.get("task")
            if loop is not None and task is not None:
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass  # The browser loop already completed and closed.
        # Give Playwright's finally blocks time to close pages and its driver.
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout=5)
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - preserve caller cancellation during cleanup
            # A late completion must still retrieve its exception.
            future.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        raise


def browser_task[**P, T](function: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return await run_browser(lambda: function(*args, **kwargs))

    return wrapped
