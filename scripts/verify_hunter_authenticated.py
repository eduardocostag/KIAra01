"""Wait for interactive sign-in, then exercise two real production searches.

No passwords, cookies, tokens or lead contact data are written to the report.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/social-leads-authenticated/report.json"
WEB = "https://kiaralead.vercel.app"


def save(report: dict) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> None:
    report = {"checked_at": datetime.now(UTC).isoformat(), "status": "awaiting_login", "searches": []}
    save(report)
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(viewport={"width": 1360, "height": 900})
        page = await context.new_page()
        try:
            await page.goto(WEB + "/sign-in", wait_until="domcontentloaded", timeout=60000)
            print("Login window ready; waiting for user authentication.", flush=True)
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                if page.is_closed():
                    raise RuntimeError("login_window_closed")
                if page.url.startswith(WEB + "/app"):
                    response = await context.request.get(WEB + "/api/hunter/searches", timeout=60000)
                    if response.status == 200:
                        break
                await asyncio.sleep(3)
            else:
                raise RuntimeError("login_timeout")
            report.update(status="authenticated", authenticated_api_status=200)
            save(report)
            print("Authenticated through the production application.", flush=True)
            for source in ("instagram", "facebook"):
                result = {"source": source, "query": "clinicas odontologicas", "location": "Porto Alegre RS"}
                report["searches"].append(result)
                save(report)
                response = await context.request.post(WEB + "/api/hunter/searches", data={
                    "market": "b2b", "query": result["query"], "location": result["location"],
                    "sources": [source], "result_limit": 2,
                }, timeout=60000)
                result["create_status"] = response.status
                if response.status != 201:
                    result["error"] = "create_failed"
                    save(report)
                    continue
                job = await response.json()
                search_id = job["id"]
                result["search_id"] = search_id
                base = WEB + "/api/hunter/searches/" + search_id
                response = await context.request.post(base + "/confirm", timeout=60000)
                result["confirm_status"] = response.status
                if response.status != 200:
                    result["error"] = "confirm_failed"
                    save(report)
                    continue
                try:
                    response = await context.request.post(base + "/process", timeout=245000)
                    result["process_status"] = response.status
                except Exception as exc:
                    result["process_transport_error"] = type(exc).__name__
                poll_until = time.monotonic() + 240
                while time.monotonic() < poll_until:
                    response = await context.request.get(base, timeout=60000)
                    if response.status != 200:
                        result["read_status"] = response.status
                        break
                    job = await response.json()
                    if job["status"] in {"completed", "failed", "cancelled"}:
                        break
                    await asyncio.sleep(5)
                rows = job.get("results", [])
                result.update(status=job.get("status"), accepted=len(rows), validation=job.get("validation"),
                              warnings=job.get("warnings", []), error_code=job.get("error_code"),
                              sync_summary=job.get("sync_summary"),
                              with_phone=sum(bool(row.get("public_data", {}).get("phone")) for row in rows),
                              with_profile_evidence=sum(row.get("public_data", {}).get("bio_status") == "verified_public_profile" for row in rows))
                save(report)
                print(json.dumps(result, ensure_ascii=True), flush=True)
            report["status"] = "finished"
            save(report)
        except Exception as exc:
            report.update(status="interrupted", error_type=type(exc).__name__)
            save(report)
            print(json.dumps({"status": "interrupted", "error_type": type(exc).__name__}), flush=True)
        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
