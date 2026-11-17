"""Kiara keeps learning: lessons per workspace and general patterns without personal data.

Every few hours the Debian worker calls POST /v1/learning/internal/tick (worker token). For each workspace in
the registry (learning_workspaces) it reads, inside that workspace's own RLS transaction, how its lead searches
turned out: per niche and city, how many results came, how many became leads in the funnel and how many
advanced (contacted, qualified, opportunity, won). From that:

- the workspace gets up to 5 short lessons in kiara_memories (source 'learned'), e.g. which niches work best
  for it and which ones waste searches. They reach the chat with the other memories and show on "Minha empresa";
- the general table kiara_patterns gets only counts per niche and city and how many workspaces contributed.
  Patterns from at least MIN_WORKSPACES workspaces are shown to everyone (chat and the Obsidian vault).

GET /v1/learning/internal/vault returns the Obsidian notes (Markdown with [[links]]) the worker writes on Debian.
Chat history stays in each person's browser; what Kiara learns from chats comes from [[LEMBRAR]] (memory.py).
"""
from __future__ import annotations

import hmac
import os
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

MIN_WORKSPACES = 2          # a general pattern needs at least this many workspaces (no single client is exposed)
MAX_WORKSPACES = 300        # per tick
LESSONS = 5
ADVANCED = ("contacted", "qualified", "opportunity", "won")
_UUID = r"^[0-9a-fA-F-]{36}$"

SEARCH_STATS = f"""
SELECT s.query, coalesce(s.location, '') AS location, count(DISTINCT s.id) AS searches, count(r.id) AS results,
       count(r.id) FILTER (WHERE coalesce(r.public_data->>'whatsapp_url', '') <> '') AS with_whatsapp,
       count(r.id) FILTER (WHERE r.public_data->>'website_status' = 'not_listed') AS without_website,
       count(p.id) AS added,
       count(p.id) FILTER (WHERE p.stage IN ('contacted', 'qualified', 'opportunity', 'won')) AS advanced,
       count(p.id) FILTER (WHERE p.stage = 'won') AS won
FROM hunter_searches s
LEFT JOIN hunter_results r ON r.organization_id = s.organization_id AND r.search_id = s.id
LEFT JOIN pipeline_entries p ON p.organization_id = s.organization_id
     AND (r.public_data->>'pipeline_entry_id') ~ '{_UUID}'
     AND p.id = (r.public_data->>'pipeline_entry_id')::uuid
WHERE s.organization_id = %s AND s.status = 'completed' AND s.created_at > now() - interval '180 days'
GROUP BY s.query, coalesce(s.location, '')
"""


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def niche_of(query: str) -> str:
    """'Dentistas sem site em Porto Alegre' -> 'dentistas sem site' (the place lives in `city`)."""
    plain = _plain(query)
    head, separator, _place = plain.rpartition(" em ")
    return ((head if separator and head else plain)[:80].strip()) or "geral"


def city_of(location: str) -> str:
    first = re.split(r"[-,/]", location or "")[0]
    return _plain(first)[:80]


def lessons(rows: list[dict[str, Any]]) -> list[str]:
    """Up to LESSONS short facts for this workspace, best first, then what wastes searches."""
    good = sorted((row for row in rows if row["advanced"] > 0), key=lambda row: (row["advanced"], row["added"]), reverse=True)
    facts = []
    for row in good[:3]:
        where = f" em {row['location']}" if row["location"] else ""
        facts.append(f"Buscas por \"{row['query']}\"{where} trouxeram {row['added']} leads para o funil e {row['advanced']} "
                     f"avançaram ({row['won']} vendas): é um dos nichos que mais funcionam para este negócio.")
    weak = [row for row in rows if row["searches"] >= 2 and row["results"] >= 10 and row["added"] == 0]
    for row in sorted(weak, key=lambda row: row["results"], reverse=True)[:2]:
        where = f" em {row['location']}" if row["location"] else ""
        facts.append(f"Buscas por \"{row['query']}\"{where} trouxeram {row['results']} resultados, mas nenhum virou lead: "
                     "vale ajustar o nicho, a região ou os filtros.")
    total_results = sum(row["results"] for row in rows)
    if total_results >= 30 and len(facts) < LESSONS:
        rate = round(100 * sum(row["with_whatsapp"] for row in rows) / total_results)
        facts.append(f"Nas buscas deste negócio, {rate}% dos resultados têm WhatsApp público.")
    return [fact[:300] for fact in facts[:LESSONS]]


