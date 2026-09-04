from __future__ import annotations

import argparse
import asyncio
import json

from app.browser.session import BrowserSession


async def run(query: str, limit: int) -> None:
    browser = BrowserSession(headless=True, timeout_ms=20_000, profile_dir=None)
    try:
        businesses = await browser.search_google_maps_businesses(query=query, limit=limit)
        print(json.dumps(businesses, ensure_ascii=False, indent=2))
    finally:
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Teste real e somente leitura do coletor Maps.")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(run(args.query, args.limit))
