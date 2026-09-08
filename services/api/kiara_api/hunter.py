from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import quote, urlsplit
from dataclasses import dataclass
from typing import Any, Literal
from urllib.request import Request as UrlRequest, urlopen
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field, field_validator

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

ALLOWED_SOURCES = {"web", "google_maps", "instagram", "linkedin"}
DOMAIN_BY_SOURCE = {"instagram": "instagram.com", "linkedin": "linkedin.com"}


class SearchCreate(BaseModel):
    market: str
    query: str = Field(min_length=2, max_length=300)
    location: str | None = Field(default=None, max_length=160)
    sources: list[str] = Field(min_length=1, max_length=4)
    result_limit: int = Field(default=10, ge=1, le=20)
    research_mode: Literal["broad", "focused"] = "broad"
    objective: str = Field(default="", max_length=500)

    @field_validator("query", "objective", "location", mode="before")
    @classmethod
    def trim_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("market")
    @classmethod
    def valid_market(cls, value: str) -> str:
        if value not in {"b2c", "b2b"}:
            raise ValueError("market must be b2c or b2b")
        return value

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, value: list[str]) -> list[str]:
        unique = list(dict.fromkeys(value))
        if set(unique) - ALLOWED_SOURCES:
            raise ValueError("unsupported source")
        return unique


