"""Bounded parsing and AI analysis adapters for public Hunter sources."""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urljoin


MAX_PUBLIC_PAGE_BYTES = 2_000_000


def parse_with_scrapling(html: str, base_url: str) -> tuple[str, list[str]]:
    """Use Scrapling's parser only; fetching remains under Kiara's SSRF guard."""
    from scrapling.parser import Selector

    page = Selector(html)
    text = page.css("body *:not(script):not(style):not(noscript) ::text").getall()
    links = page.css("a::attr(href)").getall()
    visible = " ".join(re.sub(r"\s+", " ", part).strip() for part in text if isinstance(part, str) and part.strip())
    return visible[:40000], [urljoin(base_url, link) for link in links if isinstance(link, str)][:500]


def fetch_public_with_scrapling(url: str) -> tuple[str, list[str], str]:
    """Fetch one public HTML page without cookies, proxies, or challenge solving.

    Scrapling's safe redirect mode rejects redirects to private/internal IPs. The
    caller still validates both the original and final destinations as a second
    SSRF boundary. This deliberately uses the lightweight HTTP fetcher rather
    than a logged-in or stealth browser session.
    """
    from scrapling.fetchers import Fetcher

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


def analyze_with_scrapegraph(source_url: str, prompt: str) -> dict[str, Any]:
    """Opt-in semantic hints, not verified contact facts or CRM evidence.

    The open-source graph requires an independently configured LLM. It must
    never run on arbitrary URLs or replace the deterministic contact parser.
    """
    model = os.getenv("KIARA_SCRAPEGRAPH_MODEL", "").strip()
    if not model:
        raise RuntimeError("scrapegraph_model_not_configured")
    from scrapegraphai.graphs import SmartScraperGraph

    llm: dict[str, Any] = {"model": model, "model_tokens": 4096}
    if key := os.getenv("KIARA_SCRAPEGRAPH_API_KEY", "").strip():
        llm["api_key"] = key
    graph = SmartScraperGraph(
        prompt=prompt[:500],
        source=source_url,
        config={"llm": llm, "headless": True, "verbose": False},
    )
    result = graph.run()
    return result if isinstance(result, dict) else {"unverified_hint": str(result)[:2000]}
