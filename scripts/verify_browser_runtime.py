from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.browser import BrowserSession
from app.config import load_settings


async def main() -> int:
    settings = load_settings()
    browser = BrowserSession(
        headless=True,
        timeout_ms=int(settings.get("browser.timeout_ms", 15_000)),
        profile_dir=settings.root / str(
            settings.get("browser.profile_dir", "data/browser-profile")
        ),
    )
    try:
        page = await browser.navigate("https://example.com")
        print(f"BROWSER_OK={page.title == 'Example Domain'}")
        return 0 if page.title == "Example Domain" else 2
    finally:
        await browser.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
