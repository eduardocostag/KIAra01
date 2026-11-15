"""Results dashboard: what Kiara produced in a period, in leads, conversations and money.

Money comes from the deal value of each lead, or the average deal value in the sales profile when a lead
has none. Each metric is compared with the previous period of the same length.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

STAGES = ("new", "qualified", "contacted", "opportunity", "won", "lost")

# Distinct leads per event kind in [since, until). Values use the lead's own value or the average.
_PERIOD_SQL = """
WITH avg AS (SELECT COALESCE((SELECT average_deal_cents FROM sales_profiles WHERE organization_id=%(org)s), 0) AS cents),
reached AS (
  SELECT e.pipeline_entry_id, e.to_stage FROM pipeline_stage_events e
  WHERE e.organization_id=%(org)s AND e.created_at>=%(since)s AND e.created_at<%(until)s
),
replied AS (
  SELECT pipeline_entry_id FROM outreach_activities
   WHERE organization_id=%(org)s AND status='replied' AND created_at>=%(since)s AND created_at<%(until)s
  UNION SELECT pipeline_entry_id FROM reached WHERE to_stage IN ('qualified','opportunity','won')
),
generated AS (SELECT DISTINCT pipeline_entry_id FROM reached WHERE to_stage IN ('opportunity','won')),
won AS (SELECT DISTINCT pipeline_entry_id FROM reached WHERE to_stage='won')
SELECT
  (SELECT count(*) FROM hunter_results WHERE organization_id=%(org)s AND created_at>=%(since)s AND created_at<%(until)s) AS found,
  (SELECT count(*) FROM pipeline_entries WHERE organization_id=%(org)s AND created_at>=%(since)s AND created_at<%(until)s) AS added,
  (SELECT count(DISTINCT pipeline_entry_id) FROM outreach_activities
    WHERE organization_id=%(org)s AND status='sent' AND created_at>=%(since)s AND created_at<%(until)s) AS approached,
  (SELECT count(DISTINCT thread_id) FROM messages
    WHERE organization_id=%(org)s AND direction='inbound' AND sent_at>=%(since)s AND sent_at<%(until)s) AS conversations,
  (SELECT count(DISTINCT pipeline_entry_id) FROM replied) AS replied,
  (SELECT count(*) FROM generated) AS opportunities,
  (SELECT count(*) FROM won) AS won,
  (SELECT COALESCE(sum(COALESCE(p.deal_value_cents, (SELECT cents FROM avg))), 0) FROM generated g
     JOIN pipeline_entries p ON p.organization_id=%(org)s AND p.id=g.pipeline_entry_id) AS generated_cents,
  (SELECT COALESCE(sum(COALESCE(p.deal_value_cents, (SELECT cents FROM avg))), 0) FROM won w
     JOIN pipeline_entries p ON p.organization_id=%(org)s AND p.id=w.pipeline_entry_id) AS won_cents
"""

_NOW_SQL = """
SELECT p.stage, count(*) AS total,
       COALESCE(sum(COALESCE(p.deal_value_cents,
         (SELECT average_deal_cents FROM sales_profiles WHERE organization_id=%(org)s), 0)), 0) AS cents
FROM pipeline_entries p WHERE p.organization_id=%(org)s GROUP BY p.stage
"""

_WEEKLY_SQL = """
SELECT date_trunc('week', d)::date AS week,
  (SELECT count(DISTINCT pipeline_entry_id) FROM outreach_activities
    WHERE organization_id=%(org)s AND status='sent' AND created_at>=d AND created_at<d + interval '7 days') AS approached,
  (SELECT count(DISTINCT pipeline_entry_id) FROM pipeline_stage_events
    WHERE organization_id=%(org)s AND to_stage='won' AND created_at>=d AND created_at<d + interval '7 days') AS won
FROM generate_series(date_trunc('week', now()) - interval '7 weeks', date_trunc('week', now()), interval '1 week') AS d
ORDER BY week
"""

METRICS = ("found", "added", "approached", "conversations", "replied", "opportunities", "won", "generated_cents", "won_cents")


class DealValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipeline_entry_id: str = Field(min_length=1, max_length=128)
    value_cents: int | None = Field(default=None, ge=0, le=100_000_000_000)


class ResultsRepository:
    def __init__(self, postgres: PostgresRepository) -> None:
        self._postgres = postgres

    async def summary(self, organization_id: str, days: int, now: datetime | None = None) -> dict[str, Any]:
        org = _uuid("organization", organization_id)
        until = now or datetime.now(UTC)
        since, before = until - timedelta(days=days), until - timedelta(days=2 * days)
        async with self._postgres._transaction(organization_id) as connection:
            current = await (await connection.execute(_PERIOD_SQL, {"org": org, "since": since, "until": until})).fetchone()
            previous = await (await connection.execute(_PERIOD_SQL, {"org": org, "since": before, "until": since})).fetchone()
            stages = await (await connection.execute(_NOW_SQL, {"org": org})).fetchall()
            weekly = await (await connection.execute(_WEEKLY_SQL, {"org": org})).fetchall()
            average = await (await connection.execute(
                "SELECT average_deal_cents FROM sales_profiles WHERE organization_id=%s", (org,))).fetchone()
        by_stage = {row["stage"]: row for row in stages}
        return {
            "days": days,
            "since": since.isoformat(),
            "current": {key: int(current[key] or 0) for key in METRICS},
            "previous": {key: int(previous[key] or 0) for key in METRICS},
            "funnel": [{"stage": stage, "total": int(by_stage[stage]["total"]) if stage in by_stage else 0,
                        "cents": int(by_stage[stage]["cents"]) if stage in by_stage else 0} for stage in STAGES],
            "open_cents": sum(int(by_stage[stage]["cents"]) for stage in ("qualified", "opportunity") if stage in by_stage),
            "weekly": [{"week": row["week"].isoformat(), "approached": int(row["approached"]), "won": int(row["won"])} for row in weekly],
            "average_deal_cents": int(average["average_deal_cents"]) if average else 0,
        }

    async def set_deal_value(self, organization_id: str, entry_id: str, value_cents: int | None) -> None:
        org, entry = _uuid("organization", organization_id), _uuid("pipeline", entry_id)
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                "UPDATE pipeline_entries SET deal_value_cents=%s,version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s RETURNING id",
                (value_cents, org, entry))).fetchone()
        if row is None:
            raise ApiError(404, "pipeline_entry_not_found", "Lead não encontrado no funil.")


def create_results_router(repository: ResultsRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/sales", tags=["sales"])

    @router.get("/results")
    async def results(context: Annotated[RequestContext, Depends(authenticated_context)],
                      days: Annotated[int, Query(ge=7, le=365)] = 30) -> dict[str, Any]:
        return await repository.summary(context.organization_id, days)

    @router.put("/deal-value", status_code=204)
    async def deal_value(body: DealValue, context: Annotated[RequestContext, Depends(authenticated_context)]) -> None:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Acesso restrito a operadores.")
        await repository.set_deal_value(context.organization_id, body.pipeline_entry_id, body.value_cents)

    return router
