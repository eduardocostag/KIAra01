"""Optional native Maps CLI bridge for the local Hunter worker."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from .hunter_research import maps_detail_result


async def native_maps_search(query: str, limit: int) -> list[dict[str, Any]] | None:
    """None means unconfigured; configured failures propagate to provider fallback."""
    executable = os.getenv("KIARA_MAPS_SCRAPER_EXECUTABLE", "").strip()
    if not executable:
        return None
    from app.integrations.maps_scraper import MapsScraperClient
    from app.security.kill_switch import KillSwitch

    kill_switch = KillSwitch()
    root = Path(__file__).resolve().parents[3]
    client = MapsScraperClient(executable, root / "data" / "maps-scraper", kill_switch, timeout=110)
    try:
        businesses = await client.search(query=query, limit=min(limit, 50))
    except asyncio.CancelledError:
        kill_switch.trigger()
        raise
    rows: list[dict[str, Any]] = []
    for business in businesses:
        row = maps_detail_result(
            {"title": business["name"], "url": business["maps_url"]},
            {"title": business["name"], "loaded": True, "phone": business["phone"],
             "website": business["website"], "website_button": bool(business["website"]),
             "address": business["address"], "category": business["category"], "links": []},
        )
        row["public_data"].update({
            "provider": "gosom/google-maps-scraper", "rating": business["rating"],
            "user_rating_count": business["review_count"],
        })
        rows.append(row)
    return rows
