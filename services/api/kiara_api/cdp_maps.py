"""Google Maps reading over the raw Chrome DevTools Protocol (no Playwright driver).

Vercel Functions cannot start Playwright's Node driver ("Connection closed while reading from the
driver"), so remote browsers (Browserbase, Obscura) were unusable there. This client speaks CDP
directly over a WebSocket: it opens tabs, navigates, waits with JavaScript conditions and reads the
same business panel snapshot the Playwright path reads.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import time
from typing import Any

COLLECT_ITEMS = """[...new Map([...document.querySelectorAll('a[href*="/maps/place/"]')]
  .map(e => [e.href, {title: e.getAttribute('aria-label') || e.textContent.trim(), url: e.href}])).values()]"""
LIST_READY = """!!(document.querySelector('a[href*="/maps/place/"], h1.DUwDvf') || document.querySelector('[role="feed"]'))"""
SCROLL_FEED = """(() => { const feed = document.querySelector('[role="feed"]'); if (!feed) return false;
  feed.scrollBy(0, Math.max(feed.clientHeight * 1.8, 900)); return true })()"""
DETAIL_READY = """(() => { const heading = document.querySelector('h1.DUwDvf') || document.querySelector('[role="main"] h1');
  const panel = heading?.closest('[role="main"]');
  return !!(panel && panel.querySelector('[data-item-id="address"], [data-item-id^="phone:"], a[data-item-id="authority"]')
    && !panel.querySelector('[role="progressbar"]')) })()"""
ACCEPT_CONSENT = """(() => { if (location.hostname !== 'consent.google.com') return false;
  const button = [...document.querySelectorAll('button')].find(b => /^(Aceitar tudo|Accept all|Concordo|I agree)$/i.test(b.textContent.trim()));
  if (button) { button.click(); return true } return false })()"""


class CdpError(RuntimeError):
    pass


class CdpConnection:
    """Minimal CDP client: browser-level socket with flattened per-tab sessions."""

    def __init__(self, socket: Any) -> None:
        self._socket = socket
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, url: str, headers: dict[str, str] | None = None) -> CdpConnection:
        import websockets

        socket = await asyncio.wait_for(websockets.connect(
            url, additional_headers=headers or None, max_size=64 * 1024 * 1024, open_timeout=15,
        ), timeout=20)
        return cls(socket)

    async def _read(self) -> None:
        try:
            async for raw in self._socket:
                message = json.loads(raw)
                future = self._pending.pop(message.get("id"), None) if "id" in message else None
                if future and not future.done():
                    if "error" in message:
                        future.set_exception(CdpError(str(message["error"].get("message", "cdp_error"))[:200]))
                    else:
                        future.set_result(message.get("result", {}))
        except Exception as exc:  # noqa: BLE001 - surface the closed socket to every waiter
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(CdpError(f"cdp_socket_closed: {type(exc).__name__}"))
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(CdpError("cdp_socket_closed"))

    async def send(self, method: str, params: dict[str, Any] | None = None, session: str | None = None,
                   timeout: float = 20) -> dict[str, Any]:
        message_id = next(self._ids)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[message_id] = future
        payload: dict[str, Any] = {"id": message_id, "method": method, "params": params or {}}
        if session:
            payload["sessionId"] = session
        await self._socket.send(json.dumps(payload))
        return await asyncio.wait_for(future, timeout=timeout)

    async def close(self) -> None:
        self._reader.cancel()
        try:
            await asyncio.wait_for(self._socket.close(), timeout=5)
        except Exception:  # noqa: BLE001 - cleanup must not hide results
            pass


class Tab:
    def __init__(self, cdp: CdpConnection, target: str, session: str) -> None:
        self.cdp, self.target, self.session = cdp, target, session

    @classmethod
    async def open(cls, cdp: CdpConnection) -> Tab:
        target = (await cdp.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
        session = (await cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
        tab = cls(cdp, target, session)
        await tab.cdp.send("Page.enable", session=session)
        await tab.cdp.send("Emulation.setLocaleOverride", {"locale": "pt-BR"}, session=session)
        return tab

    async def evaluate(self, expression: str, timeout: float = 15) -> Any:
        result = await self.cdp.send("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True},
                                     session=self.session, timeout=timeout)
        if result.get("exceptionDetails"):
            raise CdpError("page_script_failed")
        return (result.get("result") or {}).get("value")

    async def goto(self, url: str) -> None:
        await self.cdp.send("Page.navigate", {"url": url}, session=self.session, timeout=25)

    async def wait_for(self, expression: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if await self.evaluate(expression, timeout=5):
                    return True
            except (CdpError, TimeoutError):
                pass  # The document may be replaced mid-navigation.
            await asyncio.sleep(0.4)
        return False

    async def close(self) -> None:
        try:
            await self.cdp.send("Target.closeTarget", {"targetId": self.target}, timeout=5)
        except Exception:  # noqa: BLE001 - cleanup must not hide results
            pass


async def read_maps(connect_url: str, search_url: str, limit: int, detail_script: str,
                    to_result: Any, *, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """List businesses for a Maps search and read each business panel; same output as Playwright."""
    cdp = await CdpConnection.connect(connect_url, headers)
    try:
        tab = await Tab.open(cdp)
        await tab.goto(search_url)
        await tab.wait_for("document.readyState !== 'loading'", 15)
        if await tab.evaluate(ACCEPT_CONSENT):
            await asyncio.sleep(2)
        if not await tab.wait_for(LIST_READY, 14):
            raise CdpError("maps_results_unavailable")
        await tab.wait_for("!!document.querySelector('a[href*=\"/maps/place/\"], h1.DUwDvf')", 6)
        items = [item for item in (await tab.evaluate(COLLECT_ITEMS) or []) if isinstance(item, dict) and item.get("url")][:limit]
        attempts = 0
        while len(items) < limit and attempts < 20 and await tab.evaluate(SCROLL_FEED):
            attempts += 1
            await asyncio.sleep(0.7)
            items = [item for item in (await tab.evaluate(COLLECT_ITEMS) or []) if isinstance(item, dict) and item.get("url")][:limit]
        await tab.close()
        slots = asyncio.Semaphore(4)

        async def inspect(item: dict[str, Any]) -> dict[str, Any]:
            async with slots:
                detail_tab = await Tab.open(cdp)
                try:
                    await detail_tab.goto(item["url"])
                    if not await detail_tab.wait_for(DETAIL_READY, 12):
                        return to_result(item, {})
                    detail = await detail_tab.evaluate(f"({detail_script})()")
                    return to_result(item, detail if isinstance(detail, dict) else {})
                except (CdpError, TimeoutError, ValueError, TypeError):
                    return to_result(item, {})
                finally:
                    await detail_tab.close()

        tasks = [asyncio.create_task(inspect(item)) for item in items]
        if not tasks:
            return []
        done, pending = await asyncio.wait(tasks, timeout=75)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        return [task.result() if task in done and not task.cancelled() and task.exception() is None
                else to_result(item, {}) for item, task in zip(items, tasks, strict=True)]
    finally:
        await cdp.close()
