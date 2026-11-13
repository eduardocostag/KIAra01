"""Bounded parsing and AI analysis adapters for public Hunter sources."""
from __future__ import annotations

import os
import re
from html import escape
from typing import Any
from urllib.parse import urljoin

MAX_PUBLIC_PAGE_BYTES = 2_000_000


def parse_with_scrapling(html: str, base_url: str) -> tuple[str, list[str]]:
    """Use Scrapling's parser only; fetching remains under Kiara's SSRF guard."""
    from scrapling.parser import Selector

    page = Selector(html)
    # Exclude the whole subtree: a CSS descendant text selector also includes
    # script/style contents through their parent div and pollutes contact facts.
    text = page.xpath(
        "//body//text()[not(ancestor::script or ancestor::style or ancestor::noscript "
        "or ancestor::template or ancestor::*[@hidden or @aria-hidden='true'])]"
    ).getall()
    links = page.xpath(
        "//body//a[not(ancestor::script or ancestor::style or ancestor::noscript "
        "or ancestor::template or ancestor-or-self::*[@hidden or @aria-hidden='true'])]/@href"
    ).getall()
    visible = " ".join(re.sub(r"\s+", " ", part).strip() for part in text if isinstance(part, str) and part.strip())
    return visible[:40000], [urljoin(base_url, link) for link in links if isinstance(link, str)][:500]


def fetch_public_with_scrapling(url: str) -> tuple[str, list[str], str]:
    """Fetch one public HTML page without cookies, proxies, or challenge solving.

    Scrapling's safe redirect mode rejects redirects to private/internal IPs. The
    caller still validates both the original and final destinations as a second
    SSRF boundary. This deliberately uses the lightweight HTTP fetcher rather
    than a logged-in or stealth browser session.
    """
    try:
        from scrapling.fetchers import Fetcher
    except ImportError:
        # On Vercel Scrapling's fetchers are unavailable (they pull Patchright, which exhausts the
        # Function disk). curl_cffi is the engine behind Scrapling's HTTP fetcher: the same
        # Chrome TLS/HTTP2 fingerprint that keeps public sites from blocking the request.
        return fetch_public_with_curl_cffi(url)

    page = Fetcher.get(
        url,
        stealthy_headers=True,
        impersonate="chrome",
        follow_redirects="safe",
        max_redirects=5,
        timeout=12,
        retries=1,
        headers={"Accept": "text/html,application/xhtml+xml;q=0.9"},
    )
    status = int(getattr(page, "status", 0) or 0)
    if not 200 <= status < 300:
        raise OSError(f"public_page_http_{status}")
    body = bytes(getattr(page, "body", b""))
    if len(body) > MAX_PUBLIC_PAGE_BYTES:
        raise ValueError("page_too_large")
    headers = {str(key).lower(): str(value) for key, value in dict(getattr(page, "headers", {}) or {}).items()}
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError("unsupported_content")
    encoding = str(getattr(page, "encoding", "") or "utf-8")
    final_url = str(getattr(page, "url", "") or url)
    text, links = parse_with_scrapling(body.decode(encoding, errors="replace"), final_url)
    return text, links, final_url


def fetch_public_with_curl_cffi(url: str, max_redirects: int = 5) -> tuple[str, list[str], str]:
    """Fetch a public HTML page impersonating Chrome, re-checking SSRF on every redirect."""
    from urllib.parse import urljoin as join

    from curl_cffi import requests as curl_requests

    from .hunter import _assert_public_destination

    current = url
    for _ in range(max_redirects + 1):
        _assert_public_destination(current)
        response = curl_requests.get(
            current, impersonate="chrome", allow_redirects=False, timeout=12, stream=True,
            headers={"Accept": "text/html,application/xhtml+xml;q=0.9", "Accept-Language": "pt-BR,pt;q=0.9"},
        )
        try:
            if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
                current = join(current, response.headers["location"])
                continue
            if not 200 <= response.status_code < 300:
                raise OSError(f"public_page_http_{response.status_code}")
            content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
            if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
                raise ValueError("unsupported_content")
            body = bytearray()
            for chunk in response.iter_content():
                body.extend(chunk)
                if len(body) > MAX_PUBLIC_PAGE_BYTES:
                    raise ValueError("page_too_large")
            charset = re.search(r"charset=([\w-]+)", response.headers.get("content-type") or "", re.IGNORECASE)
            text, links = parse_with_scrapling(bytes(body).decode(charset.group(1) if charset else "utf-8", errors="replace"), current)
            return text, links, current
        finally:
            response.close()
    raise ValueError("too_many_redirects")


def analyze_with_scrapegraph(source_url: str, prompt: str) -> dict[str, Any]:
    """Opt-in semantic hints, not verified contact facts or CRM evidence.

    The open-source graph requires an independently configured LLM. It must
    never run on arbitrary URLs or replace the deterministic contact parser.
    """
    model = os.getenv("KIARA_SCRAPEGRAPH_MODEL", "").strip()
    if not model:
        raise RuntimeError("scrapegraph_model_not_configured")
    from scrapegraphai.graphs import SmartScraperGraph

    # Reuse the bounded public HTTP fetcher. Giving the graph a URL starts its
    # own browser, which cannot run on psycopg's Windows Selector loop and
    # bypasses Kiara's fetch limits. Raw HTML is an upstream-supported source.
    text, _, _ = fetch_public_with_scrapling(source_url)
    if not text.strip():
        raise ValueError("empty_public_page")
    llm: dict[str, Any] = {"model": model, "model_tokens": 4096}
    if key := os.getenv("KIARA_SCRAPEGRAPH_API_KEY", "").strip():
        llm["api_key"] = key
    graph = SmartScraperGraph(
        prompt=prompt[:500],
        source="<html><body>" + escape(text[:12000]) + "</body></html>",
        config={"llm": llm, "headless": True, "verbose": False},
    )
    result = graph.run()
    return result if isinstance(result, dict) else {"unverified_hint": str(result)[:2000]}
