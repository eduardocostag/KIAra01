"""Bounded parsing and AI analysis adapters for public Hunter sources."""
from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urljoin


def parse_with_scrapling(html: str, base_url: str) -> tuple[str, list[str]]:
    """Use Scrapling's parser only; fetching remains under Kiara's SSRF guard."""
    from scrapling.parser import Selector

    page = Selector(html)
    text = page.css("body *:not(script):not(style):not(noscript) ::text").getall()
    links = page.css("a::attr(href)").getall()
    visible = " ".join(re.sub(r"\s+", " ", part).strip() for part in text if isinstance(part, str) and part.strip())
    return visible[:40000], [urljoin(base_url, link) for link in links if isinstance(link, str)][:500]


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
