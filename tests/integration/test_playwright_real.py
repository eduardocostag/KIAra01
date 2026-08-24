import pytest

from app.browser import BrowserSession


@pytest.mark.asyncio
async def test_real_playwright_launch_and_close():
    browser = BrowserSession(headless=True)
    try:
        await browser.start()
        snapshot = await browser.snapshot()
        assert snapshot.url == "about:blank"
    finally:
        await browser.close()
