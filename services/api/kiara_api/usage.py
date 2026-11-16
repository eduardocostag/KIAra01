"""Plans and monthly usage limits.

Every costly action (leads searched, images, videos, internet searches, AI messages) counts against the
month of the client's plan. The payment provider is plugged in later; until then a workspace without a
subscription starts on the trial plan and only the monthly limits apply (an expired trial is not blocked
unless KIARA_BILLING_ENFORCE=1).
"""
from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

SYSTEM_ADMIN_EMAIL = "admin@kiara.local"
PLANS: dict[str, dict[str, Any]] = {
    "trial": {"label": "Teste grátis", "price_cents": 0, "limits": {"images": 20, "videos": 3, "web_searches": 100, "ai_messages": 300, "seats": 1}},
    "starter": {"label": "Essencial", "price_cents": 19700, "limits": {"images": 60, "videos": 6, "web_searches": 400, "ai_messages": 1500, "seats": 1}},
    "pro": {"label": "Profissional", "price_cents": 49700, "limits": {"images": 250, "videos": 25, "web_searches": 2000, "ai_messages": 6000, "seats": 3}},
    "business": {"label": "Empresa", "price_cents": 129700, "limits": {"images": 1000, "videos": 100, "web_searches": 10000, "ai_messages": 30000, "seats": 10}},
}
# Leads have no limit on any plan (decision 2026-11-16): searches are still counted, never blocked.
METRIC_LABELS = {"leads": "leads pesquisados", "images": "imagens", "videos": "vídeos", "web_searches": "pesquisas na internet",
                 "ai_messages": "mensagens escritas pela Kiara", "seats": "pessoas na equipe"}


def month_start(now: datetime | None = None) -> date:
    today = (now or datetime.now(UTC)).date()
    return today.replace(day=1)


def enforce_trial() -> bool:
    return os.getenv("KIARA_BILLING_ENFORCE", "").strip() == "1"


async def subscription(connection, organization_uuid) -> dict[str, Any]:
    row = await (await connection.execute(
        "SELECT plan,status,trial_ends_at,current_period_end,provider FROM subscriptions WHERE organization_id=%s",
        (organization_uuid,))).fetchone()
    if row is None:
        row = await (await connection.execute(
            """INSERT INTO subscriptions(organization_id) VALUES(%s) ON CONFLICT (organization_id) DO UPDATE SET updated_at=now()
               RETURNING plan,status,trial_ends_at,current_period_end,provider""", (organization_uuid,))).fetchone()
    return dict(row)


async def consume(connection, organization_uuid, metric: str, amount: int = 1, *, unlimited: bool = False) -> int:
    """Counts `amount` of `metric` for this month; raises 402 when the plan's limit would be passed."""
    plan = await subscription(connection, organization_uuid)
    if enforce_trial() and plan["status"] == "trialing" and plan["trial_ends_at"] < datetime.now(UTC):
        raise ApiError(402, "trial_ended", "Seu período de teste terminou. Escolha um plano para continuar.")
    if plan["status"] in {"past_due", "canceled"} and enforce_trial():
        raise ApiError(402, "subscription_inactive", "Sua assinatura está pendente. Atualize o pagamento para continuar.")
    limit = PLANS[plan["plan"]]["limits"].get(metric)
    row = await (await connection.execute(
        """INSERT INTO usage_counters(organization_id,metric,period,used) VALUES(%s,%s,%s,%s)
           ON CONFLICT (organization_id,metric,period) DO UPDATE SET used=usage_counters.used+excluded.used
           RETURNING used""", (organization_uuid, metric, month_start(), amount))).fetchone()
    used = int(row["used"])
    if limit is not None and not unlimited and used > limit:
        raise ApiError(402, "plan_limit_reached",
                       f"Você usou todo o limite de {METRIC_LABELS.get(metric, metric)} do seu plano neste mês ({limit}). "
                       "Mude de plano para continuar agora, ou aguarde o próximo mês.")
    return used


class UsageService:
    def __init__(self, postgres: PostgresRepository | None) -> None:
        self._postgres = postgres

    async def consume(self, context: RequestContext, metric: str, amount: int = 1) -> None:
        if self._postgres is None or amount <= 0:
            return
        unlimited = (context.email or "").strip().lower() == SYSTEM_ADMIN_EMAIL
        # The counter is committed only when the limit holds: a refused action does not spend the quota.
        async with self._postgres._transaction(context.organization_id) as connection:
            await consume(connection, _uuid("organization", context.organization_id), metric, amount, unlimited=unlimited)

    async def overview(self, context: RequestContext) -> dict[str, Any]:
        org = _uuid("organization", context.organization_id)
        async with self._postgres._transaction(context.organization_id) as connection:
            plan = await subscription(connection, org)
            rows = await (await connection.execute(
                "SELECT metric,used FROM usage_counters WHERE organization_id=%s AND period=%s", (org, month_start()))).fetchall()
            seats = await (await connection.execute(
                "SELECT count(*) AS total FROM team_seats WHERE organization_id=%s", (org,))).fetchone()
        used = {row["metric"]: int(row["used"]) for row in rows}
        used["seats"] = 1 + int(seats["total"])
        limits = PLANS[plan["plan"]]["limits"]
        return {
            "plan": plan["plan"], "label": PLANS[plan["plan"]]["label"], "status": plan["status"],
            "trial_ends_at": plan["trial_ends_at"].isoformat() if plan["trial_ends_at"] else None,
            "current_period_end": plan["current_period_end"].isoformat() if plan["current_period_end"] else None,
            "billing_connected": bool(plan["provider"]),
            "usage": [{"metric": metric, "label": METRIC_LABELS[metric], "used": used.get(metric, 0), "limit": limit} for metric, limit in limits.items()],
            "plans": [{"id": key, "label": value["label"], "price_cents": value["price_cents"], "limits": value["limits"]}
                      for key, value in PLANS.items() if key != "trial"],
        }


def create_usage_router(service: UsageService) -> APIRouter:
    router = APIRouter(prefix="/v1/billing", tags=["billing"])

    @router.get("/plan")
    async def plan(context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        if service._postgres is None:
            raise ApiError(503, "billing_unavailable", "Planos indisponíveis neste servidor.")
        return await service.overview(context)

    return router
