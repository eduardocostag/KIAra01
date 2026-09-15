"""Read-only Hunter provider smoke test. Run only with provider credentials in env.

No database writes, CRM sync, or messages. Output is counts and source evidence.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.hunter import _instagram_profile_matches, execute_research, inspect_instagram_bios, maps_search, public_search
from kiara_api.hunter_research import is_editorial_or_post, safe_public_url


SCENARIOS = [
    ("clinicas", "Porto Alegre", "web", 50),
    ("dentistas", "Rio Grande do Sul", "web", 100),
    ("psiquiatras", "São Paulo", "web", 50),
    ("educador fisico", "Curitiba", "web", 50),
    ("agencias", "Rio Grande do Sul", "web", 50),
    ("dentistas", "Porto Alegre", "instagram", 50),
    ("psiquiatras", "São Paulo", "instagram", 50),
    ("educador fisico", "Curitiba", "instagram", 50),
    ("agencias", "Rio Grande do Sul", "instagram", 50),
    ("clinicas", "Paraná", "instagram", 100),
    ("clinicas", "Porto Alegre", "google_maps", 30),
    ("dentistas", "Rio Grande do Sul", "google_maps", 30),
]


async def run_case(niche: str, location: str, source: str, limit: int) -> dict[str, object]:
    query = f"{niche} {location}"
    rows = await (maps_search(query, limit) if source == "google_maps" else public_search(query, source, limit))
    if source == "instagram":
        await inspect_instagram_bios(rows)
    valid_urls = [row for row in rows if safe_public_url(row.get("url"))]
    accepted_urls = [row for row in valid_urls if not is_editorial_or_post(row)]
    match_search = {"query": niche, "location": location, "market": "b2c", "sources": [source]}
    matched = [row for row in accepted_urls if _instagram_profile_matches(row, match_search)] if source == "instagram" else []
    profiles = [row for row in matched if row.get("public_data", {}).get("content_kind") == "profile"]
    publications = [row for row in matched if row.get("public_data", {}).get("content_kind") == "publication"]
    return {
        "niche": niche, "location": location, "source": source, "requested": limit,
        "returned": len(rows), "valid_urls": len(valid_urls),
        "profiles_not_posts": len(profiles) if source == "instagram" else None,
        "publications": len(publications) if source == "instagram" else None,
        "instagram_candidates": len(matched) if source == "instagram" else None,
        "with_niche_evidence": sum(row.get("public_data", {}).get("niche_evidence") is True for row in matched) if source == "instagram" else None,
        "with_location_evidence": sum(row.get("public_data", {}).get("location_evidence") is True for row in matched) if source == "instagram" else None,
        "bios_verified": sum(row.get("public_data", {}).get("bio_status") == "verified_public_profile" for row in matched) if source == "instagram" else None,
        "maps_details_inspected": sum(row.get("public_data", {}).get("detail_inspected") is True for row in rows) if source == "google_maps" else None,
    }


async def main() -> None:
    if "--flow" in sys.argv or "--flow-instagram" in sys.argv:
        flow_cases = [
            ("dentistas", "Porto Alegre", "instagram", 30),
            ("clinicas", "Porto Alegre", "google_maps", 30),
            ("psiquiatras", "S\u00e3o Paulo", "web", 30),
        ]
        if "--flow-instagram" in sys.argv:
            flow_cases = flow_cases[:1]
        for niche, location, source, limit in flow_cases:
            search = {"query": niche, "location": location, "sources": [source],
                      "result_limit": limit, "market": "b2b", "research_mode": "broad"}
            try:
                outcome = await execute_research(search)
                report = {"niche": niche, "location": location, "source": source,
                          "requested": limit, "accepted": len(outcome["results"]),
                          "validation": outcome["validation"], "error": outcome["error"]}
            except Exception as exc:
                report = {"niche": niche, "location": location, "source": source,
                          "error_class": type(exc).__name__, "error": str(exc)[:80]}
            print(json.dumps(report, ensure_ascii=False), flush=True)
        return
    scenarios = [case for case in SCENARIOS if case[2] == "instagram"] if "--instagram" in sys.argv else SCENARIOS
    for scenario in scenarios:
        try:
            result = await run_case(*scenario)
        except Exception as exc:  # noqa: BLE001 - diagnostic must continue across providers
            result = {"niche": scenario[0], "location": scenario[1], "source": scenario[2],
                      "requested": scenario[3], "error_class": type(exc).__name__, "error_code": str(exc)[:80]}
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
