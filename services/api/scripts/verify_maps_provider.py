"""One bounded Maps smoke: at most 3 public listings, counts only, no CRM writes."""
import asyncio
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kiara_api.hunter import maps_search


async def main():
    needed = {"BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID"}
    for line in (Path(__file__).resolve().parents[1] / ".env.local").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in needed:
            os.environ[key] = json.loads(value) if value.startswith('"') else value
    missing = sorted(key for key in needed if not os.getenv(key))
    if missing:
        print(json.dumps({"missing_configuration": missing}))
        return
    logging.disable(logging.CRITICAL)
    results = await asyncio.wait_for(maps_search("psicólogos São Paulo", 3), timeout=130)
    print(json.dumps({"returned": len(results), "inspected": sum(bool(r.get("public_data", {}).get("detail_inspected")) for r in results),
        "with_phone": sum(bool(r.get("public_data", {}).get("phone")) for r in results),
        "with_whatsapp_link": sum(bool(r.get("public_data", {}).get("whatsapp_url")) for r in results),
        "website_statuses": [r.get("public_data", {}).get("website_status") for r in results]}))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        message = str(error)
        safe_code = message if message in {
            "maps_results_unavailable", "browserbase_not_configured",
            "browser_provider_unavailable",
        } else "unclassified_provider_error"
        print(json.dumps({"error_type": type(error).__name__, "error_code": safe_code}))
        sys.exit(1)