def aggregate(per_workspace: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """General patterns: counts per niche and city, plus how many workspaces contributed. No ids, no names."""
    totals: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"searches": 0, "results": 0, "with_whatsapp": 0, "without_website": 0,
                                                                          "added": 0, "advanced": 0, "won": 0, "workspaces": 0})
    for rows in per_workspace:
        seen = set()
        for row in rows:
            key = (niche_of(row["query"]), city_of(row["location"]))
            for field in ("searches", "results", "with_whatsapp", "without_website", "added", "advanced", "won"):
                totals[key][field] += int(row[field] or 0)
            seen.add(key)
        for key in seen:
            totals[key]["workspaces"] += 1
    return [{"niche": niche, "city": city, **values} for (niche, city), values in totals.items()]


def pattern_lines(patterns: list[dict[str, Any]], limit: int = 8) -> list[str]:
    shared = [item for item in patterns if item["workspaces"] >= MIN_WORKSPACES and item["results"] >= 10]
    ranked = sorted(shared, key=lambda item: (item["advanced"] / max(1, item["added"]), item["added"]), reverse=True)
    lines = []
    for item in ranked[:limit]:
        where = f" em {item['city'].title()}" if item["city"] else ""
        whatsapp = round(100 * item["with_whatsapp"] / max(1, item["results"]))
        lines.append(f"\"{item['niche']}\"{where}: {item['added']} leads no funil, {item['advanced']} avançaram, "
                     f"{whatsapp}% com WhatsApp público ({item['workspaces']} empresas)")
    return lines


def prompt_block(patterns: list[dict[str, Any]]) -> str:
    lines = pattern_lines(patterns)
    if not lines:
        return ""
    return ("\n\nPadrões gerais de prospecção que a Kiara aprendeu com várias empresas (só números, sem dados pessoais; use "
            "para sugerir nichos e regiões, sem citar outras empresas):\n" + "\n".join(f"- {line}" for line in lines) + "\n")


def vault_notes(patterns: list[dict[str, Any]], workspaces: int, now: datetime | None = None) -> dict[str, str]:
    """Obsidian notes (path -> Markdown). Only general patterns: no workspace data ever goes to the vault."""
    stamp = (now or datetime.now(UTC)).strftime("%d/%m/%Y %H:%M UTC")
    shared = [item for item in patterns if item["workspaces"] >= MIN_WORKSPACES]
    notes: dict[str, str] = {}
    by_niche: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in shared:
        by_niche[item["niche"]].append(item)
    for niche, items in by_niche.items():
        rows = "\n".join(f"| {item['city'].title() or '—'} | {item['searches']} | {item['results']} | {item['added']} | {item['advanced']} | {item['won']} | "
                         f"{round(100 * item['with_whatsapp'] / max(1, item['results']))}% | {item['workspaces']} |" for item in sorted(items, key=lambda i: -i["added"]))
        title = niche.title()
        notes[f"Kiara/Nichos/{title}.md"] = (
            f"---\ntags: [kiara, nicho]\natualizado: {stamp}\n---\n# {title}\n\nVoltar para [[Padrões gerais]].\n\n"
            "| Cidade | Buscas | Resultados | No funil | Avançaram | Vendas | Com WhatsApp | Empresas |\n|---|---|---|---|---|---|---|---|\n"
            f"{rows}\n")
    lines = pattern_lines(patterns, limit=20)
    index = "\n".join(f"- [[{item.title()}]]" for item in sorted(by_niche)) or "- Ainda não há nichos com dados de pelo menos duas empresas."
    notes["Kiara/Padrões gerais.md"] = (
        f"---\ntags: [kiara]\natualizado: {stamp}\n---\n# Padrões gerais\n\nO que a Kiara aprendeu com as buscas de {workspaces} empresas "
        f"(só números; um padrão aparece quando pelo menos {MIN_WORKSPACES} empresas buscaram o mesmo nicho).\n\n"
        "## O que mais funciona\n" + ("\n".join(f"- {line}" for line in lines) or "- Ainda aprendendo.") + "\n\n## Nichos\n" + index + "\n\n"
        "Veja também [[Como a Kiara aprende]].\n")
    notes["Kiara/Como a Kiara aprende.md"] = (
        "---\ntags: [kiara]\n---\n# Como a Kiara aprende\n\n"
        "- **Por empresa:** a cada poucas horas, a Kiara olha as buscas de leads de cada empresa (o que virou lead, o que avançou, "
        "o que não deu certo) e guarda até 5 lições na memória daquela empresa. Cada cliente vê as suas em *Minha empresa → O que a Kiara lembra*.\n"
        "- **No chat:** quando a pessoa conta algo que vale lembrar, a Kiara guarda na memória da empresa dela.\n"
        "- **Geral:** só números por nicho e cidade, sem nomes, telefones ou conversas. Um padrão só aparece quando vem de pelo menos "
        f"{MIN_WORKSPACES} empresas.\n- Este cofre é atualizado sozinho pelo servidor da Kiara. Não edite: as notas são reescritas.\n\n[[Padrões gerais]]\n")
    return notes


