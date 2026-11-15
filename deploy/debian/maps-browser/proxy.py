"""Kiara Maps browser: headless Chromium for the Hunter's Google Maps reading (replaces paid remote browsers).

Chromium's DevTools websocket has a random id per launch, so this proxy offers a fixed address
(ws://127.0.0.1:8892/cdp) and forwards each connection to the current browser. It also:
* limits simultaneous searches: extra ones get HTTP 503 before the handshake and the Hunter retries shortly;
* relaunches Chromium if it dies, and restarts it after a while idle to drop leftover tabs and memory.
The gateway in front of it requires the gateway token; this process listens only on 127.0.0.1.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import urllib.request

import websockets

PORT = int(os.getenv("PORT", "8892"))
DEBUG_PORT = 9223
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "3"))
IDLE_RESTART_SECONDS = 600
PROFILE = "/tmp/chromium-profile"
FLAGS = [
    "--headless=new", f"--remote-debugging-port={DEBUG_PORT}", "--remote-debugging-address=127.0.0.1",
    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-sync", "--disable-extensions", "--mute-audio",
    "--lang=pt-BR", "--window-size=1366,900", f"--user-data-dir={PROFILE}",
]

browser: subprocess.Popen | None = None
active = 0
reservations: list[float] = []  # handshakes accepted but not yet running (expire if the client gives up)
last_used = time.monotonic()
lock = asyncio.Lock()


def browser_url() -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=3) as response:
        return json.load(response)["webSocketDebuggerUrl"]


async def ensure_browser() -> str:
    global browser
    async with lock:
        if browser is None or browser.poll() is not None:
            shutil.rmtree(PROFILE, ignore_errors=True)
            binary = shutil.which("chromium") or shutil.which("chromium-browser")
            browser = subprocess.Popen([binary, *FLAGS, "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                return await asyncio.to_thread(browser_url)
            except OSError:
                await asyncio.sleep(0.25)
        raise RuntimeError("chromium_not_ready")


async def stop_browser() -> None:
    global browser
    async with lock:
        if browser and browser.poll() is None:
            browser.terminate()
            try:
                await asyncio.to_thread(browser.wait, 10)
            except subprocess.TimeoutExpired:
                browser.kill()
        browser = None


async def pump(source, target) -> None:
    async for message in source:
        await target.send(message)


async def handle(client) -> None:
    global active, last_used
    if client.request.path.split("?")[0] != "/cdp":
        await client.close(1008, "not found")
        return
    if reservations:
        reservations.pop(0)
    active += 1
    try:
        upstream_url = await ensure_browser()
        async with websockets.connect(upstream_url, max_size=64 * 1024 * 1024, open_timeout=10) as upstream:
            tasks = [asyncio.create_task(pump(client, upstream)), asyncio.create_task(pump(upstream, client))]
            _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
    except Exception:  # noqa: BLE001 - a broken session must not stop the service
        pass
    finally:
        active -= 1
        last_used = time.monotonic()


async def janitor() -> None:
    while True:
        await asyncio.sleep(60)
        if active == 0 and browser is not None and time.monotonic() - last_used > IDLE_RESTART_SECONDS:
            await stop_browser()  # next search starts a clean browser


async def health(connection, request):
    if request.path == "/healthz":
        return connection.respond(200, f"ok active={active}\n")
    # Busy: refuse before the handshake (HTTP 503) so the Hunter waits a few seconds and tries again.
    now = time.monotonic()
    reservations[:] = [stamp for stamp in reservations if now - stamp < 20]
    if active + len(reservations) >= MAX_SESSIONS:
        return connection.respond(503, "busy\n")
    reservations.append(now)
    return None


async def main() -> None:
    asyncio.create_task(janitor())
    async with websockets.serve(handle, "127.0.0.1", PORT, max_size=64 * 1024 * 1024, process_request=health,
                                ping_interval=20, ping_timeout=60):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
