from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import logging
import os
import re
import socket
import psycopg
import threading
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.request import Request as UrlRequest
from urllib.error import HTTPError
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, field_validator

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
from .hunter_crm import sync_hunter_results
from .hunter_intelligence import expand_provider_query, understand_search
from .hunter_research import (
    clean_summary,
    extract_contacts,
    filter_results,
    folded,
    maps_detail_result,
    normalize_result,
    research_options,
    safe_public_url,
    website_opportunity,
)
from .scraping_adapters import analyze_with_scrapegraph, fetch_public_with_scrapling, parse_with_scrapling

ALLOWED_SOURCES = {"web", "google_maps", "instagram", "facebook"}
DOMAIN_BY_SOURCE = {"instagram": "instagram.com", "facebook": "facebook.com", "google_maps": "google.com"}
SOURCE_TIMEOUT_SECONDS = 130
SOURCE_RETRY_TIMEOUT_SECONDS = 90
ENRICHMENT_TIMEOUT_SECONDS = 25
HUNTER_MAX_RESULTS = 100
SOURCE_LABELS = {"web": "Web pública", "google_maps": "Google Maps", "instagram": "Instagram", "facebook": "Facebook"}
logger = logging.getLogger(__name__)
_PROVIDER_HTTP_SLOTS = threading.BoundedSemaphore(2)
_BROWSERBASE_CIRCUIT_LOCK = threading.Lock()
_BROWSERBASE_DISABLED_UNTIL = 0.0


def _browserbase_circuit_open() -> bool:
    with _BROWSERBASE_CIRCUIT_LOCK:
        return time.monotonic() < _BROWSERBASE_DISABLED_UNTIL


def _trip_browserbase_circuit(error: Exception) -> None:
    """Back off configuration/billing failures that cannot recover immediately."""
    if getattr(error, "status_code", None) not in {401, 402, 403}:
        return
    global _BROWSERBASE_DISABLED_UNTIL
    with _BROWSERBASE_CIRCUIT_LOCK:
        _BROWSERBASE_DISABLED_UNTIL = max(_BROWSERBASE_DISABLED_UNTIL, time.monotonic() + 900)


class SearchCreate(BaseModel):
    market: str
    query: str = Field(min_length=2, max_length=300)
    location: str | None = Field(default=None, max_length=160)
    sources: list[str] = Field(min_length=1, max_length=4)
    result_limit: int = Field(default=10, ge=1, le=HUNTER_MAX_RESULTS)
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


class InstagramImport(BaseModel):
    market: Literal["b2c", "b2b"] = "b2c"
    profiles: str = Field(min_length=2, max_length=8000)


class FacebookImport(BaseModel):
    market: Literal["b2c", "b2b"] = "b2c"
    profiles: str = Field(min_length=2, max_length=8000)


_INSTAGRAM_HANDLE = re.compile(r"[A-Za-z0-9_.]{1,30}\Z")
_INSTAGRAM_RESERVED = {"p", "reel", "reels", "explore", "stories", "accounts", "direct", "about"}

_FACEBOOK_HANDLE = re.compile(r"[A-Za-z0-9_.-]{1,60}\Z")
_FACEBOOK_RESERVED = {
    "p", "posts", "photos", "videos", "watch", "groups", "events", "share",
    "sharer", "story.php", "permalink.php", "login", "pages", "help",
    "marketplace", "about", "policies", "recover", "settings", "profile.php",
}


def parse_instagram_import(value: str) -> list[dict[str, Any]]:
    """Parse user-selected public profile identities, never posts or session data."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(value.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        identity, _, notes = line.partition("|")
        identity = identity.strip()
        notes = notes.strip()
        if identity.startswith("@"):
            handle = identity[1:]
        elif identity.lower().startswith(("https://", "http://")):
            parts = urlsplit(identity)
            host = (parts.hostname or "").lower().removeprefix("www.")
            path = parts.path.strip("/")
            if parts.scheme != "https" or host != "instagram.com" or "/" in path or parts.username or parts.password:
                raise ApiError(422, "invalid_instagram_profile", f"Linha {line_number}: use um @ ou URL de perfil do Instagram.")
            handle = path
        else:
            handle = identity
        if not _INSTAGRAM_HANDLE.fullmatch(handle) or handle.lower() in _INSTAGRAM_RESERVED:
            raise ApiError(422, "invalid_instagram_profile", f"Linha {line_number}: @ inválido ou link que não é perfil.")
        if len(notes) > 300:
            raise ApiError(422, "instagram_note_too_long", f"Linha {line_number}: observação deve ter até 300 caracteres.")
        key = handle.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "source": "instagram", "title": f"@{handle}",
            "url": f"https://www.instagram.com/{handle}/", "summary": notes,
            "public_data": {"provider": "user_supplied", "manual_import": True,
                            "verification_version": 1, "criterion_status": "manual_review",
                            "profile_handle": handle, "user_notes": notes},
        })
        if len(results) > HUNTER_MAX_RESULTS:
            raise ApiError(422, "instagram_import_too_large", f"Importe até {HUNTER_MAX_RESULTS} perfis por vez.")
    if not results:
        raise ApiError(422, "instagram_import_empty", "Informe pelo menos um @ ou URL de perfil.")
    return results


def parse_facebook_import(value: str) -> list[dict[str, Any]]:
    """Parse user-selected public Facebook page or profile identities, never posts or session data."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(value.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        identity, _, notes = line.partition("|")
        identity = identity.strip()
        notes = notes.strip()
        if identity.startswith("@"):
            handle = identity[1:]
        elif identity.lower().startswith(("https://", "http://")):
            parts = urlsplit(identity)
            host = (parts.hostname or "").lower().removeprefix("www.")
            path = parts.path.strip("/")
            if parts.scheme != "https" or host not in {"facebook.com", "fb.com"} or "/" in path or parts.username or parts.password:
                raise ApiError(422, "invalid_facebook_profile", f"Linha {line_number}: use um @ ou URL de página/perfil do Facebook.")
            handle = path
        else:
            handle = identity
        if not _FACEBOOK_HANDLE.fullmatch(handle) or handle.lower() in _FACEBOOK_RESERVED:
            raise ApiError(422, "invalid_facebook_profile", f"Linha {line_number}: @ inválido ou link que não é página/perfil.")
        if len(notes) > 300:
            raise ApiError(422, "facebook_note_too_long", f"Linha {line_number}: observação deve ter até 300 caracteres.")
        key = handle.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "source": "facebook", "title": f"@{handle}",
            "url": f"https://www.facebook.com/{handle}/", "summary": notes,
            "public_data": {"provider": "user_supplied", "manual_import": True,
                            "verification_version": 1, "criterion_status": "manual_review",
                            "profile_handle": handle, "user_notes": notes},
        })
        if len(results) > HUNTER_MAX_RESULTS:
            raise ApiError(422, "facebook_import_too_large", f"Importe até {HUNTER_MAX_RESULTS} perfis por vez.")
    if not results:
        raise ApiError(422, "facebook_import_empty", "Informe pelo menos um @ ou URL de página/perfil.")
    return results


