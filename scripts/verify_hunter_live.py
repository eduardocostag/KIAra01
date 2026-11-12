"""Exercise real Hunter providers without saving leads or exposing contact data."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
sys.path.insert(0, str(ROOT / "services/api/scripts"))

from apply_migrations import load_env
from kiara_api.hunter import SearchCreate, execute_research
from kiara_api.hunter_research import lead_requirement_gaps, phone_number, whatsapp_link


async def verify(request: SearchCreate, timeout: float) -> dict:
    started = time.monotonic()
    outcome = await asyncio.wait_for(execute_research(request.model_dump()), timeout)
    rows = outcome["results"]
    gaps = Counter(gap for row in rows for gap in lead_requirement_gaps(row, request.model_dump()))
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "mode": "real_providers_no_persistence",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "requested": request.result_limit,
        "accepted": len(rows),
        "requested_limit_reached": len(rows) == request.result_limit,
        "all_sources_succeeded": outcome["validation"].get("source_failures", 0) == 0,
        "sources": dict(Counter(row["source"] for row in rows)),
        "with_phone": sum(bool(phone_number(row["public_data"].get("phone"))) for row in rows),
        "with_public_whatsapp": sum(bool(whatsapp_link(row["public_data"].get("whatsapp_url"))) for row in rows),
        "requirement_gaps": dict(gaps),
        "validation": outcome["validation"],
        "warnings": outcome["warnings"],
        "error": outcome["error"],
        "passed": bool(rows) and not gaps and not outcome["error"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--location", required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--sources", nargs="+", choices=["web", "google_maps", "instagram", "facebook"], default=["google_maps", "web"])
    parser.add_argument("--env-file", type=Path, default=ROOT / "services/api/.env.local")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_env(args.env_file)
    request = SearchCreate(market="b2b", query=args.query, location=args.location,
                           sources=args.sources, result_limit=args.limit)
    try:
        report = asyncio.run(verify(request, args.timeout))
    except Exception as error:  # noqa: BLE001 - Sanitized boundary for external provider failures.
        # Provider errors may include request URLs or credentials; print only type.
        report = {"passed": False, "error_type": type(error).__name__,
                  "mode": "real_providers_no_persistence"}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
