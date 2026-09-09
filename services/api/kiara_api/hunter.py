from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field, field_validator

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
from .hunter_crm import sync_hunter_results
from .hunter_research import (
    clean_summary,
    extract_contacts,
    filter_results,
    maps_detail_result,
    normalize_result,
    research_options,
    safe_public_url,
)

ALLOWED_SOURCES = {"web", "google_maps", "instagram", "linkedin"}
DOMAIN_BY_SOURCE = {"instagram": "instagram.com", "linkedin": "linkedin.com"}
SOURCE_TIMEOUT_SECONDS = 130
ENRICHMENT_TIMEOUT_SECONDS = 25
SOURCE_LABELS = {"web": "Web pública", "google_maps": "Google Maps", "instagram": "Instagram", "linkedin": "LinkedIn"}
logger = logging.getLogger(__name__)


class SearchCreate(BaseModel):
    market: str
    query: str = Field(min_length=2, max_length=300)
    location: str | None = Field(default=None, max_length=160)
    sources: list[str] = Field(min_length=1, max_length=4)
    result_limit: int = Field(default=10, ge=1, le=20)
    research_mode: Literal["broad", "focused"] = "broad"
    objective: str = Field(default="", max_length=500)
    website_filter: Literal["any", "without_website", "with_website"] = "any"
    contact_filter: Literal["any", "phone", "whatsapp"] = "any"

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
        filters = research_options(payload.model_dump())
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
                    "website_filter": filters["website_filter"], "contact_filter": filters["contact_filter"],
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
                    "SELECT resource_id,metadata FROM audit_events WHERE organization_id=%s AND action IN ('hunter.search.requested','hunter.search.finished') AND resource_id=ANY(%s) ORDER BY occurred_at",
                    (org, [row["id"] for row in searches]),
                )).fetchall()
                by_id: dict[UUID, dict[str, Any]] = {}
                for item in options:
                    by_id.setdefault(item["resource_id"], {}).update(item["metadata"])
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

    async def finish(self, context: RequestContext, search_id: str, results: list[dict[str, Any]], error: str | None = None,
                     *, validation: dict[str, int] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
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
            summary = {"created": 0, "existing": 0, "skipped": 0}
            if not error:
                summary = await sync_hunter_results(connection, org, self._search(row, []), saved)
            outcome = {"validation": validation or {}, "warnings": warnings or [], "sync_summary": summary}
            await connection.execute(
                "INSERT INTO audit_events (organization_id,actor_user_id,action,resource_type,resource_id,correlation_id,metadata) VALUES (%s,%s,'hunter.search.finished','hunter_search',%s,%s,%s)",
                (org, _uuid("user", context.user_id), sid, context.correlation_id, json.dumps(outcome)),
            )
            row["search_options"].update(outcome)
        return self._search(row, [self._result(item) for item in saved])

    @staticmethod
    async def _attach_options(connection: Any, org: UUID, row: dict[str, Any]) -> None:
        events = await (await connection.execute(
            "SELECT metadata FROM audit_events WHERE organization_id=%s AND resource_id=%s AND action IN ('hunter.search.requested','hunter.search.finished') ORDER BY occurred_at",
            (org, row["id"]),
        )).fetchall()
        row["search_options"] = {}
        for event in events:
            row["search_options"].update(event["metadata"])

    @staticmethod
    def _result(row: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_result(row)
        return {"id": str(row["id"]), "source": row["source"], "title": normalized["title"],
                "url": row["url"], "summary": normalized["summary"], "public_data": normalized["public_data"]}

    @staticmethod
    def _search(row: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
        options = row.get("search_options") or {}
        payload = {"id": str(row["id"]), "market": row["market"], "query": row["query"],
                "research_mode": options.get("research_mode", "broad"),
                "objective": options.get("objective", ""),
                "website_filter": options.get("website_filter", "any"),
                "contact_filter": options.get("contact_filter", "any"),
                "validation": options.get("validation", {}), "warnings": options.get("warnings", []),
                "sync_summary": options.get("sync_summary", {}),
                "location": row["location"], "sources": row["sources"], "result_limit": row["result_limit"],
                "status": row["status"], "confirmed_at": _iso(row["confirmed_at"]),
                "created_at": _iso(row["created_at"]), "error_code": row["error_code"], "results": results}
        inferred = research_options(payload)
        payload["website_filter"] = inferred["website_filter"]
        payload["contact_filter"] = inferred["contact_filter"]
        legacy = any(item.get("public_data", {}).get("verification_version") != 1 for item in results)
        if legacy and row["status"] == "completed":
            # Read-time compatibility only: do not delete historical records or
            # quietly import them into CRM as newly verified discoveries.
            if inferred["website_filter"] != "any" or inferred["contact_filter"] != "any":
                payload["results"], payload["validation"] = filter_results(results, payload)
            for item in payload["results"]:
                item["public_data"].update({"criterion_status": "not_verified", "verification_version": 0})
            payload["warnings"] = [*payload["warnings"],
                "Pesquisa antiga: resultados sem evidência para os filtros foram ocultados. Execute uma nova pesquisa para validar contatos e importar para o CRM."]
        return payload


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
                  and (safe_public_url(item.get("url")) or "").startswith("https://")][:3]

    async def enrich(item: dict[str, Any]) -> None:
        try:
            response = await asyncio.to_thread(
                _post_json, "https://api.firecrawl.dev/v2/scrape",
                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                {"url": item["url"], "formats": ["markdown", "links"], "onlyMainContent": True,
                 "timeout": 20000},
            )
            content = (response.get("data") or {}).get("markdown")
            if response.get("success") and isinstance(content, str) and content.strip():
                contacts = extract_contacts(content[:40000], (response.get("data") or {}).get("links") or [])
                item.setdefault("public_data", {}).update({
                    "enrichment": "completed", "provider": "firecrawl", "source_url": item["url"], **contacts,
                })
                item["summary"] = clean_summary(content)
            else:
                item.setdefault("public_data", {})["enrichment"] = "unavailable"
        except (OSError, ValueError, TypeError, AttributeError):
            item.setdefault("public_data", {})["enrichment"] = "unavailable"

    await asyncio.gather(*(enrich(item) for item in candidates))


async def maps_search(query: str, limit: int) -> list[dict[str, Any]]:
    try:
        import playwright.async_api  # noqa: F401 — check optional dependency before creating a paid session
        from browserbase import Browserbase
    except ImportError as exc:
        raise RuntimeError("browser_provider_unavailable") from exc
    key, project = os.getenv("BROWSERBASE_API_KEY"), os.getenv("BROWSERBASE_PROJECT_ID")
    if not key or not project:
        raise RuntimeError("browserbase_not_configured")
    client = Browserbase(api_key=key, timeout=10, max_retries=0)
    session = await asyncio.wait_for(asyncio.to_thread(client.sessions.create, project_id=project, keep_alive=False), timeout=12)
    try:
        return await _read_maps_session(session, query, limit)
    finally:
        try:
            await asyncio.wait_for(asyncio.to_thread(client.sessions.update, session.id,
                project_id=project, status="REQUEST_RELEASE", timeout=4), timeout=5)
        except Exception as exc:  # noqa: BLE001 — a cleanup failure must not erase completed research
            logger.warning("hunter.maps.session_release_failed", extra={"error_class": type(exc).__name__})
        client.close()


async def _read_maps_session(session: Any, query: str, limit: int) -> list[dict[str, Any]]:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(session.connect_url, timeout=10_000)
        try:
            context = browser.contexts[0]
            page = context.pages[0]
            await page.goto(f"https://www.google.com/maps/search/{quote(query, safe='')}?hl=pt-BR", wait_until="domcontentloaded", timeout=25_000)
            await page.wait_for_selector('a[href*="/maps/place/"], h1.DUwDvf, [role="feed"], [role="main"]', timeout=8_000)
            # Allow the business list, not just the Maps application shell, to load.
            try:
                await page.wait_for_selector('a[href*="/maps/place/"], h1.DUwDvf', timeout=6_000)
            except PlaywrightTimeoutError:
                if await page.locator('[role="feed"]').count() == 0:
                    raise RuntimeError("maps_results_unavailable")
            items = await page.locator('a[href*="/maps/place/"]').evaluate_all(
                "els => [...new Map(els.map(e => [e.href, {title: e.getAttribute('aria-label') || e.textContent.trim(), url: e.href}])).values()]"
            )
            if not items and await page.locator('h1.DUwDvf').count():
                items = [{"title": await page.locator('h1.DUwDvf').first.inner_text(), "url": page.url}]
            items = [item for item in items if safe_public_url(item.get("url"))][:min(limit, 30)]
            slots = asyncio.Semaphore(3)

            async def inspect(item: dict[str, Any]) -> dict[str, Any]:
                async with slots:
                    detail_page = await context.new_page()
                    try:
                        await detail_page.goto(item["url"], wait_until="domcontentloaded", timeout=10_000)
                        await detail_page.wait_for_function("""() => {
                            const heading = document.querySelector('h1.DUwDvf') || document.querySelector('[role="main"] h1');
                            const panel = heading?.closest('[role="main"]');
                            return panel && panel.querySelector('[data-item-id="address"], [data-item-id^="phone:"], a[data-item-id="authority"]')
                                && !panel.querySelector('[role="progressbar"]');
                        }""", timeout=5_000)
                        detail = await detail_page.evaluate(MAPS_DETAIL_SCRIPT)
                        return maps_detail_result(item, detail)
                    except (PlaywrightError, TimeoutError, ValueError, TypeError):
                        return maps_detail_result(item, {})
                    finally:
                        await detail_page.close()

            tasks = [asyncio.create_task(inspect(item)) for item in items]
            if not tasks:
                return []
            done, pending = await asyncio.wait(tasks, timeout=50)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            return [task.result() if task in done and not task.cancelled() and task.exception() is None
                    else maps_detail_result(item, {}) for item, task in zip(items, tasks)]
        finally:
            try:
                await asyncio.wait_for(browser.close(), timeout=5)
            except (PlaywrightError, TimeoutError, RuntimeError):
                logger.warning("hunter.maps.browser_cleanup_failed")


MAPS_DETAIL_SCRIPT = """() => {
    const heading = document.querySelector('h1.DUwDvf') || document.querySelector('[role="main"] h1');
    const panel = heading?.closest('[role="main"]');
    if (!panel) return {};
    const website = panel.querySelector('a[data-item-id="authority"]');
    const websiteButton = panel.querySelector('[data-item-id="authority"], [aria-label^="Website:"], [aria-label^="Site:"]');
    const phone = panel.querySelector('[data-item-id^="phone:"], a[href^="tel:"]');
    const address = panel.querySelector('[data-item-id="address"]');
    return {
        title: heading.textContent.trim(),
        loaded: !!(address || phone || website),
        website: website?.href || null,
        website_button: !!websiteButton,
        phone: phone?.getAttribute('href') || phone?.getAttribute('aria-label') || phone?.textContent || null,
        address: (address?.getAttribute('aria-label') || address?.textContent || '').replace(/^(?:Address|Endereço):\\s*/i, ''),
        category: panel.querySelector('button[jsaction*="category"]')?.textContent || '',
        links: [...panel.querySelectorAll('a[href]')].map(a => a.href),
    };
}"""


def research_query(search: dict[str, Any]) -> str:
    options = research_options(search)
    base = " ".join(filter(None, [options["provider_query"], search.get("location")]))
    objective = options["remaining_objective"]
    if objective:
        return f"{base}. Critério de interesse: {objective}"
    return base


async def execute_research(search: dict[str, Any]) -> dict[str, Any]:
    """Bound provider work, retain partial successes, then apply hard filters."""
    options = research_options(search)
    query = research_query(search)
    strict = options["website_filter"] != "any" or options["contact_filter"] != "any"
    # Filter after recall: never spend the user's result allowance on rejects.
    per_source = min(30, search["result_limit"] * 2) if strict else max(1, (search["result_limit"] + len(search["sources"]) - 1) // len(search["sources"]))
    tasks = {source: asyncio.create_task(maps_search(query, per_source) if source == "google_maps"
                                        else exa_search(query, source, per_source)) for source in search["sources"]}
    _, pending = await asyncio.wait(tasks.values(), timeout=SOURCE_TIMEOUT_SECONDS)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    failures: list[str] = []
    allowed_errors = {"exa_not_configured", "browserbase_not_configured", "browser_provider_unavailable"}
    for source, task in tasks.items():
        if task.cancelled() or task.exception() is not None:
            code = str(task.exception()) if not task.cancelled() else "provider_timeout"
            failures.append(code if code in allowed_errors else "provider_error")
            warnings.append(f"{SOURCE_LABELS[source]} não concluiu a consulta. Os resultados das outras fontes foram preservados.")
        else:
            batch = task.result()
            if isinstance(batch, list) and all(isinstance(item, dict) for item in batch):
                candidates.extend(batch)
            else:
                failures.append("provider_error")
                warnings.append(f"{SOURCE_LABELS[source]} retornou dados inválidos. Os resultados das outras fontes foram preservados.")
    # A known external website can never pass without_website. Avoid paying
    # to crawl pages which this explicit constraint will discard anyway.
    if options["website_filter"] != "without_website":
        try:
            await asyncio.wait_for(enrich_results(candidates), timeout=ENRICHMENT_TIMEOUT_SECONDS)
        except TimeoutError:
            warnings.append("O enriquecimento atingiu o limite de tempo; somente os contatos já encontrados foram mantidos.")
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError):
            warnings.append("O enriquecimento não foi concluído; os resultados originais foram preservados.")
    results, validation = filter_results(candidates, search)
    validation["source_failures"] = len(failures)
    results = results[:search["result_limit"]]
    validation["accepted"] = len(results)
    if options["website_filter"] == "without_website":
        warnings.append("Sem site significa que o campo Site não foi informado no perfil do Google Maps inspecionado; não prova que um site não existe.")
        if "google_maps" not in search["sources"]:
            warnings.append("Selecione Google Maps para verificar o filtro sem site. Outras fontes sem evidência foram excluídas.")
    if options["contact_filter"] == "whatsapp":
        warnings.append("WhatsApp exige um link público explícito. Um número de celular isolado não confirma WhatsApp.")
    if validation["unknown"]:
        warnings.append(f"{validation['unknown']} candidato(s) excluído(s) por falta de evidência para os filtros solicitados.")
    if options["unsupported_criterion"]:
        warnings.append("O critério livre foi enviado à busca, mas não pôde ser comprovado automaticamente. Esses resultados não foram importados para o CRM.")
    if any(item.get("public_data", {}).get("enrichment") == "unavailable" for item in candidates):
        warnings.append("Algumas páginas não permitiram enriquecimento; dados indisponíveis não foram inventados.")
    error = (failures[0] if len(set(failures)) == 1 else "provider_error") if len(failures) == len(tasks) else None
    return {"results": results, "validation": validation, "warnings": warnings, "error": error}


def create_hunter_router(repository: HunterRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/hunter", tags=["hunter"])

    @router.post("/searches", status_code=201)
    async def create_search(payload: SearchCreate, context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        return await repository.create(context, payload)

    @router.get("/searches")
    async def list_searches(context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        return {"items": await repository.list(context)}

    @router.post("/searches/{search_id}/confirm")
    async def confirm_search(search_id: str, request: Request,
                             idempotency_key: str = Header(min_length=8, max_length=200),
                             context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        del request, idempotency_key
        search = await repository.claim_confirmation(context, search_id)
        try:
            outcome = await execute_research(search)
        except Exception as exc:  # noqa: BLE001 — persist a terminal state at the external-provider boundary
            logger.warning("hunter.research.unexpected_error", extra={"error_class": type(exc).__name__})
            outcome = {"results": [], "error": "provider_error", "validation": {},
                       "warnings": ["A pesquisa não pôde ser concluída. Tente novamente; nenhum contato foi inventado."]}
        return await repository.finish(context, search_id, outcome["results"], outcome["error"],
                                       validation=outcome["validation"], warnings=outcome["warnings"])

    return router