@dataclass(slots=True)
class HunterRepository:
    database: PostgresRepository

    async def create(self, context: RequestContext, payload: SearchCreate) -> dict[str, Any]:
        org, user = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        filters = research_options(payload.model_dump())
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))
            await connection.execute("SELECT kiara.ensure_current_user('clerk', %s)", (context.user_id,))
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

    async def clear(self, context: RequestContext) -> int:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Seu perfil não pode limpar pesquisas.")
        org, user = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))
            await connection.execute("SELECT kiara.ensure_current_user('clerk', %s)", (context.user_id,))
            running = await (await connection.execute(
                "SELECT count(*) count FROM hunter_searches WHERE organization_id=%s AND status='running'", (org,)
            )).fetchone()
            if running and running["count"]:
                raise ApiError(409, "hunter_search_running", "Aguarde a pesquisa em execução terminar antes de limpar o histórico.")
            deleted = await (await connection.execute(
                "DELETE FROM hunter_searches WHERE organization_id=%s RETURNING id", (org,)
            )).fetchall()
            await connection.execute(
                "INSERT INTO audit_events (organization_id,actor_user_id,action,resource_type,correlation_id,metadata) VALUES (%s,%s,'hunter.searches.cleared','hunter_search',%s,%s)",
                (org, user, context.correlation_id, json.dumps({"deleted_searches": len(deleted), "pipeline_preserved": True})),
            )
        return len(deleted)

    async def claim_confirmation(self, context: RequestContext, search_id: str) -> dict[str, Any]:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Seu perfil não pode confirmar pesquisas.")
        org, sid, user = (_uuid("organization", context.organization_id),
                          _uuid("hunter_search", search_id), _uuid("user", context.user_id))
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user),))
            await connection.execute("SELECT kiara.ensure_current_user('clerk', %s)", (context.user_id,))
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
            await connection.execute(
                """INSERT INTO jobs
                   (organization_id,kind,state,payload,idempotency_key,max_attempts)
                   VALUES (%s,'hunter.search','queued',%s,%s,12)
                   ON CONFLICT (organization_id,idempotency_key) DO NOTHING""",
                (org, json.dumps({"search_id": str(sid), "requested_by": context.user_id,
                                  "membership_id": context.membership_id,
                                  "role": context.role, "correlation_id": context.correlation_id}),
                 f"hunter.search:{sid}"),
            )
            await connection.execute(
                """INSERT INTO hunter_work_queue (organization_id,search_id)
                   VALUES (%s,%s) ON CONFLICT (organization_id,search_id)
                   DO UPDATE SET available_at=LEAST(hunter_work_queue.available_at,now()),
                     lease_owner=NULL,lease_expires_at=NULL,updated_at=now()""",
                (org, sid),
            )
        return self._search(row, [])

    async def get(self, context: RequestContext, search_id: str) -> dict[str, Any]:
        org, sid = _uuid("organization", context.organization_id), _uuid("hunter_search", search_id)
        async with self.database._transaction(context.organization_id) as connection:
            row = await (await connection.execute(
                "SELECT * FROM hunter_searches WHERE organization_id=%s AND id=%s", (org, sid)
            )).fetchone()
            if not row:
                raise ApiError(404, "hunter_search_not_found", "Pesquisa não encontrada.")
            await self._attach_options(connection, org, row)
            results = await (await connection.execute(
                "SELECT * FROM hunter_results WHERE organization_id=%s AND search_id=%s ORDER BY created_at,id",
                (org, sid),
            )).fetchall()
        return self._search(row, [self._result(item) for item in results])

    async def claim_work(self, context: RequestContext, search_id: str) -> dict[str, Any] | None:
        """Lease one tenant-scoped Hunter job; expired workers can be recovered safely."""
        org, sid = _uuid("organization", context.organization_id), _uuid("hunter_search", search_id)
        owner = f"{context.correlation_id}:{context.user_id}"[:200]
        async with self.database._transaction(context.organization_id) as connection:
            row = await (await connection.execute(
                """UPDATE jobs SET state='running',attempts=attempts+1,lease_owner=%s,
                          lease_expires_at=now() + interval '4 minutes',updated_at=now()
                   WHERE organization_id=%s AND kind='hunter.search'
                     AND payload->>'search_id'=%s AND attempts < max_attempts
                     AND ((state='queued' AND available_at<=now()) OR
                          (state='running' AND lease_expires_at<now()))
                   RETURNING id,attempts,max_attempts,payload""",
                (owner, org, str(sid)),
            )).fetchone()
        return row

    async def retry_work(self, context: RequestContext, search_id: str, error_code: str,
                         attempts: int, max_attempts: int) -> bool:
        org, sid = _uuid("organization", context.organization_id), _uuid("hunter_search", search_id)
        exhausted = attempts >= max_attempts
        delay = min(900, 15 * (2 ** max(0, attempts - 1)))
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute(
                """UPDATE jobs SET state=%s,available_at=now()+(%s * interval '1 second'),
                          lease_owner=NULL,lease_expires_at=NULL,last_error_code=%s,updated_at=now()
                   WHERE organization_id=%s AND kind='hunter.search' AND payload->>'search_id'=%s""",
                ("failed" if exhausted else "queued", delay, error_code, org, str(sid)),
            )
            if exhausted:
                await connection.execute(
                    "DELETE FROM hunter_work_queue WHERE organization_id=%s AND search_id=%s", (org, sid),
                )
            else:
                await connection.execute(
                    """UPDATE hunter_work_queue SET available_at=now()+(%s * interval '1 second'),
                         lease_owner=NULL,lease_expires_at=NULL,updated_at=now()
                       WHERE organization_id=%s AND search_id=%s""",
                    (delay, org, sid),
                )
        return exhausted

    async def complete_work(self, context: RequestContext, search_id: str) -> None:
        org, sid = _uuid("organization", context.organization_id), _uuid("hunter_search", search_id)
        async with self.database._transaction(context.organization_id) as connection:
            await connection.execute(
                """UPDATE jobs SET state='succeeded',lease_owner=NULL,lease_expires_at=NULL,
                          last_error_code=NULL,updated_at=now()
                   WHERE organization_id=%s AND kind='hunter.search' AND payload->>'search_id'=%s""",
                (org, str(sid)),
            )
            await connection.execute(
                "DELETE FROM hunter_work_queue WHERE organization_id=%s AND search_id=%s", (org, sid),
            )

    async def claim_next_global(self, worker_id: str) -> tuple[RequestContext, str] | None:
        """Claim identifiers globally, then recover the payload inside its tenant RLS context."""
        async with await self.database._connect(row_factory=dict_row) as connection, connection.transaction():
            row = await (await connection.execute(
                """WITH candidate AS (
                     SELECT organization_id,search_id FROM hunter_work_queue
                     WHERE available_at<=now() AND (lease_owner IS NULL OR lease_expires_at<now())
                     ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1
                   )
                   UPDATE hunter_work_queue queue SET lease_owner=%s,
                     lease_expires_at=now()+interval '4 minutes',updated_at=now()
                   FROM candidate WHERE queue.organization_id=candidate.organization_id
                     AND queue.search_id=candidate.search_id
                   RETURNING queue.organization_id,queue.search_id""",
                (worker_id[:200],),
            )).fetchone()
        if not row:
            return None
        organization_id, search_id = str(row["organization_id"]), str(row["search_id"])
        async with self.database._transaction(organization_id) as connection:
            job = await (await connection.execute(
                """SELECT payload FROM jobs WHERE organization_id=%s AND kind='hunter.search'
                   AND payload->>'search_id'=%s""",
                (_uuid("organization", organization_id), search_id),
            )).fetchone()
        if not job:
            return None
        payload = job["payload"]
        return RequestContext(
            user_id=str(payload["requested_by"]), organization_id=organization_id,
            membership_id=str(payload["membership_id"]), role=str(payload["role"]),
            correlation_id=str(payload.get("correlation_id") or worker_id),
        ), search_id

    async def finish(self, context: RequestContext, search_id: str, results: list[dict[str, Any]], error: str | None = None,
                     *, validation: dict[str, int] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
        org, sid = _uuid("organization", context.organization_id), _uuid("hunter_search", search_id)
        async with self.database._transaction(context.organization_id) as connection:
            outcome_warnings = list(warnings or [])
            rejected_results = 0
            for result in results:
                try:
                    async with connection.transaction():
                        await connection.execute(
                            """INSERT INTO hunter_results (organization_id,search_id,source,title,url,summary,public_data)
                               VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,search_id,url) DO NOTHING""",
                            (org, sid, result["source"], result["title"][:500], result["url"][:3000],
                             result.get("summary"), json.dumps(result.get("public_data", {}))),
                        )
                except (psycopg.errors.CheckViolation, psycopg.DataError) as exc:
                    rejected_results += 1
                    logger.exception(
                        "hunter.result_rejected request_id=%s search_id=%s source=%s error_class=%s constraint=%s",
                        context.correlation_id, search_id, result.get("source"), type(exc).__name__,
                        getattr(getattr(exc, "diag", None), "constraint_name", None),
                    )
            if rejected_results:
                outcome_warnings.append(
                    f"{rejected_results} resultado(s) incompatível(is) foram isolados sem interromper a pesquisa. "
                    "Os demais resultados foram preservados; contate o administrador com a referência da pesquisa."
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
                try:
                    async with connection.transaction():
                        summary = await sync_hunter_results(connection, org, self._search(row, []), saved)
                except (psycopg.Error, ValueError, RuntimeError, TypeError, KeyError) as exc:
                    logger.exception(
                        "hunter.crm_sync_failed request_id=%s search_id=%s error_class=%s",
                        context.correlation_id, search_id, type(exc).__name__,
                    )
                    outcome_warnings.append(
                        "A pesquisa foi concluída e os resultados foram preservados, mas a sincronização com Leads/Pipeline falhou. "
                        "Atualize a página; se os contatos não aparecerem em Leads, contate o administrador com a referência da pesquisa."
                    )
            outcome = {"validation": validation or {}, "warnings": outcome_warnings, "sync_summary": summary}
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
    last_error: Exception | None = None
    for attempt in range(3):
        request = UrlRequest(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with _PROVIDER_HTTP_SLOTS, build_opener().open(request, timeout=45) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 425, 429, 500, 502, 503, 504} or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            delay = min(5.0, float(retry_after)) if retry_after.isdigit() else float(2 ** attempt)
            logger.warning("hunter.provider.retry", extra={"status_code": exc.code, "attempt": attempt + 1})
            time.sleep(delay)
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                raise
            logger.warning("hunter.provider.retry", extra={"error_class": type(exc).__name__, "attempt": attempt + 1})
            time.sleep(float(2 ** attempt))
    raise RuntimeError("provider_retry_exhausted") from last_error


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


async def firecrawl_search(query: str, source: str, limit: int) -> list[dict[str, Any]]:
    """Discover public pages through the already configured Firecrawl search API."""
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not key:
        raise RuntimeError("firecrawl_not_configured")
    domain = DOMAIN_BY_SOURCE.get(source)
    scoped_query = f"site:{domain}/maps {query}" if source == "google_maps" else query
    body: dict[str, Any] = {
        "query": scoped_query,
        "limit": min(limit, HUNTER_MAX_RESULTS),
        "sources": ["web"],
        "country": "BR",
        "timeout": 30_000,
        "ignoreInvalidURLs": True,
    }
    if domain and source != "google_maps":
        body["includeDomains"] = [domain]
    response = await asyncio.to_thread(
        _post_json,
        "https://api.firecrawl.dev/v2/search",
        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        body,
    )
    rows = (response.get("data") or {}).get("web") or []
    return [{
        "source": source,
        "title": item.get("title") or (item.get("metadata") or {}).get("title") or "Resultado público",
        "url": item.get("url") or (item.get("metadata") or {}).get("sourceURL") or "",
        "summary": item.get("description") or item.get("markdown") or "",
        "public_data": {"provider": "firecrawl_search"},
    } for item in rows if item.get("url") or (item.get("metadata") or {}).get("sourceURL")]


class _PublicIndexParser(HTMLParser):
    def __init__(self, source: str, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.source, self.limit = source, limit
        self.rows: list[dict[str, Any]] = []
        self._href = ""
        self._title: list[str] = []
        self._in_result = False
        self._result_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        fields = dict(attrs)
        classes = (fields.get("class") or "").split()
        if tag == "a" and "result__a" in classes and len(self.rows) < self.limit or tag == "a" and (fields.get("href") or "").startswith(("https://", "http://")) and len(self.rows) < self.limit:
            self._href = fields.get("href") or ""
            self._title = []
            self._in_result = True
            self._result_tag = "a"
        elif tag == "a" and (fields.get("href") or "").startswith("/url?"):
            self._href = (fields.get("href") or "")[4:]
        elif tag == "h3" and self._href and len(self.rows) < self.limit:
            self._title = []
            self._in_result = True
            self._result_tag = "h3"

    def handle_data(self, data: str) -> None:
        if self._in_result:
            self._title.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._result_tag or not self._in_result:
            return
        self._in_result = False
        href = "https:" + self._href if self._href.startswith("//") else self._href
        parts = urlsplit(href)
        if (parts.hostname or "").endswith("duckduckgo.com"):
            href = unquote((parse_qs(parts.query).get("uddg") or [""])[0])
        elif not parts.scheme:
            href = unquote((parse_qs(href).get("q") or [""])[0])
        safe = safe_public_url(href)
        title = clean_summary(" ".join(self._title), 500)
        host = (urlsplit(safe).hostname or "").lower().removeprefix("www.") if safe else ""
        required_domain = DOMAIN_BY_SOURCE.get(self.source)
        source_matches = not required_domain or host == required_domain or host.endswith("." + required_domain)
        if self.source == "google_maps":
            source_matches = bool(safe) and source_matches and "/maps" in urlsplit(safe).path
        if safe and title and source_matches and all(row["url"] != safe for row in self.rows):
            self.rows.append({
                "source": self.source,
                "title": title,
                "url": safe,
                "summary": "",
                "public_data": {"provider": "public_web_index"},
            })


def _read_public_index_endpoint(endpoint: str, source: str, limit: int) -> list[dict[str, Any]]:
    request = UrlRequest(endpoint, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    })
    with build_opener().open(request, timeout=20) as response:
        if response.headers.get_content_type() != "text/html":
            raise RuntimeError("public_index_invalid_response")
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise RuntimeError("public_index_response_too_large")
    parser = _PublicIndexParser(source, min(limit, HUNTER_MAX_RESULTS))
    parser.feed(body.decode("utf-8", errors="replace"))
    return parser.rows


def _read_public_index(query: str, source: str, limit: int) -> list[dict[str, Any]]:
    scoped = query
    domain = DOMAIN_BY_SOURCE.get(source)
    if domain and f"site:{domain}" not in scoped:
        scoped = f"site:{domain} {scoped}"
    endpoints = [
        "https://search.brave.com/search?" + urlencode({"q": scoped, "source": "web"}),
        "https://html.duckduckgo.com/html/?" + urlencode({"q": scoped}),
    ]
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            rows = _read_public_index_endpoint(endpoint, source, limit)
            if rows:
                return rows
        except (OSError, RuntimeError) as exc:
            last_error = exc
            logger.warning("hunter.public_index.endpoint_unavailable", extra={
                "host": urlsplit(endpoint).hostname, "error_class": type(exc).__name__,
            })
    if last_error:
        raise RuntimeError("public_index_unavailable") from last_error
    return []


async def indexed_search(query: str, source: str, limit: int) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_read_public_index, query, source, limit)


async def public_search(query: str, source: str, limit: int) -> list[dict[str, Any]]:
    if source == "instagram":
        query = f"site:instagram.com/ {query} Instagram perfil bio"
    elif source == "facebook":
        query = f"site:facebook.com/ {query} Facebook pagina perfil contato"
    try:
        rows = await exa_search(query, source, limit)
        if rows:
            return rows
    except Exception as exc:  # noqa: BLE001 — Firecrawl is an independent discovery fallback
        logger.warning("hunter.exa.unavailable", extra={"source": source, "error_class": type(exc).__name__})
    try:
        rows = await firecrawl_search(query, source, limit)
        if rows:
            return rows
    except Exception as fallback_exc:  # noqa: BLE001 - public index is credential-free
        logger.warning("hunter.firecrawl.unavailable", extra={
            "source": source, "error_class": type(fallback_exc).__name__,
        })
    try:
        return await indexed_search(query, source, limit)
    except Exception as index_exc:
        raise RuntimeError("public_index_unavailable") from index_exc


async def multi_public_search(queries: list[str], source: str, limit: int) -> list[dict[str, Any]]:
    """Search a few auditable variants and merge them without duplicate URLs."""
    unique_queries = list(dict.fromkeys(query.strip() for query in queries if query.strip()))[:3]
    batches = await asyncio.gather(
        *(public_search(query, source, limit) for query in unique_queries), return_exceptions=True,
    )
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[BaseException] = []
    for batch in batches:
        if isinstance(batch, BaseException):
            errors.append(batch)
            continue
        for row in batch:
            url = safe_public_url(row.get("url"))
            if url:
                parts = urlsplit(url)
                identity = f"{parts.scheme.lower()}://{(parts.hostname or '').lower()}{parts.path.rstrip('/').lower()}"
            else:
                identity = f"invalid:{row.get('url')}:{row.get('title')}"
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(row)
            if len(merged) >= limit:
                return merged
    if not merged and errors:
        raise RuntimeError(str(errors[0])) from errors[0]
    return merged


class _InstagramBioParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.bio = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        fields = dict(attrs)
        if fields.get("property") in {"og:description", "twitter:description"} or fields.get("name") == "description":
            self.bio = self.bio or (fields.get("content") or "")


def _read_public_instagram_bio(url: str) -> str:
    _assert_public_destination(url)
    request = UrlRequest(url, headers={"User-Agent": "KiaraResearchBot/1.0", "Accept": "text/html"})
    with build_opener(_SafeRedirectHandler()).open(request, timeout=8) as response:
        if response.headers.get_content_type() != "text/html":
            raise ValueError("unsupported_content")
        payload = response.read(500_001)
        if len(payload) > 500_000:
            raise ValueError("page_too_large")
    parser = _InstagramBioParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return clean_summary(parser.bio, 500)


async def inspect_instagram_bios(rows: list[dict[str, Any]]) -> None:
    """Verify public profile bios where Instagram serves them without login."""
    slots = asyncio.Semaphore(4)

    async def inspect(row: dict[str, Any]) -> None:
        url = safe_public_url(row.get("url"))
        parts = urlsplit(url) if url else None
        host = (parts.hostname or "").lower().removeprefix("www.") if parts else ""
        path = parts.path.strip("/") if parts else ""
        if host != "instagram.com" or not _INSTAGRAM_HANDLE.fullmatch(path) or path.lower() in _INSTAGRAM_RESERVED:
            return
        data = row.setdefault("public_data", {})
        data["profile_handle"] = path
        async with slots:
            try:
                bio = await asyncio.to_thread(_read_public_instagram_bio, url)
            except (OSError, ValueError, TypeError, UnicodeError):
                bio = ""
        data["bio_status"] = "verified_public_profile" if bio else "indexed_excerpt_only"
        if bio:
            data["profile_bio"] = bio
            row["summary"] = bio

    await asyncio.gather(*(inspect(row) for row in rows[:30]))


class _FacebookAboutParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.about = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        fields = dict(attrs)
        if fields.get("property") in {"og:description", "twitter:description"} or fields.get("name") == "description":
            self.about = self.about or (fields.get("content") or "")


def _read_public_facebook_about(url: str) -> str:
    _assert_public_destination(url)
    request = UrlRequest(url, headers={"User-Agent": "KiaraResearchBot/1.0", "Accept": "text/html"})
    with build_opener(_SafeRedirectHandler()).open(request, timeout=8) as response:
        if response.headers.get_content_type() != "text/html":
            raise ValueError("unsupported_content")
        payload = response.read(500_001)
        if len(payload) > 500_000:
            raise ValueError("page_too_large")
    parser = _FacebookAboutParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return clean_summary(parser.about, 500)


async def inspect_facebook_pages(rows: list[dict[str, Any]]) -> None:
    """Verify public page descriptions where Facebook serves them without login."""
    slots = asyncio.Semaphore(4)

    async def inspect(row: dict[str, Any]) -> None:
        url = safe_public_url(row.get("url"))
        parts = urlsplit(url) if url else None
        host = (parts.hostname or "").lower().removeprefix("www.") if parts else ""
        path = parts.path.strip("/") if parts else ""
        segments = path.split("/") if path else []
        if host not in {"facebook.com", "fb.com"}:
            return
        if not segments or (len(segments) == 1 and (not _FACEBOOK_HANDLE.fullmatch(segments[0]) or segments[0].lower() in _FACEBOOK_RESERVED)):
            return
        handle = segments[0] if len(segments) == 1 else (segments[1] if segments[0].lower() in {"people", "pages"} and len(segments) > 1 else segments[0])
        data = row.setdefault("public_data", {})
        data["profile_handle"] = handle
        async with slots:
            try:
                about = await asyncio.to_thread(_read_public_facebook_about, url)
            except (OSError, ValueError, TypeError, UnicodeError):
                about = ""
        data["page_status"] = "verified_public_page" if about else "indexed_excerpt_only"
        data["bio_status"] = "verified_public_profile" if about else "indexed_excerpt_only"
        if about:
            data["profile_bio"] = about
            row["summary"] = about

    await asyncio.gather(*(inspect(row) for row in rows[:30]))


async def enrich_results(results: list[dict[str, Any]]) -> None:
    """Enrich public websites with contacts and observable opportunity signals."""
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not key:
        await obscura_enrich_results(results)
        await native_enrich_results(results)
        await semantic_enrich_results(results)
        return
    candidates = []
    for item in results:
        data = item.setdefault("public_data", {})
        target = safe_public_url(data.get("website_url")) or (safe_public_url(item.get("url")) if item.get("source") == "web" else None)
        if target and len(candidates) < 20:
            data["enrichment_url"] = target
            candidates.append(item)

    async def enrich(item: dict[str, Any]) -> None:
        try:
            response = await asyncio.to_thread(
                _post_json, "https://api.firecrawl.dev/v2/scrape",
                {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                {"url": item["public_data"]["enrichment_url"], "formats": ["markdown", "links"], "onlyMainContent": True,
                 "timeout": 20000},
            )
            content = (response.get("data") or {}).get("markdown")
            if response.get("success") and isinstance(content, str) and content.strip():
                links = (response.get("data") or {}).get("links") or []
                contacts = extract_contacts(content[:40000], links)
                quality, signals = website_opportunity(item["public_data"]["enrichment_url"], content, links)
                item.setdefault("public_data", {}).update({
                    "enrichment": "completed", "provider": "firecrawl", **contacts,
                    "website_quality_score": quality, "website_quality_signals": signals,
                })
                item["summary"] = clean_summary(content)
            else:
                item.setdefault("public_data", {})["enrichment"] = "unavailable"
        except (OSError, ValueError, TypeError, AttributeError):
            item.setdefault("public_data", {})["enrichment"] = "unavailable"

    await asyncio.gather(*(enrich(item) for item in candidates))
    await native_enrich_results(results)
    await semantic_enrich_results(results)


class _PublicHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text: list[str] = []
        self.links: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(urljoin(self.base_url, href))

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored and data.strip():
            self.text.append(data.strip())


def _assert_public_destination(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("unsafe_url")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for item in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            raise ValueError("unsafe_destination")


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        _assert_public_destination(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_public_page(url: str) -> tuple[str, list[str], str]:
    _assert_public_destination(url)
    try:
        text, links, final_url = fetch_public_with_scrapling(url)
        _assert_public_destination(final_url)
        return text, links, "scrapling_http"
    except (ImportError, ModuleNotFoundError, OSError, ValueError, TypeError, AttributeError, UnicodeError) as exc:
        logger.info("hunter.scrapling.fetch_fallback", extra={
            "url_host": urlsplit(url).hostname, "error_class": type(exc).__name__,
        })
    request = UrlRequest(url, headers={
        "User-Agent": "KiaraResearchBot/1.0 (+public-contact-research)",
        "Accept": "text/html,application/xhtml+xml;q=0.9",
    })
    with build_opener(_SafeRedirectHandler()).open(request, timeout=12) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("unsupported_content")
        payload = response.read(2_000_001)
        if len(payload) > 2_000_000:
            raise ValueError("page_too_large")
        charset = response.headers.get_content_charset() or "utf-8"
        page_url = response.geturl()
    html = payload.decode(charset, errors="replace")
    try:
        text, links = parse_with_scrapling(html, page_url)
        return text, links, "kiara_native"
    except (ImportError, ValueError, TypeError):
        parser = _PublicHtmlParser(page_url)
        parser.feed(html)
        return " ".join(parser.text)[:40000], parser.links[:500], "python_html_parser"


async def native_enrich_results(results: list[dict[str, Any]]) -> None:
    """Zero-config, bounded HTML enrichment that runs inside the Kiara API."""
    candidates: list[dict[str, Any]] = []
    for item in results:
        data = item.setdefault("public_data", {})
        if data.get("enrichment") == "completed":
            continue
        target = safe_public_url(data.get("website_url")) or (safe_public_url(item.get("url")) if item.get("source") == "web" else None)
        host = (urlsplit(target).hostname or "").lower().removeprefix("www.") if target else ""
        is_meta = host in {"instagram.com", "facebook.com", "fb.com"} or host.endswith((".instagram.com", ".facebook.com"))
        if target and not is_meta and len(candidates) < 12:
            data["enrichment_url"] = target
            candidates.append(item)
    slots = asyncio.Semaphore(4)

    async def enrich(item: dict[str, Any]) -> None:
        async with slots:
            try:
                target = item["public_data"]["enrichment_url"]
                content, links, provider = await asyncio.to_thread(_fetch_public_page, target)
                if not content.strip():
                    return
                target_host = (urlsplit(target).hostname or "").lower().removeprefix("www.")
                relevant = re.compile(
                    r"/(?:contato|contact|fale-conosco|sobre|about|equipe|team|unidades?|locations?|servicos?|services?)(?:/|$)",
                    re.IGNORECASE,
                )
                internal_pages: list[str] = []
                for link in links:
                    safe = safe_public_url(link)
                    parts = urlsplit(safe) if safe else None
                    host = (parts.hostname or "").lower().removeprefix("www.") if parts else ""
                    if (safe and host == target_host and relevant.search(parts.path)
                            and safe.rstrip("/") != target.rstrip("/") and safe not in internal_pages):
                        internal_pages.append(safe)
                    if len(internal_pages) >= 3:
                        break
                page_count = 1
                combined_content = content[:40000]
                combined_links = list(links[:500])
                for page_url in internal_pages:
                    try:
                        child_content, child_links, _ = await asyncio.to_thread(_fetch_public_page, page_url)
                    except (OSError, ValueError, TypeError, AttributeError, UnicodeError):
                        continue
                    page_count += 1
                    combined_content = (combined_content + "\n" + child_content[:30000])[:100000]
                    combined_links.extend(child_links[:300])
                contacts = extract_contacts(combined_content, combined_links)
                quality, signals = website_opportunity(target, combined_content, combined_links)
                item["public_data"].update({
                    "enrichment": "completed", "provider": provider, **contacts,
                    "website_quality_score": quality, "website_quality_signals": signals,
                    "pages_inspected": page_count,
                })
                item["summary"] = clean_summary(combined_content)
            except (OSError, ValueError, TypeError, AttributeError, UnicodeError):
                item["public_data"].setdefault("enrichment", "unavailable")

    await asyncio.gather(*(enrich(item) for item in candidates))


async def semantic_enrich_results(results: list[dict[str, Any]]) -> None:
    """Add unverified business context through the open-source ScrapeGraphAI graph."""
    if not os.getenv("KIARA_SCRAPEGRAPH_MODEL", "").strip():
        return
    prompt = (
        "Resuma em JSON o ramo de atividade e serviços descritos nesta página pública. "
        "Não invente telefone, WhatsApp, e-mail, identidade, ausência de site ou filtros comerciais."
    )
    for item in results[:3]:
        data = item.get("public_data") or {}
        target = safe_public_url(data.get("enrichment_url"))
        if data.get("enrichment") != "completed" or not target:
            continue
        try:
            _assert_public_destination(target)
            hint = await asyncio.wait_for(
                asyncio.to_thread(analyze_with_scrapegraph, target, prompt), timeout=20,
            )
            item.setdefault("public_data", {})["semantic_hint"] = {
                "provider": "scrapegraphai", "verified": False, "data": hint,
            }
        except (ImportError, OSError, ValueError, TypeError, RuntimeError, TimeoutError):
            logger.warning("hunter.scrapegraph.unavailable", extra={"url_host": urlsplit(target).hostname})


def _obscura_connection() -> tuple[str, dict[str, str]] | None:
    """Return a server-side Obscura CDP connection without leaking its secret."""
    endpoint = os.getenv("OBSCURA_CDP_URL", "").strip()
    if not endpoint:
        return None
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"https", "wss", "http", "ws"} or not parsed.hostname or parsed.username or parsed.password:
        logger.warning("hunter.obscura.invalid_endpoint")
        return None
    headers: dict[str, str] = {}
    token = os.getenv("OBSCURA_AUTH_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return endpoint, headers


async def obscura_enrich_results(results: list[dict[str, Any]]) -> None:
    """Render dynamic public pages through Obscura and extract observable facts."""
    connection = _obscura_connection()
    if not connection:
        return
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    candidates: list[dict[str, Any]] = []
    for item in results:
        data = item.setdefault("public_data", {})
        target = safe_public_url(data.get("website_url")) or (safe_public_url(item.get("url")) if item.get("source") == "web" else None)
        if target and len(candidates) < 20:
            data["enrichment_url"] = target
            candidates.append(item)
    if not candidates:
        return

    endpoint, headers = connection
    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(endpoint, headers=headers, timeout=10_000)
        context = await browser.new_context()
        slots = asyncio.Semaphore(4)

        async def enrich(item: dict[str, Any]) -> None:
            async with slots:
                page = await context.new_page()
                try:
                    await page.goto(item["public_data"]["enrichment_url"], wait_until="domcontentloaded", timeout=15_000)
                    await page.wait_for_timeout(500)
                    snapshot = await page.evaluate("""() => ({
                        text: (document.body?.innerText || '').slice(0, 40000),
                        links: Array.from(document.querySelectorAll('a[href]'), a => a.href).slice(0, 500)
                    })""")
                    content = snapshot.get("text", "") if isinstance(snapshot, dict) else ""
                    links = snapshot.get("links", []) if isinstance(snapshot, dict) else []
                    if content.strip():
                        contacts = extract_contacts(content, links)
                        quality, signals = website_opportunity(item["public_data"]["enrichment_url"], content, links)
                        item["public_data"].update({
                            "enrichment": "completed", "provider": "obscura", **contacts,
                            "website_quality_score": quality, "website_quality_signals": signals,
                        })
                        item["summary"] = clean_summary(content)
                    else:
                        item["public_data"]["enrichment"] = "unavailable"
                except (PlaywrightError, TimeoutError, ValueError, TypeError, AttributeError):
                    item["public_data"]["enrichment"] = "unavailable"
                finally:
                    await page.close()

        try:
            await asyncio.gather(*(enrich(item) for item in candidates))
        finally:
            await context.close()
            await browser.close()


async def google_places_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Use Places Text Search when the server administrator configured it."""
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise RuntimeError("google_places_not_configured")
    field_mask = (
        "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
        "places.internationalPhoneNumber,places.websiteUri,places.googleMapsUri,places.primaryType,"
        "places.types,places.rating,places.userRatingCount,places.businessStatus,nextPageToken"
    )
    rows: list[dict[str, Any]] = []
    page_token: str | None = None
    while len(rows) < min(limit, HUNTER_MAX_RESULTS):
        body: dict[str, Any] = {
            "textQuery": query, "languageCode": "pt-BR", "regionCode": "BR",
            "pageSize": min(20, limit - len(rows)),
        }
        if page_token:
            body["pageToken"] = page_token
        response = await asyncio.to_thread(
            _post_json, "https://places.googleapis.com/v1/places:searchText",
            {"Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": field_mask}, body,
        )
        for place in response.get("places") or []:
            place_id = str(place.get("id") or "").strip()
            display = place.get("displayName") or {}
            title = display.get("text") if isinstance(display, dict) else display
            if not place_id or not title:
                continue
            maps_url = safe_public_url(place.get("googleMapsUri"))
            website = safe_public_url(place.get("websiteUri"))
            phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
            rating, reviews = place.get("rating"), place.get("userRatingCount")
            summary = [place.get("primaryType") or "Perfil empresarial no Google Maps"]
            if rating is not None:
                summary.append(f"Nota {rating}" + (f" ({reviews} avaliações)" if reviews is not None else ""))
            rows.append({
                "source": "google_maps", "title": str(title),
                "url": maps_url or f"https://www.google.com/maps/place/?q=place_id:{quote(place_id, safe='')}",
                "summary": " · ".join(summary),
                "public_data": {
                    "provider": "google_places", "place_id": place_id, "detail_inspected": True,
                    "address": place.get("formattedAddress"), "phone": phone, "website_url": website,
                    "website_status": "present" if website else "not_listed",
                    "business_status": place.get("businessStatus"), "rating": rating,
                    "user_rating_count": reviews, "types": place.get("types") or [],
                },
            })
            if len(rows) >= limit:
                break
        page_token = response.get("nextPageToken")
        if not page_token or len(rows) >= limit:
            break
    return rows[:limit]


async def maps_search(query: str, limit: int) -> list[dict[str, Any]]:
    async def supplement(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(rows) >= limit:
            return rows[:limit]
        try:
            indexed = await maps_index_search(query, limit)
        except Exception as exc:  # noqa: BLE001 — partial browser results remain useful
            logger.warning("hunter.maps.index_supplement_unavailable", extra={"error_class": type(exc).__name__})
            if rows:
                return rows[:limit]
            raise
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in [*rows, *indexed]:
            url = safe_public_url(row.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(row)
            if len(merged) >= limit:
                break
        return merged

    try:
        places = await google_places_search(query, limit)
        if places:
            return await supplement(places)
    except Exception as exc:  # noqa: BLE001 - browser/index providers remain independent fallbacks
        logger.info("hunter.google_places.unavailable", extra={"error_class": type(exc).__name__})

    obscura = _obscura_connection()
    key, project = os.getenv("BROWSERBASE_API_KEY"), os.getenv("BROWSERBASE_PROJECT_ID")
    if not obscura and (not key or not project):
        try:
            return await supplement(await _read_maps_local(query, limit))
        except Exception as exc:  # noqa: BLE001 — the public index remains the final fallback
            logger.warning("hunter.maps.local_browser_unavailable", extra={"error_class": type(exc).__name__})
        return await maps_index_search(query, limit)
    try:
        import playwright.async_api  # noqa: F401 — check optional dependency before creating a paid session
    except ImportError as exc:
        logger.warning("hunter.maps.playwright_unavailable", extra={"error_class": type(exc).__name__})
        return await maps_index_search(query, limit)
    if obscura:
        endpoint, headers = obscura
        try:
            rows = await _read_maps_cdp(endpoint, query, limit, headers=headers)
            if rows:
                return await supplement(rows)
        except Exception as exc:  # noqa: BLE001 — Browserbase remains the isolated fallback
            logger.warning("hunter.obscura.maps_failed", extra={"error_class": type(exc).__name__})
    if not key or not project:
        return await maps_index_search(query, limit)
    if _browserbase_circuit_open():
        logger.warning("hunter.maps.browserbase_circuit_open")
        return await maps_index_search(query, limit)
    try:
        from browserbase import Browserbase
    except ImportError as exc:
        raise RuntimeError("browser_provider_unavailable") from exc
    client = Browserbase(api_key=key, timeout=10, max_retries=0)
    try:
        session = await asyncio.wait_for(asyncio.to_thread(client.sessions.create, project_id=project, keep_alive=False), timeout=12)
    except Exception as exc:  # noqa: BLE001 — indexed public Maps pages remain available
        _trip_browserbase_circuit(exc)
        logger.warning("hunter.maps.browserbase_unavailable", extra={
            "error_class": type(exc).__name__, "provider_status": getattr(exc, "status_code", None),
        })
        client.close()
        return await maps_index_search(query, limit)
    try:
        return await supplement(await _read_maps_cdp(session.connect_url, query, limit))
    finally:
        try:
            await asyncio.wait_for(asyncio.to_thread(client.sessions.update, session.id,
                project_id=project, status="REQUEST_RELEASE", timeout=4), timeout=5)
        except Exception as exc:  # noqa: BLE001 — a cleanup failure must not erase completed research
            logger.warning("hunter.maps.session_release_failed", extra={"error_class": type(exc).__name__})
        client.close()


async def maps_index_search(query: str, limit: int) -> list[dict[str, Any]]:
    """Fallback for public Maps pages indexed on the web; no browser session required."""
    rows = await public_search(f"{query} Google Maps", "google_maps", limit)
    indexed: list[dict[str, Any]] = []
    for row in rows:
        url = safe_public_url(row.get("url"))
        parsed = urlsplit(url) if url else None
        host = (parsed.hostname or "").lower() if parsed else ""
        google_host = host in {"google.com", "google.com.br"} or host.endswith((".google.com", ".google.com.br"))
        if parsed and google_host and "/maps" in parsed.path:
            row.setdefault("public_data", {}).update({
                "detail_inspected": False,
                "website_status": "unknown",
                "provider": "maps_public_index",
            })
            indexed.append(row)
    return indexed


async def _read_maps_cdp(connect_url: str, query: str, limit: int, *, headers: dict[str, str] | None = None) -> list[dict[str, Any]]:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.connect_over_cdp(connect_url, headers=headers, timeout=10_000)
        try:
            context = browser.contexts[0]
            page = context.pages[0]
            return await _collect_maps_page(context, page, query, limit)
        finally:
            try:
                await asyncio.wait_for(browser.close(), timeout=5)
            except (PlaywrightError, TimeoutError, RuntimeError):
                logger.warning("hunter.maps.browser_cleanup_failed")


async def _read_maps_local(query: str, limit: int) -> list[dict[str, Any]]:
    """Use a locally installed Chromium without an API key or remote CDP service."""
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, timeout=10_000)
        try:
            context = await browser.new_context(locale="pt-BR")
            page = await context.new_page()
            return await _collect_maps_page(context, page, query, limit)
        finally:
            await browser.close()


async def _collect_maps_page(context: Any, page: Any, query: str, limit: int) -> list[dict[str, Any]]:
    from playwright.async_api import Error as PlaywrightError
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    try:
            await page.goto(f"https://www.google.com/maps/search/?api=1&query={quote(query, safe='')}&hl=pt-BR", wait_until="domcontentloaded", timeout=25_000)
            await _dismiss_google_consent(page)
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
            items = [item for item in items if safe_public_url(item.get("url"))][:min(limit, HUNTER_MAX_RESULTS)]
            feed = page.locator('[role="feed"]')
            attempts = 0
            while len(items) < min(limit, HUNTER_MAX_RESULTS) and await feed.count() and attempts < 20:
                attempts += 1
                await feed.evaluate("element => element.scrollBy(0, Math.max(element.clientHeight * 1.8, 900))")
                await page.wait_for_timeout(700)
                items = await page.locator('a[href*="/maps/place/"]').evaluate_all(
                    "els => [...new Map(els.map(e => [e.href, {title: e.getAttribute('aria-label') || e.textContent.trim(), url: e.href}])).values()]"
                )
                items = [item for item in items if safe_public_url(item.get("url"))][:min(limit, HUNTER_MAX_RESULTS)]
            slots = asyncio.Semaphore(6)

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
            await page.close()
        except PlaywrightError:
            logger.warning("hunter.maps.page_cleanup_failed")


async def _read_maps_session(session: Any, query: str, limit: int) -> list[dict[str, Any]]:
    """Compatibility wrapper for existing callers and contract tests."""
    return await _read_maps_cdp(session.connect_url, query, limit)


async def _dismiss_google_consent(page: Any) -> None:
    """Continue past Google's regional consent screen when it is presented.

    The action is scoped to the Browserbase research session. It stores no
    customer identity and does not weaken browser or application security.
    """
    if (urlsplit(getattr(page, "url", "")).hostname or "").lower() == "consent.google.com":
        buttons = page.get_by_role("button", name=re.compile(
            r"^(?:Aceitar tudo|Accept all|Concordo|I agree)$", re.IGNORECASE,
        ))
        if await buttons.count():
            await buttons.first.click(timeout=5_000)
            await page.wait_for_load_state("domcontentloaded", timeout=12_000)


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


def expanded_research_query(search: dict[str, Any]) -> str:
    """Expanded query for indexes; Maps receives the concise user wording."""
    options = research_options(search)
    base = expand_provider_query(options["provider_query"], search.get("location"))
    objective = options["remaining_objective"]
    return f"{base}. Critério de interesse: {objective}" if objective else base


def research_query_variants(search: dict[str, Any]) -> list[str]:
    """Cover semantic, concise, and contact-oriented provider phrasing."""
    options = research_options(search)
    primary = expanded_research_query(search)
    concise = " ".join(filter(None, [options["provider_query"], search.get("location")]))
    contact = f"{concise} contato telefone site"
    return list(dict.fromkeys(value.strip() for value in (primary, concise, contact) if value.strip()))


def _instagram_profile_matches(row: dict[str, Any], search: dict[str, Any]) -> bool:
    """Keep indexed Instagram candidates; record what the public evidence actually proves."""
    url = safe_public_url(row.get("url"))
    parts = urlsplit(url) if url else None
    if not parts or (parts.hostname or "").lower().removeprefix("www.") != "instagram.com":
        return False
    segments = parts.path.strip("/").split("/")
    publication = len(segments) == 2 and segments[0].lower() in {"p", "reel", "tv"}
    profile = len(segments) == 1 and _INSTAGRAM_HANDLE.fullmatch(segments[0]) and segments[0].lower() not in _INSTAGRAM_RESERVED
    if not profile and not publication:
        return False
    options = research_options(search)
    plan = understand_search(options["provider_query"], search.get("location"))
    semantic_terms = [plan.get("entity") or "", *plan.get("services", []), *plan.get("alternatives", [])]
    niche = [word.rstrip("s") for word in re.findall(r"[a-z]{4,}", folded(" ".join(semantic_terms) or options["provider_query"]))
             if word not in {"para", "com", "sem", "quero", "buscar", "encontrar"}]
    place = [word for word in re.findall(r"[a-z]{4,}", folded(search.get("location") or ""))]
    indexed = folded(" ".join(str(row.get(key) or "") for key in ("title", "summary")) + " " + (segments[0] if profile else ""))
    bio = folded(str(row.get("public_data", {}).get("profile_bio") or ""))
    data = row.setdefault("public_data", {})
    data["content_kind"] = "publication" if publication else "profile"
    data["niche_evidence"] = bool(niche and any(word in indexed or word in bio for word in niche))
    data["location_evidence"] = bool(place and all(word in indexed or word in bio for word in place))
    data["bio_niche_evidence"] = bool(niche and any(word in bio for word in niche))
    data["bio_location_evidence"] = bool(place and all(word in bio for word in place))
    return True


def _facebook_profile_matches(row: dict[str, Any], search: dict[str, Any]) -> bool:
    """Keep indexed Facebook candidates; record what the public evidence actually proves."""
    url = safe_public_url(row.get("url"))
    parts = urlsplit(url) if url else None
    if not parts or (parts.hostname or "").lower().removeprefix("www.") not in {"facebook.com", "fb.com"}:
        return False
    segments = parts.path.strip("/").split("/")
    if not segments or segments == [""]:
        return False
    first = segments[0].lower()
    publication = (
        first in {"posts", "photos", "videos", "watch", "events", "share", "sharer", "story.php", "permalink.php"}
        or (len(segments) >= 2 and segments[1].lower() in {"posts", "photos", "videos"})
    )
    profile = (
        (len(segments) == 1 and _FACEBOOK_HANDLE.fullmatch(segments[0]) and first not in _FACEBOOK_RESERVED)
        or (first in {"pages", "people"} and len(segments) >= 2)
        or (first == "profile.php" and bool(parse_qs(parts.query).get("id")))
    )
    if not profile and not publication:
        return False
    options = research_options(search)
    plan = understand_search(options["provider_query"], search.get("location"))
    semantic_terms = [plan.get("entity") or "", *plan.get("services", []), *plan.get("alternatives", [])]
    niche = [word.rstrip("s") for word in re.findall(r"[a-z]{4,}", folded(" ".join(semantic_terms) or options["provider_query"]))
             if word not in {"para", "com", "sem", "quero", "buscar", "encontrar"}]
    place = [word for word in re.findall(r"[a-z]{4,}", folded(search.get("location") or ""))]
    indexed = folded(" ".join(str(row.get(key) or "") for key in ("title", "summary")) + " " + (segments[0] if profile else ""))
    bio = folded(str(row.get("public_data", {}).get("profile_bio") or ""))
    data = row.setdefault("public_data", {})
    data["content_kind"] = "publication" if publication else "profile"
    data["niche_evidence"] = bool(niche and any(word in indexed or word in bio for word in niche))
    data["location_evidence"] = bool(place and all(word in indexed or word in bio for word in place))
    data["bio_niche_evidence"] = bool(niche and any(word in bio for word in niche))
    data["bio_location_evidence"] = bool(place and all(word in bio for word in place))
    return True


async def execute_research(search: dict[str, Any]) -> dict[str, Any]:
    """Bound provider work, retain partial successes, then apply hard filters."""
    options = research_options(search)
    query = research_query(search)
    expanded_queries = research_query_variants(search)
    logger.info("hunter.research.started", extra={
        "sources": search["sources"], "result_limit": search["result_limit"],
        "has_location": bool(search.get("location")), "research_mode": search.get("research_mode", "broad"),
    })
    strict = any(options[key] != "any" for key in ("website_filter", "contact_filter", "email_filter", "website_quality_filter"))
    # Filter after recall: never spend the user's result allowance on rejects.
    per_source = min(HUNTER_MAX_RESULTS, search["result_limit"] * 2) if strict else max(1, (search["result_limit"] + len(search["sources"]) - 1) // len(search["sources"]))
    def source_task(source: str) -> asyncio.Task[list[dict[str, Any]]]:
        operation = maps_search(query, per_source) if source == "google_maps" else multi_public_search(expanded_queries, source, per_source)
        return asyncio.create_task(operation)

    def valid_task(task: asyncio.Task[Any]) -> bool:
        if task.cancelled() or task.exception() is not None:
            return False
        value = task.result()
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)

    tasks = {source: source_task(source) for source in search["sources"]}
    _, pending = await asyncio.wait(tasks.values(), timeout=SOURCE_TIMEOUT_SECONDS)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    retry_sources = [source for source, task in tasks.items() if not valid_task(task)]
    if retry_sources:
        retries = {source: source_task(source) for source in retry_sources}
        retry_timeout = min(SOURCE_RETRY_TIMEOUT_SECONDS, SOURCE_TIMEOUT_SECONDS)
        _, retry_pending = await asyncio.wait(retries.values(), timeout=retry_timeout)
        for task in retry_pending:
            task.cancel()
        await asyncio.gather(*retry_pending, return_exceptions=True)
        for source, retry in retries.items():
            if valid_task(retry):
                tasks[source] = retry
                logger.info("hunter.research.source_recovered", extra={"source": source})
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    failures: list[str] = []
    allowed_errors = {"exa_not_configured", "firecrawl_not_configured", "public_index_unavailable", "browserbase_not_configured", "browser_provider_unavailable", "provider_timeout"}
    source_failure_messages = {
        "public_index_unavailable": "{source} não concluiu a consulta porque o índice público está temporariamente indisponível. Tente novamente em alguns minutos; se persistir, peça ao administrador para verificar EXA_API_KEY e FIRECRAWL_API_KEY.",
        "exa_not_configured": "{source} não concluiu a consulta porque não está configurada. Peça ao administrador para configurar EXA_API_KEY.",
        "firecrawl_not_configured": "{source} não concluiu a consulta porque não está configurada. Peça ao administrador para configurar FIRECRAWL_API_KEY.",
        "browserbase_not_configured": "Google Maps não está configurado. Peça ao administrador para configurar o navegador de pesquisa.",
        "browser_provider_unavailable": "Google Maps está temporariamente indisponível. Tente novamente; se persistir, peça ao administrador para revisar Browserbase ou Obscura.",
    }
    for source, task in tasks.items():
        if task.cancelled() or task.exception() is not None:
            code = str(task.exception()) if not task.cancelled() else "provider_timeout"
            failures.append(code if code in allowed_errors else "provider_error")
            warnings.append(source_failure_messages.get(
                code,
                "{source} não concluiu a consulta por uma falha inesperada. Tente novamente; se persistir, contate o administrador.",
            ).format(source=SOURCE_LABELS[source]) + " Os resultados das outras fontes foram preservados.")
        else:
            batch = task.result()
            if isinstance(batch, list) and all(isinstance(item, dict) for item in batch):
                candidates.extend(batch)
                logger.info("hunter.research.source_completed", extra={"source": source, "candidate_count": len(batch)})
            else:
                failures.append("provider_error")
                warnings.append(f"{SOURCE_LABELS[source]} retornou dados inválidos. Os resultados das outras fontes foram preservados.")
    instagram_rows = [row for row in candidates if row.get("source") == "instagram"]
    if instagram_rows:
        await inspect_instagram_bios(instagram_rows)
        candidates = [row for row in candidates if row.get("source") != "instagram" or _instagram_profile_matches(row, search)]
        if any(row.get("public_data", {}).get("bio_status") == "indexed_excerpt_only" for row in candidates):
            warnings.append("Alguns perfis do Instagram apareceram no índice público, mas a bio atual não pôde ser confirmada sem login; confira o perfil antes de abordar.")
    facebook_rows = [row for row in candidates if row.get("source") == "facebook"]
    if facebook_rows:
        await inspect_facebook_pages(facebook_rows)
        candidates = [row for row in candidates if row.get("source") != "facebook" or _facebook_profile_matches(row, search)]
        if any(row.get("public_data", {}).get("page_status") == "indexed_excerpt_only" for row in candidates):
            warnings.append("Algumas páginas do Facebook apareceram no índice público, mas as informações atuais não puderam ser confirmadas sem login; confira a página antes de abordar.")
    # A known external website can never pass without_website. Avoid paying
    # to crawl pages which this explicit constraint will discard anyway.
    if options["website_filter"] != "without_website" or options["email_filter"] != "any" or options["website_quality_filter"] != "any":
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
    if options["email_filter"] == "without_email":
        warnings.append("Sem e-mail significa que nenhum endereço foi encontrado nas fontes e páginas inspecionadas; não prova ausência em toda a internet.")
    if options["website_quality_filter"] == "opportunity":
        warnings.append("Oportunidade digital usa sinais técnicos verificáveis; a Kiara não classifica gosto visual como fato.")
    if validation["unknown"]:
        warnings.append(f"{validation['unknown']} candidato(s) excluído(s) por falta de evidência para os filtros solicitados.")
    if options["unsupported_criterion"]:
        warnings.append("O critério livre foi enviado à busca, mas não pôde ser comprovado automaticamente. Esses resultados não foram importados para o CRM.")
    if any(item.get("public_data", {}).get("enrichment") == "unavailable" for item in candidates):
        warnings.append("Algumas páginas não permitiram enriquecimento; dados indisponíveis não foram inventados.")
    if any(item.get("public_data", {}).get("provider") == "maps_public_index" for item in candidates):
        warnings.append("O navegador do Maps estava indisponível. A Kiara preservou perfis públicos indexados; telefone, site e filtros específicos exigem detalhes verificáveis.")
    error = (failures[0] if len(set(failures)) == 1 else "provider_error") if len(failures) == len(tasks) else None
    logger.info("hunter.research.finished", extra={
        "candidate_count": len(candidates), "accepted_count": len(results),
        "excluded_count": validation["excluded"], "source_failures": len(failures), "error_code": error,
    })
    return {"results": results, "validation": validation, "warnings": warnings, "error": error}


def create_hunter_router(repository: HunterRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/hunter", tags=["hunter"])

    async def run_leased_search(context: RequestContext, search_id: str) -> dict[str, Any]:
        leased = await repository.claim_work(context, search_id)
        if leased is None:
            return await repository.get(context, search_id)
        search = await repository.get(context, search_id)
        try:
            outcome = await execute_research(search)
        except Exception as exc:  # noqa: BLE001 — the durable boundary must requeue unknown transient failures
            logger.warning("hunter.research.unexpected_error", extra={"error_class": type(exc).__name__})
            outcome = {"results": [], "error": "transient_worker_error", "validation": {},
                       "warnings": ["A execução foi interrompida e continuará automaticamente; nenhum contato foi perdido."]}
        if outcome["error"]:
            exhausted = await repository.retry_work(
                context, search_id, outcome["error"], leased["attempts"], leased["max_attempts"],
            )
            if not exhausted:
                current = await repository.get(context, search_id)
                current["warnings"] = [*current.get("warnings", []), *outcome["warnings"],
                    "As fontes limitaram temporariamente a consulta. A pesquisa permanece na fila e será retomada."]
                return current
        completed = await repository.finish(context, search_id, outcome["results"], outcome["error"],
                                            validation=outcome["validation"], warnings=outcome["warnings"])
        if not outcome["error"]:
            await repository.complete_work(context, search_id)
        return completed

    @router.post("/instagram/import", status_code=201)
    async def import_instagram(payload: InstagramImport, context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Seu perfil não pode importar perfis.")
        results = parse_instagram_import(payload.profiles)
        search = await repository.create(context, SearchCreate(
            market=payload.market, query="Perfis do Instagram selecionados pelo usuário",
            sources=["instagram"], result_limit=len(results),
        ))
        await repository.claim_confirmation(context, search["id"])
        completed = await repository.finish(context, search["id"], results,
            validation={"checked": len(results), "accepted": len(results), "excluded": 0, "unknown": 0, "source_failures": 0},
            warnings=["Perfis e observações fornecidos pelo usuário. A Kiara não leu sua sessão do Instagram nem confirmou bio, telefone ou mensagens."],
        )
        await repository.complete_work(context, search["id"])
        return completed

    @router.post("/facebook/import", status_code=201)
    async def import_facebook(payload: FacebookImport, context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Seu perfil não pode importar páginas ou perfis.")
        results = parse_facebook_import(payload.profiles)
        search = await repository.create(context, SearchCreate(
            market=payload.market, query="Páginas do Facebook selecionadas pelo usuário",
            sources=["facebook"], result_limit=len(results),
        ))
        await repository.claim_confirmation(context, search["id"])
        completed = await repository.finish(context, search["id"], results,
            validation={"checked": len(results), "accepted": len(results), "excluded": 0, "unknown": 0, "source_failures": 0},
            warnings=["Páginas e observações fornecidas pelo usuário. A Kiara não leu sua sessão do Facebook nem confirmou dados, telefone ou mensagens."],
        )
        await repository.complete_work(context, search["id"])
        return completed

    @router.post("/searches", status_code=201)
    async def create_search(payload: SearchCreate, context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        return await repository.create(context, payload)

    @router.get("/searches")
    async def list_searches(context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        return {"items": await repository.list(context)}

    @router.get("/searches/{search_id}")
    async def get_search(search_id: str, context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008
        return await repository.get(context, search_id)

    @router.delete("/searches")
    async def clear_searches(context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        return {"deleted": await repository.clear(context), "pipeline_preserved": True}

    @router.post("/searches/{search_id}/confirm")
    async def confirm_search(search_id: str, request: Request,
                             idempotency_key: str = Header(min_length=8, max_length=200),
                             context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008 — FastAPI dependency marker
        del request, idempotency_key
        return await repository.claim_confirmation(context, search_id)

    @router.post("/searches/{search_id}/process")
    async def process_search(search_id: str, request: Request,
                             context: RequestContext = Depends(authenticated_context)) -> dict[str, Any]:  # noqa: B008
        del request
        return await run_leased_search(context, search_id)

    @router.get("/internal/drain")
    async def drain_queue(request: Request) -> dict[str, Any]:
        expected = os.getenv("KIARA_WORKER_TOKEN") or os.getenv("CRON_SECRET")
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            raise ApiError(401, "worker_unauthorized", "Worker não autorizado.")
        claimed = await repository.claim_next_global(request.state.correlation_id)
        if not claimed:
            return {"processed": False, "queue": "empty"}
        context, search_id = claimed
        result = await run_leased_search(context, search_id)
        return {"processed": True, "search_id": search_id, "status": result["status"]}

    return router
