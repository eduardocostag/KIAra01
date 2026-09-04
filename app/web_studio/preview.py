from __future__ import annotations

import asyncio
import functools
import threading
from dataclasses import asdict, dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ViewportResult:
    name: str
    width: int
    height: int
    horizontal_overflow: bool
    console_errors: tuple[str, ...]
    page_errors: tuple[str, ...]
    screenshot_checked: bool


@dataclass(frozen=True, slots=True)
class SitePreviewReport:
    passed: bool
    title: str
    external_requests: tuple[str, ...]
    accessibility_issues: tuple[str, ...]
    viewports: tuple[ViewportResult, ...]

    def as_metadata(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "title": self.title,
            "external_requests": list(self.external_requests),
            "accessibility_issues": list(self.accessibility_issues),
            "viewports": [asdict(item) for item in self.viewports],
        }


class _PreviewHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


class SitePreviewValidator:
    VIEWPORTS: ClassVar[tuple[tuple[str, int, int], ...]] = (
        ("mobile", 390, 844),
        ("tablet", 768, 1024),
        ("desktop", 1440, 900),
    )

    def __init__(self, output_root: Path, *, timeout_ms: int = 10_000) -> None:
        self.output_root = output_root.resolve()
        self.timeout_ms = max(1_000, timeout_ms)

    def resolve_project(self, project: str | Path) -> Path:
        candidate = Path(project)
        if not candidate.is_absolute():
            candidate = self.output_root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.output_root) or not resolved.is_dir():
            raise ValueError("Projeto fora da pasta autorizada ou inexistente.")
        if not (resolved / "index.html").is_file():
            raise ValueError("Projeto sem index.html.")
        return resolved

    async def validate(self, project: str | Path) -> SitePreviewReport:
        directory = self.resolve_project(project)
        handler = functools.partial(_PreviewHandler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/index.html"
        try:
            return await self._validate_browser(url)
        finally:
            await asyncio.to_thread(server.shutdown)
            server.server_close()
            thread.join(timeout=2)

    async def _validate_browser(self, url: str) -> SitePreviewReport:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright não está instalado para validar o site.") from exc

        external_requests: set[str] = set()
        viewport_results: list[ViewportResult] = []
        accessibility_issues: set[str] = set()
        title = ""
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                for name, width, height in self.VIEWPORTS:
                    context = await browser.new_context(viewport={"width": width, "height": height})

                    async def guard(route, request) -> None:
                        host = urlparse(request.url).hostname
                        if host not in {"127.0.0.1", None}:
                            external_requests.add(request.url[:500])
                            await route.abort("blockedbyclient")
                            return
                        await route.continue_()

                    await context.route("**/*", guard)
                    page = await context.new_page()
                    console_errors: list[str] = []
                    page_errors: list[str] = []
                    page.on(
                        "console",
                        lambda message, errors=console_errors: (
                            errors.append(message.text[:500]) if message.type == "error" else None
                        ),
                    )
                    page.on(
                        "pageerror",
                        lambda error, errors=page_errors: errors.append(str(error)[:500]),
                    )
                    await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                    title = await page.title()
                    checks = await page.evaluate(
                        """() => ({
                          overflow: document.documentElement.scrollWidth > innerWidth + 1,
                          main: document.querySelectorAll('main').length,
                          h1: document.querySelectorAll('h1').length,
                          imagesWithoutAlt: [...document.images].filter(i => !i.hasAttribute('alt')).length,
                          unnamedButtons: [...document.querySelectorAll('button')]
                            .filter(b => !(b.textContent || '').trim() && !b.getAttribute('aria-label')).length,
                          unlabeledInputs: [...document.querySelectorAll('input,textarea,select')]
                            .filter(e => !e.labels?.length && !e.getAttribute('aria-label')).length
                        })"""
                    )
                    if checks["main"] != 1:
                        accessibility_issues.add(
                            "A página deve possuir exatamente um elemento main."
                        )
                    if checks["h1"] != 1:
                        accessibility_issues.add("A página deve possuir exatamente um título h1.")
                    if checks["imagesWithoutAlt"]:
                        accessibility_issues.add("Existem imagens sem atributo alt.")
                    if checks["unnamedButtons"]:
                        accessibility_issues.add("Existem botões sem nome acessível.")
                    if checks["unlabeledInputs"]:
                        accessibility_issues.add("Existem campos sem rótulo acessível.")
                    screenshot = await page.screenshot(full_page=True, type="png")
                    viewport_results.append(
                        ViewportResult(
                            name,
                            width,
                            height,
                            bool(checks["overflow"]),
                            tuple(console_errors),
                            tuple(page_errors),
                            bool(screenshot),
                        )
                    )
                    await context.close()
            finally:
                await browser.close()
        passed = (
            bool(title.strip())
            and not external_requests
            and not accessibility_issues
            and all(
                not item.horizontal_overflow
                and not item.console_errors
                and not item.page_errors
                and item.screenshot_checked
                for item in viewport_results
            )
        )
        return SitePreviewReport(
            passed,
            title,
            tuple(sorted(external_requests)),
            tuple(sorted(accessibility_issues)),
            tuple(viewport_results),
        )