@dataclass(slots=True)
class HunterRepository:
    database: PostgresRepository

    async def create(self, context: RequestContext, payload: SearchCreate) -> dict[str, Any]:
        org, user = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute(
                "INSERT INTO users (id,identity_provider,external_subject) VALUES (%s,'clerk',%s) ON CONFLICT (id) DO NOTHING",
                (user, context.user_id),
            )
            row = await (await connection.execute(
                """INSERT INTO hunter_searches
                   (organization_id,requested_by,market,query,location,sources,result_limit)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (org, user, payload.market, payload.query.strip(), payload.location or None,
                 payload.sources, payload.result_limit),
            )).fetchone()
            await connection.execute(
                "INSERT INTO audit_events (organization_id,actor_user_id,action,resource_type,resource_id,correlation_id,metadata) VALUES (%s,%s,'hunter.search.requested','hunter_search',%s,%s,%s)",
                (org, user, row["id"], context.correlation_id, json.dumps({
                    "sources": payload.sources, "research_mode": payload.research_mode,
                    "objective": payload.objective if payload.research_mode == "focused" else "",
                })),
            )
            await self._attach_options(connection, org, row)
        return self._search(row, [])

    async def list(self, context: RequestContext) -> list[dict[str, Any]]:
        org = _uuid("organization", context.organization_id)
        async with self.database._transaction(context.organization_id) as connection:
            searches = await (await connection.execute(
                "SELECT * FROM hunter_searches WHERE organization_id=%s ORDER BY created_at DESC LIMIT 30", (org,)
            )).fetchall()
            results = await (await connection.execute(
                "SELECT * FROM hunter_results WHERE organization_id=%s AND search_id=ANY(%s) ORDER BY created_at,id",
                (org, [row["id"] for row in searches]),
            )).fetchall() if searches else []
            if searches:
                options = await (await connection.execute(
                    "SELECT resource_id,metadata FROM audit_events WHERE organization_id=%s AND action='hunter.search.requested' AND resource_id=ANY(%s)",
                    (org, [row["id"] for row in searches]),
                )).fetchall()
                by_id = {item["resource_id"]: item["metadata"] for item in options}
                for row in searches:
                    row["search_options"] = by_id.get(row["id"], {})
        grouped: dict[UUID, list[dict[str, Any]]] = {}
        for result in results:
            grouped.setdefault(result["search_id"], []).append(self._result(result))
        return [self._search(row, grouped.get(row["id"], [])) for row in searches]

    async def claim_confirmation(self, context: RequestContext, search_id: str) -> dict[str, Any]:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Seu perfil não pode confirmar pesquisas.")
        org, sid, user = (_uuid("organization", context.organization_id),
                          _uuid("hunter_search", search_id), _uuid("user", context.user_id))
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute(
                "INSERT INTO users (id,identity_provider,external_subject) VALUES (%s,'clerk',%s) ON CONFLICT (id) DO NOTHING",
                (user, context.user_id),
            )
            row = await (await connection.execute(
                "SELECT * FROM hunter_searches WHERE organization_id=%s AND id=%s FOR UPDATE", (org, sid)
            )).fetchone()
            if not row:
                raise ApiError(404, "hunter_search_not_found", "Pesquisa não encontrada.")
            if row["status"] != "pending_confirmation":
                raise ApiError(409, "hunter_search_already_confirmed", "Esta pesquisa já foi confirmada.")
            row = await (await connection.execute(
                "UPDATE hunter_searches SET status='running',confirmed_by=%s,confirmed_at=now(),updated_at=now() WHERE organization_id=%s AND id=%s RETURNING *",
                (user, org, sid),
            )).fetchone()
            await self._attach_options(connection, org, row)
            await connection.execute(
                "INSERT INTO audit_events (organization_id,actor_user_id,action,resource_type,resource_id,correlation_id) VALUES (%s,%s,'hunter.search.confirmed','hunter_search',%s,%s)",
                (org, user, sid, context.correlation_id),
            )
        return self._search(row, [])

    async def finish(self, context: RequestContext, search_id: str, results: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
        org, sid = _uuid("organization", context.organization_id), _uuid("hunter_search", search_id)
        async with self.database._transaction(context.organization_id) as connection:
            for result in results:
                await connection.execute(
                    """INSERT INTO hunter_results (organization_id,search_id,source,title,url,summary,public_data)
                       VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,search_id,url) DO NOTHING""",
                    (org, sid, result["source"], result["title"][:500], result["url"][:3000],
                     result.get("summary"), json.dumps(result.get("public_data", {}))),
                )
            row = await (await connection.execute(
                "UPDATE hunter_searches SET status=%s,error_code=%s,updated_at=now() WHERE organization_id=%s AND id=%s RETURNING *",
                ("failed" if error else "completed", error, org, sid),
            )).fetchone()
            await self._attach_options(connection, org, row)
            saved = await (await connection.execute(
                "SELECT * FROM hunter_results WHERE organization_id=%s AND search_id=%s ORDER BY created_at,id", (org, sid)
            )).fetchall()
        return self._search(row, [self._result(item) for item in saved])

    @staticmethod
    async def _attach_options(connection: Any, org: UUID, row: dict[str, Any]) -> None:
        event = await (await connection.execute(
            "SELECT metadata FROM audit_events WHERE organization_id=%s AND resource_id=%s AND action='hunter.search.requested' ORDER BY occurred_at DESC LIMIT 1",
            (org, row["id"]),
        )).fetchone()
        row["search_options"] = event["metadata"] if event else {}

    @staticmethod
    def _result(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(row["id"]), "source": row["source"], "title": row["title"],
                "url": row["url"], "summary": row["summary"], "public_data": row["public_data"]}

    @staticmethod
    def _search(row: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
        options = row.get("search_options") or {}
        return {"id": str(row["id"]), "market": row["market"], "query": row["query"],
                "research_mode": options.get("research_mode", "broad"),
                "objective": options.get("objective", ""),
                "location": row["location"], "sources": row["sources"], "result_limit": row["result_limit"],
                "status": row["status"], "confirmed_at": _iso(row["confirmed_at"]),
                "created_at": _iso(row["created_at"]), "error_code": row["error_code"], "results": results}


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    request = UrlRequest(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read())


async def exa_search(query: str, source: str, limit: int) -> list[dict[str, Any]]:
    key = os.getenv("EXA_API_KEY")
    if not key:
        raise RuntimeError("exa_not_configured")
    body: dict[str, Any] = {"query": query, "type": "auto", "numResults": limit,
                            "contents": {"highlights": {"maxCharacters": 700}}}
    if source in DOMAIN_BY_SOURCE:
        body["includeDomains"] = [DOMAIN_BY_SOURCE[source]]
    data = await asyncio.to_thread(_post_json, "https://api.exa.ai/search",
                                   {"Content-Type": "application/json", "x-api-key": key}, body)
    return [{"source": source, "title": item.get("title") or "Resultado público",
             "url": item.get("url") or "", "summary": " ".join(item.get("highlights") or [])[:1500]}
            for item in data.get("results", []) if item.get("url")]


async def enrich_results(results: list[dict[str, Any]]) -> None:
    """Enrich up to three public websites, preserving results on provider failure."""
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not key:
        return
    candidates = [item for item in results if item.get("source") == "web"
                  and urlsplit(item.get("url", "")).scheme == "https"][:3]

    async def enrich(item: dict[str, Any]) -> None:
        try:
            response = await asyncio.to_thread(
                _post_json, "https://api.firecrawl.dev/v2/scrape",
                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                {"url": item["url"], "formats": ["markdown"], "onlyMainContent": True,
                 "timeout": 20000},
            )
            content = (response.get("data") or {}).get("markdown")
            if response.get("success") and isinstance(content, str) and content.strip():
                item["public_data"] = {"enrichment": "completed", "provider": "firecrawl",
                                       "source_url": item["url"], "content": content[:12000]}
                item["summary"] = content[:1500]
            else:
                item["public_data"] = {"enrichment": "unavailable"}
        except Exception:
            item["public_data"] = {"enrichment": "unavailable"}

    await asyncio.gather(*(enrich(item) for item in candidates))


async def maps_search(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        from browserbase import Browserbase
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("browser_provider_unavailable") from exc
    key, project = os.getenv("BROWSERBASE_API_KEY"), os.getenv("BROWSERBASE_PROJECT_ID")
    if not key or not project:
        raise RuntimeError("browserbase_not_configured")
    session = await asyncio.to_thread(Browserbase(api_key=key).sessions.create, project_id=project)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(session.connect_url)
        page = browser.contexts[0].pages[0]
        await page.goto(f"https://www.google.com/maps/search/{quote(query, safe='')}", wait_until="domcontentloaded", timeout=45_000)
        try:
            await page.wait_for_selector('a[href*="/maps/place/"]', timeout=15_000)
        except Exception:
            pass
        items = await page.locator('a[href*="/maps/place/"]').evaluate_all(
            "els => [...new Map(els.map(e => [e.href, {title: e.getAttribute('aria-label') || e.textContent.trim(), url: e.href}])).values()]"
        )
        await browser.close()
    return [{"source": "google_maps", "title": item["title"] or "Empresa no Google Maps",
             "url": item["url"], "summary": "Perfil empresarial público no Google Maps."}
            for item in items[:limit]]


def research_query(search: dict[str, Any]) -> str:
    base = " ".join(filter(None, [search["query"], search.get("location")]))
    objective = search.get("objective", "").strip()
    if search.get("research_mode") == "focused" and objective:
        return f"{base}. Critério de interesse: {objective}"
    return base


def create_hunter_router(repository: HunterRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/hunter", tags=["hunter"])

    @router.post("/searches", status_code=201)
    async def create_search(payload: SearchCreate, context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:
        return await repository.create(context, payload)

    @router.get("/searches")
    async def list_searches(context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:
        return {"items": await repository.list(context)}

    @router.post("/searches/{search_id}/confirm")
    async def confirm_search(search_id: str, request: Request,
                             idempotency_key: str = Header(min_length=8, max_length=200),
                             context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:
        del request, idempotency_key
        search = await repository.claim_confirmation(context, search_id)
        full_query = research_query(search)
        per_source = max(1, search["result_limit"] // len(search["sources"]))
        try:
            batches = await asyncio.gather(*[
                maps_search(full_query, per_source) if source == "google_maps"
                else exa_search(full_query, source, per_source)
                for source in search["sources"]
            ])
            results = [item for batch in batches for item in batch][:search["result_limit"]]
            await enrich_results(results)
            if search.get("research_mode") == "focused" and search.get("objective"):
                for result in results:
                    result.setdefault("public_data", {}).update({
                        "research_objective": search["objective"],
                        "criterion_status": "not_verified",
                    })
            return await repository.finish(context, search_id, results)
        except Exception as exc:
            code = str(exc) if str(exc) in {"exa_not_configured", "browserbase_not_configured", "browser_provider_unavailable"} else "provider_error"
            await repository.finish(context, search_id, [], code)
            raise ApiError(502, code, "A fonte externa não concluiu a pesquisa. Tente novamente mais tarde.") from exc

    return router
