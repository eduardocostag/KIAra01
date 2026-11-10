"""Read-only production smoke checks; never signs in or sends customer messages."""
from __future__ import annotations

import argparse
import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

WEB = "https://kiaralead.vercel.app"
API = "https://kiara-api-rouge.vercel.app"
ROOT = Path(__file__).resolve().parents[1]


def request_status(url: str, *, method: str = "GET") -> dict[str, object]:
    body = json.dumps({"text": "Release authentication check",
                       "idempotency_key": "release-authentication-check"}).encode() if method == "POST" else None
    request = urllib.request.Request(url, method=method, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"status": response.status, "host": urlsplit(response.url).hostname,
                    "path": urlsplit(response.url).path}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "host": urlsplit(url).hostname,
                "path": urlsplit(url).path}


async def browser_check() -> dict[str, object]:
    from playwright.async_api import async_playwright

    folder = ROOT / "evidence/commercial-release"
    folder.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        try:
            context = await browser.new_context(viewport={"width": 1440, "height": 1000})
            page = await context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            response = await page.goto(WEB + "/sign-in", wait_until="networkidle", timeout=60000)
            await page.locator('input[name="login"]').wait_for(timeout=20000)
            desktop_form = await page.locator('input[name="login"]').is_visible()
            await page.screenshot(path=str(folder / "sign-in-desktop.png"), full_page=True)
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.screenshot(path=str(folder / "sign-in-mobile.png"), full_page=True)
            mobile_form = await page.locator('input[name="login"]').is_visible()
            await page.goto(WEB + "/app/inbox", wait_until="networkidle", timeout=60000)
            protected = urlsplit(page.url).path.startswith("/sign-in")
            if not desktop_form or not mobile_form or not protected or errors:
                raise RuntimeError("Browser smoke check failed; inspect local evidence.")
            return {"sign_in_status": response.status, "desktop_form": desktop_form,
                    "mobile_form": mobile_form, "inbox_requires_login": protected,
                    "uncaught_browser_errors": len(errors), "evidence": str(folder)}
        finally:
            await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    checks = {
        "api_live": request_status(API + "/health/live"),
        "api_ready": request_status(API + "/health/ready"),
        "api_inbox_unauthenticated": request_status(API + "/v1/inbox/threads"),
        "web_sign_in": request_status(WEB + "/sign-in"),
        "web_send_unauthenticated": request_status(
            WEB + "/api/inbox/release-check/messages", method="POST",
        ),
    }
    expected = {"api_live": 200, "api_ready": 200, "api_inbox_unauthenticated": 401,
                "web_sign_in": 200, "web_send_unauthenticated": 401}
    if any(checks[key]["status"] != status for key, status in expected.items()):
        print(json.dumps(checks, indent=2))
        raise SystemExit("Production smoke check failed.")
    if args.browser:
        checks["browser"] = asyncio.run(browser_check())
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
