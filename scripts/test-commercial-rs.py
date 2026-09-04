from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.browser.session import BrowserSession
from app.consumers import OrganicIntentClassifier


async def run(*, niche: str, location: str, limit: int, output: Path) -> int:
    browser = BrowserSession(headless=True, timeout_ms=25_000, profile_dir=None)
    classifier = OrganicIntentClassifier()
    report: dict[str, object] = {
        "executed_at": datetime.now(UTC).isoformat(),
        "niche": niche,
        "location": location,
        "safety": "somente leitura; nenhuma mensagem enviada",
    }
    try:
        try:
            businesses = await asyncio.wait_for(
                browser.search_google_maps_businesses(
                    query=f"clínicas de {niche} em Porto Alegre, {location}", limit=limit
                ),
                timeout=60,
            )
            report["b2b"] = {"count": len(businesses), "results": businesses}
        except Exception as exc:  # noqa: BLE001 - evidence preserves each source failure
            report["b2b"] = {"count": 0, "results": [], "error": f"{type(exc).__name__}: {exc}"}
        try:
            public_results = await asyncio.wait_for(
                browser.search_public_consumer_intent(
                    query=niche, location=location, limit=limit * 4
                ),
                timeout=30,
            )
            opportunities = []
            for item in public_results:
                opportunity = classifier.classify(
                    url=item["url"], title=item["title"], excerpt=item["excerpt"],
                    location=location,
                )
                if opportunity is not None:
                    opportunities.append({
                        "platform": opportunity.platform,
                        "source_url": opportunity.source_url,
                        "title": opportunity.title,
                        "intent_score": opportunity.intent_score,
                        "intent_signals": opportunity.intent_signals,
                    })
            report["b2c"] = {
                "public_results_read": len(public_results),
                "qualified_signals": len(opportunities),
                "results": opportunities,
                "contacts_created": 0,
                "messages_sent": 0,
            }
        except Exception as exc:  # noqa: BLE001 - evidence preserves each source failure
            report["b2c"] = {
                "public_results_read": 0, "qualified_signals": 0, "results": [],
                "contacts_created": 0, "messages_sent": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
    finally:
        await browser.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    failed = any("error" in report[key] for key in ("b2b", "b2c"))
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validação comercial B2B/B2C somente leitura.")
    parser.add_argument("--niche", default="estética")
    parser.add_argument("--location", default="Rio Grande do Sul")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("evidence/commercial-rs.json"))
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(
        niche=args.niche, location=args.location, limit=args.limit, output=args.output
    )))