class LearningService:
    def __init__(self, postgres: PostgresRepository | None) -> None:
        self.postgres = postgres

    async def touch(self, organization_id: str) -> None:
        """Puts the workspace in the learning registry (called when it searches for leads)."""
        if self.postgres is None:
            return
        try:
            async with self.postgres._transaction(organization_id) as connection:
                await connection.execute(
                    """INSERT INTO learning_workspaces(organization_id) VALUES(%s)
                       ON CONFLICT (organization_id) DO UPDATE SET last_activity_at=now()""",
                    (_uuid("organization", organization_id),))
        except Exception:  # noqa: BLE001 - learning never breaks a search
            pass

    async def patterns(self) -> list[dict[str, Any]]:
        if self.postgres is None:
            return []
        async with await self.postgres._connect() as connection:
            rows = await (await connection.execute(
                "SELECT niche,city,searches,results,with_whatsapp,without_website,added,advanced,won,workspaces FROM kiara_patterns")).fetchall()
        return [dict(row) for row in rows]

    async def tick(self) -> dict[str, Any]:
        if self.postgres is None:
            raise ApiError(503, "learning_store_unavailable", "Banco de dados não configurado.")
        async with await self.postgres._connect() as connection:
            registry = await (await connection.execute(
                "SELECT organization_id FROM learning_workspaces ORDER BY last_activity_at DESC LIMIT %s", (MAX_WORKSPACES,))).fetchall()
        per_workspace, taught = [], 0
        for row in registry:
            organization_id = str(row["organization_id"])
            try:
                async with self.postgres._transaction(organization_id) as connection:
                    org = _uuid("organization", organization_id)
                    rows = [dict(item) for item in await (await connection.execute(SEARCH_STATS, (org,))).fetchall()]
                    facts = lessons(rows)
                    await connection.execute("DELETE FROM kiara_memories WHERE organization_id=%s AND source='learned'", (org,))
                    for fact in facts:
                        await connection.execute(
                            """INSERT INTO kiara_memories(organization_id,fact,source) VALUES(%s,%s,'learned')
                               ON CONFLICT (organization_id, lower(btrim(fact))) DO UPDATE SET updated_at=now()""", (org, fact))
                    await connection.execute("UPDATE learning_workspaces SET learned_at=now() WHERE organization_id=%s", (org,))
                per_workspace.append(rows)
                taught += int(bool(facts))
            except Exception:  # noqa: BLE001 - one workspace never stops the others
                continue
        patterns = aggregate(per_workspace)
        async with await self.postgres._connect() as connection, connection.transaction():
            await connection.execute("DELETE FROM kiara_patterns")
            for item in patterns:
                await connection.execute(
                    """INSERT INTO kiara_patterns(niche,city,searches,results,with_whatsapp,without_website,added,advanced,won,workspaces)
                       VALUES(%(niche)s,%(city)s,%(searches)s,%(results)s,%(with_whatsapp)s,%(without_website)s,%(added)s,%(advanced)s,%(won)s,%(workspaces)s)""",
                    item)
        return {"workspaces": len(registry), "learned": len(per_workspace), "with_lessons": taught, "patterns": len(patterns),
                "shared_patterns": sum(1 for item in patterns if item["workspaces"] >= MIN_WORKSPACES)}

    async def vault(self) -> dict[str, Any]:
        patterns = await self.patterns()
        async with await self.postgres._connect() as connection:
            row = await (await connection.execute("SELECT count(*) AS total FROM learning_workspaces")).fetchone()
        return {"files": vault_notes(patterns, int(row["total"]))}


def _worker(request: Request) -> None:
    expected = os.getenv("KIARA_WORKER_TOKEN") or os.getenv("CRON_SECRET")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        raise ApiError(401, "worker_unauthorized", "Worker não autorizado.")


def create_learning_router(service: LearningService) -> APIRouter:
    router = APIRouter(prefix="/v1/learning", tags=["learning"])

    @router.post("/internal/tick")
    async def tick(request: Request) -> dict[str, Any]:
        _worker(request)
        return await service.tick()

    @router.get("/internal/vault")
    async def vault(request: Request) -> dict[str, Any]:
        _worker(request)
        return await service.vault()

    @router.get("/patterns")
    async def patterns(context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        del context
        return {"items": pattern_lines(await service.patterns(), limit=12), "min_workspaces": MIN_WORKSPACES}

    return router
