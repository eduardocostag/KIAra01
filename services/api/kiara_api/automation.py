"""Kiara Automation on the server, plus the approval center.

Flows are saved per organization. A worker tick (called every minute by the Kiara server or any
cron) fires schedules and "new lead" triggers and runs the queued flows here, in the API:
AI, logic, CRM reading and HTTPS reads execute for real; every external action (WhatsApp,
e-mail, agenda, posts, ads, computer) becomes an item in the approval center instead of being
executed or simulated. Nothing reaches a customer without a person approving it.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context, system_administrator_context
from .http.errors import ApiError

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
MAX_STEPS = 60
MAX_TEXT = 8000
INLINE_DELAY_SECONDS = 10
DECIDERS = {"owner", "admin"}

# Blocks the server runs itself, and blocks that become an approval request.
SERVER_KINDS = {"trigger.manual", "trigger.schedule", "trigger.lead", "ai.generate", "ai.classify",
                "logic.condition", "logic.delay", "logic.notify", "crm.read", "web.http"}
APPROVAL_KINDS = {
    "messages.whatsapp": ("whatsapp", "Enviar WhatsApp"),
    "messages.email": ("email", "Enviar e-mail"),
    "calendar.event": ("calendar", "Criar evento na agenda"),
    "web.browse": ("web.browse", "Navegar em site"),
    "machine.command": ("machine.command", "Ação no computador"),
    "machine.files": ("machine.files", "Organizar arquivos"),
    "social.instagram": ("social.instagram", "Post no Instagram"),
    "social.facebook": ("social.facebook", "Post no Facebook"),
    "social.linkedin": ("social.linkedin", "Post no LinkedIn"),
    "social.google": ("social.google", "Post no Google"),
    "ads.meta": ("ads.meta", "Anúncio Meta"),
    "ads.google": ("ads.google", "Anúncio Google"),
    "ads.linkedin": ("ads.linkedin", "Anúncio LinkedIn"),
}
BLOCKED_ON_SERVER = {
    "trigger.whatsapp": "O gatilho do WhatsApp depende do WhatsApp conectado no servidor da Kiara.",
    "code.js": "Código JavaScript roda só quando você executa o fluxo pela tela.",
}
KNOWN_KINDS = SERVER_KINDS | set(APPROVAL_KINDS) | set(BLOCKED_ON_SERVER)
TRIGGER_KINDS = {"trigger.manual", "trigger.schedule", "trigger.lead", "trigger.whatsapp"}
STAGES = {"active", "new", "qualified", "contacted", "opportunity", "won", "lost"}


# ---------------------------------------------------------------- payloads

class FlowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    type: str = Field(max_length=40)
    x: float = 0
    y: float = 0
    config: dict[str, str | int | float] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def known(cls, value: str) -> str:
        if value not in KNOWN_KINDS:
            raise ValueError("Bloco desconhecido.")
        return value

    @field_validator("config")
    @classmethod
    def bounded(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 20 or any(len(key) > 40 or (isinstance(item, str) and len(item) > 5000) for key, item in value.items()):
            raise ValueError("Configuração do bloco grande demais.")
        return value


class FlowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    to: str = Field(max_length=80)
    from_: str = Field(alias="from", max_length=80)
    port: Literal["yes", "no"] | None = None


class FlowDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[FlowNode] = Field(max_length=80)
    edges: list[FlowEdge] = Field(default_factory=list, max_length=160)


class FlowSave(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    definition: FlowDefinition
    enabled: bool = False


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject", "done"]
    version: int = Field(ge=1)
    payload: dict[str, str] | None = None
    note: str | None = Field(default=None, max_length=500)

    @field_validator("payload")
    @classmethod
    def bounded(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is not None and (len(value) > 20 or any(len(key) > 40 or len(item) > 5000 for key, item in value.items())):
            raise ValueError("Edição grande demais.")
        return value


def definition_dict(definition: FlowDefinition) -> dict[str, Any]:
    return {"nodes": [node.model_dump() for node in definition.nodes],
            "edges": [edge.model_dump(by_alias=True, exclude_none=True) for edge in definition.edges]}


# ---------------------------------------------------------------- schedule

def next_schedule(config: dict[str, Any], after: datetime) -> datetime:
    """Next run of a schedule trigger (cadence daily/weekdays/weekly, São Paulo time)."""
    cadence = str(config.get("cadence") or "weekly")
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", str(config.get("time") or "09:00"))
    hour, minute = (int(match.group(1)), int(match.group(2))) if match else (9, 0)
    try:
        weekday_js = int(config.get("weekday", 1)) % 7
    except (TypeError, ValueError):
        weekday_js = 1
    local = after.astimezone(LOCAL_TZ)
    for offset in range(0, 8):
        day = (local + timedelta(days=offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if day <= local:
            continue
        js_day = (day.weekday() + 1) % 7  # Python: Monday=0; JS: Sunday=0
        if cadence == "daily" or (cadence == "weekdays" and js_day not in {0, 6}) or (cadence != "daily" and cadence != "weekdays" and js_day == weekday_js):
            return day.astimezone(UTC)
    return (local + timedelta(days=7)).astimezone(UTC)


# ---------------------------------------------------------------- runner

@dataclass
class RunEnv:
    """What a flow can touch. Every external effect goes through request_approval."""
    ask: Callable[[str], Awaitable[str]]
    leads: Callable[[str, int], Awaitable[list[str]]]
    latest_lead: Callable[[], Awaitable[str | None]]
    http_get: Callable[[str], Awaitable[str]]
    request_approval: Callable[[dict[str, Any], str, str, dict[str, Any]], Awaitable[str]]
    notify: Callable[[str, str], Awaitable[None]]


@dataclass
class RunState:
    steps: list[dict[str, Any]] = field(default_factory=list)
    pending: list[dict[str, Any]] = field(default_factory=list)
    resume_at: datetime | None = None


class Blocked(Exception):
    pass


class Waiting(Exception):
    def __init__(self, seconds: int) -> None:
        super().__init__(seconds)
        self.seconds = seconds


def fill(template: Any, value: str) -> str:
    return str(template if template is not None else "").replace("{{entrada}}", value).replace("{{lead}}", value)


def _number(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(float(value))))
    except (TypeError, ValueError):
        return default


def approval_title(node_type: str, payload: dict[str, Any]) -> str:
    label = APPROVAL_KINDS[node_type][1]
    target = payload.get("to") or payload.get("url") or payload.get("title") or ""
    return f"{label}: {target}"[:200] if target else label


async def execute_node(node: dict[str, Any], value: str, env: RunEnv, *, resumed: bool = False) -> tuple[str, str | None]:
    """Runs one block. Returns (output, port) or raises Blocked/Waiting."""
    kind, config = node["type"], node.get("config") or {}
    if kind in BLOCKED_ON_SERVER:
        raise Blocked(BLOCKED_ON_SERVER[kind])
    if kind in APPROVAL_KINDS:
        payload = {key: fill(item, value) if isinstance(item, str) else item for key, item in config.items()}
        payload["entrada"] = value[:MAX_TEXT]
        request_id = await env.request_approval(node, APPROVAL_KINDS[kind][0], approval_title(kind, payload), payload)
        return request_id, "approval"
    if kind in {"trigger.manual", "trigger.schedule"}:
        return value, None
    if kind == "trigger.lead":
        if value:
            return value, None
        latest = await env.latest_lead()
        if not latest:
            raise RuntimeError("Ainda não há leads no CRM.")
        return latest, None
    if kind == "ai.generate":
        return (await env.ask(fill(config.get("prompt"), value)))[:MAX_TEXT], None
    if kind == "ai.classify":
        answer = await env.ask(f"{fill(config.get('question'), value)}\n\nResponda apenas com SIM ou NÃO.")
        yes = re.search(r"\bsim\b", answer, re.IGNORECASE) and not re.search(r"\bn[ãa]o\b", answer, re.IGNORECASE)
        return ("SIM" if yes else "NÃO"), None
    if kind == "logic.condition":
        needle = str(config.get("contains") or "").strip().lower()
        return value, ("yes" if needle and needle in value.lower() else "no")
    if kind == "logic.delay":
        seconds = _number(config.get("seconds"), 5, 1, 86_400)
        if resumed:
            return value, None
        if seconds <= INLINE_DELAY_SECONDS:
            await asyncio.sleep(seconds)
            return value, None
        raise Waiting(seconds)
    if kind == "logic.notify":
        await env.notify(str(config.get("title") or "Kiara Automation")[:120], value[:MAX_TEXT])
        return value, None
    if kind == "crm.read":
        stage = str(config.get("stage") or "active")
        rows = await env.leads(stage if stage in STAGES else "active", _number(config.get("limit"), 10, 1, 50))
        return ("\n".join(rows) if rows else "Nenhum lead nessa etapa."), None
    if kind == "web.http":
        url = fill(config.get("url"), value).strip()
        if not url.lower().startswith("https://"):
            raise RuntimeError("Informe um endereço https.")
        return (await env.http_get(url))[:MAX_TEXT], None
    raise Blocked("Este bloco ainda não executa no servidor.")


def initial_queue(definition: dict[str, Any], trigger: str, value: str) -> list[dict[str, Any]]:
    wanted = {"manual": {"trigger.manual", "trigger.schedule", "trigger.lead"}, "schedule": {"trigger.schedule"}, "lead": {"trigger.lead"}}[trigger]
    return [{"node": node["id"], "input": value} for node in definition.get("nodes", []) if node.get("type") in wanted]


async def run_flow(definition: dict[str, Any], state: RunState, env: RunEnv, *, deadline: float) -> RunState:
    """Walks the flow breadth-first from the pending queue until done, waiting or out of time."""
    nodes = {node["id"]: node for node in definition.get("nodes", [])}
    edges = definition.get("edges", [])
    while state.pending:
        if time.monotonic() > deadline:
            return state  # Out of this tick's time: the rest continues on the next tick.
        item = state.pending.pop(0)
        node = nodes.get(item["node"])
        if node is None:
            continue
        if len(state.steps) >= MAX_STEPS:
            state.steps.append({"node_id": node["id"], "status": "error", "message": f"O fluxo passou de {MAX_STEPS} passos e foi interrompido (verifique se há um ciclo).", "at": _iso(datetime.now(UTC))})
            state.pending.clear()
            return state
        step: dict[str, Any] = {"node_id": node["id"], "type": node["type"], "at": _iso(datetime.now(UTC))}
        try:
            output, port = await execute_node(node, item.get("input", ""), env, resumed=bool(item.get("resumed")))
        except Waiting as wait:
            state.pending.insert(0, {**item, "resumed": True})
            state.resume_at = datetime.now(UTC) + timedelta(seconds=wait.seconds)
            state.steps.append({**step, "status": "waiting", "message": f"Esperando {wait.seconds} segundos."})
            return state
        except Blocked as error:
            state.steps.append({**step, "status": "blocked", "message": str(error)})
            continue
        except Exception as error:  # noqa: BLE001 - one failing block stops only its branch
            message = str(error) if isinstance(error, RuntimeError) and str(error) else "O bloco falhou."
            state.steps.append({**step, "status": "error", "message": message[:300]})
            continue
        if port == "approval":
            state.steps.append({**step, "status": "approval", "message": "Enviado para a Central de aprovações.", "request_id": output})
            continue  # The branch waits for a person; nothing after it runs on its own.
        state.steps.append({**step, "status": "done", "output": output[:2000]})
        for edge in edges:
            if edge.get("from") == node["id"] and (port is None or (edge.get("port") or "yes") == port) and edge.get("to") in nodes:
                state.pending.append({"node": edge["to"], "input": output})
    return state


def run_status(state: RunState) -> str:
    if state.pending:
        return "waiting" if state.resume_at else "queued"
    statuses = {step["status"] for step in state.steps}
    if "error" in statuses and statuses <= {"error", "blocked"}:
        return "failed"
    return "partial" if statuses & {"error", "blocked"} else "done"


# ---------------------------------------------------------------- AI and web helpers

AUTOMATION_CONTEXT = ("Você é a Kiara, executando uma automação de um cliente. Responda em português do Brasil, "
                      "de forma direta, sem inventar dados. Os dados abaixo vêm do fluxo e do CRM do cliente.\n\n")


def default_ask() -> Callable[[str], Awaitable[str]]:
    from .chat import _configuration

    async def ask(prompt: str) -> str:
        base, model, key = _configuration()
        if not base:
            raise RuntimeError("A IA do servidor não está configurada (KIARA_CHAT_API_BASE_URL, KIARA_CHAT_MODEL e KIARA_CHAT_API_KEY).")
        from app.providers.remote import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(model=model, api_key=key, base_url=base, timeout_seconds=60,
                                            vision_enabled=False, max_output_tokens=2048, follow_redirects=False)
        try:
            text = await asyncio.wait_for(provider.generate(AUTOMATION_CONTEXT + prompt[:12_000]), timeout=65)
        except Exception:  # noqa: BLE001 - never echo provider bodies or keys
            raise RuntimeError("A IA não respondeu. A execução continua nos outros caminhos.") from None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("A IA respondeu vazio.")
        return text.strip()

    return ask


def public_https_get(url: str) -> str:
    from urllib.request import Request as UrlRequest
    from urllib.request import build_opener

    from .hunter import _assert_public_destination, _SafeRedirectHandler

    _assert_public_destination(url)
    request = UrlRequest(url, headers={"User-Agent": "KiaraAutomation/1.0", "Accept": "application/json,text/*;q=0.9"})
    with build_opener(_SafeRedirectHandler()).open(request, timeout=12) as response:
        payload = response.read(200_001)[:200_000]
        charset = response.headers.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def describe_lead(row: dict[str, Any]) -> str:
    hunter = (row.get("attributes") or {}).get("hunter") or {}
    labels = {"new": "Novos", "qualified": "Qualificados", "contacted": "Em contato", "opportunity": "Oportunidades", "won": "Ganhos", "lost": "Perdidos"}
    parts = [row.get("display_name") or "Contato sem nome", hunter.get("phone"), hunter.get("address"),
             f"etapa: {labels.get(row.get('stage'), row.get('stage'))}" if row.get("stage") else None,
             f"próxima ação: {row['next_action']}" if row.get("next_action") else None]
    return " · ".join(str(part) for part in parts if part)


# ---------------------------------------------------------------- repository

class AutomationRepository:
    def __init__(self, postgres: PostgresRepository | None, *, ask: Callable[[str], Awaitable[str]] | None = None,
                 http_get: Callable[[str], str] = public_https_get) -> None:
        self._postgres = postgres
        self._ask = ask
        self._http_get = http_get

    def _store(self) -> PostgresRepository:
        if self._postgres is None:
            raise ApiError(503, "automation_store_unavailable", "As automações exigem o banco PostgreSQL configurado.")
        return self._postgres

    # ---- flows

    @staticmethod
    def _flow(row: dict[str, Any], triggers: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"id": row["client_key"], "server_id": str(row["id"]), "name": row["name"], "nodes": row["definition"].get("nodes", []),
                "edges": row["definition"].get("edges", []), "enabled": row["enabled"], "version": row["version"],
                "updatedAt": int(row["updated_at"].timestamp() * 1000), "next_run_at": _iso((triggers or {}).get("schedule"))}

    async def list_flows(self, organization_id: str) -> list[dict[str, Any]]:
        org = _uuid("organization", organization_id)
        async with self._store()._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                "SELECT id,client_key,name,definition,enabled,version,updated_at FROM automation_flows WHERE organization_id=%s ORDER BY updated_at DESC LIMIT 100",
                (org,))).fetchall()
            triggers = await (await connection.execute(
                "SELECT flow_id,next_at FROM automation_triggers WHERE organization_id=%s AND kind='schedule'", (org,))).fetchall()
        next_by_flow = {row["flow_id"]: row["next_at"] for row in triggers}
        return [self._flow(row, {"schedule": next_by_flow.get(row["id"])}) for row in rows]

    async def _sync_triggers(self, connection: Any, org: Any, flow_id: Any, definition: dict[str, Any], enabled: bool) -> datetime | None:
        await connection.execute("DELETE FROM automation_triggers WHERE organization_id=%s AND flow_id=%s", (org, flow_id))
        if not enabled:
            return None
        now = datetime.now(UTC)
        schedules = [next_schedule(node.get("config") or {}, now) for node in definition["nodes"] if node["type"] == "trigger.schedule"]
        first = min(schedules) if schedules else None
        if first:
            await connection.execute("INSERT INTO automation_triggers(organization_id,flow_id,kind,next_at) VALUES(%s,%s,'schedule',%s)", (org, flow_id, first))
        if any(node["type"] == "trigger.lead" for node in definition["nodes"]):
            await connection.execute("INSERT INTO automation_triggers(organization_id,flow_id,kind,next_at) VALUES(%s,%s,'lead',now())", (org, flow_id))
            await connection.execute("UPDATE automation_flows SET lead_cursor=COALESCE(lead_cursor,now()) WHERE organization_id=%s AND id=%s", (org, flow_id))
        return first

    async def save_flow(self, context: RequestContext, client_key: str, payload: FlowSave) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", client_key):
            raise ApiError(422, "flow_id_invalid", "Identificador de fluxo inválido.")
        definition = definition_dict(payload.definition)
        if payload.enabled and not any(node["type"] in TRIGGER_KINDS for node in definition["nodes"]):
            raise ApiError(422, "flow_without_trigger", "Adicione um gatilho antes de ativar o fluxo.")
        org, user = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        async with self._store()._transaction(context.organization_id) as connection:
            row = await (await connection.execute(
                """INSERT INTO automation_flows(organization_id,id,client_key,name,definition,enabled,created_by)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (organization_id,client_key) DO UPDATE SET name=EXCLUDED.name,definition=EXCLUDED.definition,
                     enabled=EXCLUDED.enabled,version=automation_flows.version+1,updated_at=now()
                   RETURNING id,client_key,name,definition,enabled,version,updated_at""",
                (org, uuid4(), client_key, payload.name.strip(), json.dumps(definition), payload.enabled, user))).fetchone()
            first = await self._sync_triggers(connection, org, row["id"], definition, payload.enabled)
        return self._flow(row, {"schedule": first})

    async def delete_flow(self, context: RequestContext, client_key: str) -> None:
        async with self._store()._transaction(context.organization_id) as connection:
            await connection.execute("DELETE FROM automation_flows WHERE organization_id=%s AND client_key=%s",
                                     (_uuid("organization", context.organization_id), client_key))

    async def _flow_id(self, connection: Any, org: Any, client_key: str) -> Any:
        row = await (await connection.execute("SELECT id FROM automation_flows WHERE organization_id=%s AND client_key=%s", (org, client_key))).fetchone()
        if not row:
            raise ApiError(404, "flow_not_found", "Salve o fluxo antes de executá-lo no servidor.")
        return row["id"]

    async def _create_run(self, connection: Any, org: Any, flow_id: Any, definition: dict[str, Any], trigger: str,
                          value: str = "", requested_by: Any = None) -> Any:
        run_id = uuid4()
        queue = initial_queue(definition, trigger, value)
        await connection.execute(
            "INSERT INTO automation_runs(organization_id,id,flow_id,trigger,input,pending,requested_by) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (org, run_id, flow_id, trigger, value[:MAX_TEXT], json.dumps(queue), requested_by))
        await connection.execute("INSERT INTO automation_work_queue(organization_id,run_id) VALUES(%s,%s)", (org, run_id))
        return run_id

    async def enqueue_manual(self, context: RequestContext, client_key: str) -> dict[str, Any]:
        org = _uuid("organization", context.organization_id)
        async with self._store()._transaction(context.organization_id) as connection:
            flow = await (await connection.execute("SELECT id,definition FROM automation_flows WHERE organization_id=%s AND client_key=%s", (org, client_key))).fetchone()
            if not flow:
                raise ApiError(404, "flow_not_found", "Salve o fluxo antes de executá-lo no servidor.")
            run_id = await self._create_run(connection, org, flow["id"], flow["definition"], "manual", requested_by=_uuid("user", context.user_id))
        return {"run_id": str(run_id), "status": "queued"}

    async def list_runs(self, organization_id: str, client_key: str | None) -> list[dict[str, Any]]:
        org = _uuid("organization", organization_id)
        async with self._store()._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT r.id,f.client_key,f.name,r.trigger,r.status,r.steps,r.error,r.created_at,r.started_at,r.finished_at
                   FROM automation_runs r JOIN automation_flows f ON f.organization_id=r.organization_id AND f.id=r.flow_id
                   WHERE r.organization_id=%s AND (%s::text IS NULL OR f.client_key=%s) ORDER BY r.created_at DESC LIMIT 30""",
                (org, client_key, client_key))).fetchall()
        return [{"id": str(row["id"]), "flow_id": row["client_key"], "flow_name": row["name"], "trigger": row["trigger"],
                 "status": row["status"], "steps": row["steps"], "error": row["error"], "created_at": _iso(row["created_at"]),
                 "started_at": _iso(row["started_at"]), "finished_at": _iso(row["finished_at"])} for row in rows]

    # ---- approvals

    @staticmethod
    def _request(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": str(row["id"]), "kind": row["kind"], "title": row["title"], "payload": row["payload"], "status": row["status"],
                "note": row["note"], "version": row["version"], "source": row["source"], "flow_name": row.get("flow_name"),
                "created_at": _iso(row["created_at"]), "decided_at": _iso(row["decided_at"])}

    async def list_requests(self, organization_id: str, status: str) -> dict[str, Any]:
        org = _uuid("organization", organization_id)
        statuses = ["pending"] if status == "pending" else ["approved", "rejected", "done", "failed"]
        async with self._store()._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT a.*,f.name flow_name FROM action_requests a LEFT JOIN automation_flows f
                   ON f.organization_id=a.organization_id AND f.id=a.flow_id
                   WHERE a.organization_id=%s AND a.status = ANY(%s) ORDER BY a.created_at DESC LIMIT 100""",
                (org, statuses))).fetchall()
            pending = await (await connection.execute(
                "SELECT count(*) AS total FROM action_requests WHERE organization_id=%s AND status='pending'", (org,))).fetchone()
        return {"items": [self._request(row) for row in rows], "pending": int(pending["total"])}

    async def decide(self, context: RequestContext, request_id: str, decision: Decision) -> dict[str, Any]:
        if context.role not in DECIDERS:
            raise ApiError(403, "insufficient_role", "Somente donos e administradores podem aprovar ações.")
        org, user = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        async with self._store()._transaction(context.organization_id) as connection:
            row = await (await connection.execute(
                "SELECT * FROM action_requests WHERE organization_id=%s AND id=%s FOR UPDATE", (org, _uuid("request", request_id)))).fetchone()
            if not row:
                raise ApiError(404, "request_not_found", "Pedido não encontrado.")
            if row["version"] != decision.version or row["status"] not in {"pending", "approved"}:
                raise ApiError(409, "request_changed", "Este pedido já foi decidido ou mudou. Atualize a página.")
            if row["status"] == "approved" and decision.decision != "done":
                raise ApiError(409, "request_changed", "Este pedido já foi aprovado.")
            payload = dict(row["payload"])
            if decision.payload:
                payload.update({key: value for key, value in decision.payload.items() if key in payload})
            status = {"approve": "done" if row["kind"] == "notice" else "approved", "reject": "rejected", "done": "done"}[decision.decision]
            updated = await (await connection.execute(
                """UPDATE action_requests SET status=%s,payload=%s,note=%s,decided_by=%s,decided_at=now(),version=version+1,updated_at=now()
                   WHERE organization_id=%s AND id=%s RETURNING *""",
                (status, json.dumps(payload), decision.note, user, org, row["id"]))).fetchone()
        return self._request(updated)

    # ---- worker

    async def _claim_triggers(self, worker: str) -> list[dict[str, Any]]:
        async with await self._store()._connect() as connection, connection.transaction():
            return await (await connection.execute(
                """WITH due AS (SELECT organization_id,flow_id,kind FROM automation_triggers
                     WHERE next_at<=now() AND (lease_owner IS NULL OR lease_expires_at<now())
                     ORDER BY next_at FOR UPDATE SKIP LOCKED LIMIT 20)
                   UPDATE automation_triggers t SET lease_owner=%s,lease_expires_at=now()+interval '2 minutes'
                   FROM due WHERE t.organization_id=due.organization_id AND t.flow_id=due.flow_id AND t.kind=due.kind
                   RETURNING t.organization_id,t.flow_id,t.kind""", (worker[:200],))).fetchall()

    async def _fire_trigger(self, trigger: dict[str, Any]) -> int:
        organization_id, org, flow_id = str(trigger["organization_id"]), trigger["organization_id"], trigger["flow_id"]
        created = 0
        async with self._store()._transaction(organization_id) as connection:
            flow = await (await connection.execute(
                "SELECT definition,enabled,lead_cursor FROM automation_flows WHERE organization_id=%s AND id=%s FOR UPDATE", (org, flow_id))).fetchone()
            if not flow or not flow["enabled"]:
                await connection.execute("DELETE FROM automation_triggers WHERE organization_id=%s AND flow_id=%s AND kind=%s", (org, flow_id, trigger["kind"]))
                return 0
            definition = flow["definition"]
            if trigger["kind"] == "schedule":
                await self._create_run(connection, org, flow_id, definition, "schedule")
                created = 1
                now = datetime.now(UTC)
                next_at = min(next_schedule(node.get("config") or {}, now) for node in definition["nodes"] if node["type"] == "trigger.schedule")
            else:
                rows = await (await connection.execute(
                    """SELECT c.display_name,c.attributes,p.stage,p.next_action,c.created_at FROM consumers c
                       LEFT JOIN pipeline_entries p ON p.organization_id=c.organization_id AND p.consumer_id=c.id
                       WHERE c.organization_id=%s AND c.created_at>%s AND c.lifecycle_status='active'
                         AND c.consent_status NOT IN ('revoked','opted_out')
                       ORDER BY c.created_at LIMIT 5""", (org, flow["lead_cursor"] or datetime.now(UTC)))).fetchall()
                for row in rows:
                    await self._create_run(connection, org, flow_id, definition, "lead", describe_lead(row))
                    created += 1
                if rows:
                    await connection.execute("UPDATE automation_flows SET lead_cursor=%s WHERE organization_id=%s AND id=%s", (rows[-1]["created_at"], org, flow_id))
                next_at = datetime.now(UTC) + timedelta(minutes=1)
            await connection.execute(
                "UPDATE automation_triggers SET next_at=%s,lease_owner=NULL,lease_expires_at=NULL WHERE organization_id=%s AND flow_id=%s AND kind=%s",
                (next_at, org, flow_id, trigger["kind"]))
        return created

    async def _claim_run(self, worker: str) -> dict[str, Any] | None:
        async with await self._store()._connect() as connection, connection.transaction():
            return await (await connection.execute(
                """WITH next AS (SELECT organization_id,run_id FROM automation_work_queue
                     WHERE available_at<=now() AND (lease_owner IS NULL OR lease_expires_at<now())
                     ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1)
                   UPDATE automation_work_queue q SET lease_owner=%s,lease_expires_at=now()+interval '3 minutes'
                   FROM next WHERE q.organization_id=next.organization_id AND q.run_id=next.run_id
                   RETURNING q.organization_id,q.run_id""", (worker[:200],))).fetchone()

    def _env(self, organization_id: str, org: Any, flow_id: Any, run_id: Any) -> RunEnv:
        store = self._store()
        ask = self._ask or default_ask()

        async def leads(stage: str, limit: int) -> list[str]:
            async with store._transaction(organization_id) as connection:
                rows = await (await connection.execute(
                    """SELECT c.display_name,c.attributes,p.stage,p.next_action FROM pipeline_entries p JOIN consumers c
                       ON c.organization_id=p.organization_id AND c.id=p.consumer_id
                       WHERE p.organization_id=%s AND c.lifecycle_status='active' AND c.consent_status NOT IN ('revoked','opted_out')
                         AND (CASE WHEN %s='active' THEN p.stage NOT IN ('won','lost') ELSE p.stage=%s END)
                       ORDER BY p.updated_at DESC LIMIT %s""", (org, stage, stage, limit))).fetchall()
            return [describe_lead(row) for row in rows]

        async def latest_lead() -> str | None:
            found = await leads("active", 1)
            return found[0] if found else None

        async def http_get(url: str) -> str:
            try:
                return await asyncio.wait_for(asyncio.to_thread(self._http_get, url), timeout=15)
            except Exception:  # noqa: BLE001 - external site failures without details
                raise RuntimeError("O site não respondeu ou não é um endereço público.") from None

        async def request_approval(node: dict[str, Any], kind: str, title: str, payload: dict[str, Any]) -> str:
            request_id = uuid4()
            async with store._transaction(organization_id) as connection:
                await connection.execute(
                    """INSERT INTO action_requests(organization_id,id,flow_id,run_id,node_id,kind,title,payload)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (org, request_id, flow_id, run_id, node["id"], kind, title, json.dumps(payload)))
            return str(request_id)

        async def notify(title: str, text: str) -> None:
            async with store._transaction(organization_id) as connection:
                await connection.execute(
                    """INSERT INTO action_requests(organization_id,id,flow_id,run_id,kind,title,payload)
                       VALUES(%s,%s,%s,%s,'notice',%s,%s)""",
                    (org, uuid4(), flow_id, run_id, title, json.dumps({"text": text})))

        return RunEnv(ask=ask, leads=leads, latest_lead=latest_lead, http_get=http_get, request_approval=request_approval, notify=notify)

    async def _process_run(self, claimed: dict[str, Any], deadline: float) -> str:
        organization_id, org, run_id = str(claimed["organization_id"]), claimed["organization_id"], claimed["run_id"]
        async with self._store()._transaction(organization_id) as connection:
            run = await (await connection.execute(
                """SELECT r.flow_id,r.steps,r.pending,f.definition FROM automation_runs r JOIN automation_flows f
                   ON f.organization_id=r.organization_id AND f.id=r.flow_id WHERE r.organization_id=%s AND r.id=%s""",
                (org, run_id))).fetchone()
            if run:
                await connection.execute("UPDATE automation_runs SET status='running',started_at=COALESCE(started_at,now()) WHERE organization_id=%s AND id=%s", (org, run_id))
        if not run:
            async with await self._store()._connect() as connection:
                await connection.execute("DELETE FROM automation_work_queue WHERE organization_id=%s AND run_id=%s", (org, run_id))
            return "missing"
        state = RunState(steps=list(run["steps"]), pending=list(run["pending"]))
        try:
            state = await run_flow(run["definition"], state, self._env(organization_id, org, run["flow_id"], run_id), deadline=deadline)
            status, error = run_status(state), None
        except Exception:  # noqa: BLE001 - a broken run must not stop the worker
            status, error = "failed", "A execução falhou de forma inesperada."
            state.pending.clear()
        finished = status in {"done", "partial", "failed"}
        async with self._store()._transaction(organization_id) as connection:
            await connection.execute(
                "UPDATE automation_runs SET status=%s,steps=%s,pending=%s,error=%s,finished_at=CASE WHEN %s THEN now() END WHERE organization_id=%s AND id=%s",
                (status, json.dumps(state.steps), json.dumps(state.pending), error, finished, org, run_id))
        async with await self._store()._connect() as connection, connection.transaction():
            if finished:
                await connection.execute("DELETE FROM automation_work_queue WHERE organization_id=%s AND run_id=%s", (org, run_id))
            else:
                await connection.execute(
                    "UPDATE automation_work_queue SET available_at=%s,lease_owner=NULL,lease_expires_at=NULL WHERE organization_id=%s AND run_id=%s",
                    (state.resume_at or datetime.now(UTC), org, run_id))
        return status

    async def tick(self, worker: str, budget_seconds: float = 45) -> dict[str, Any]:
        deadline = time.monotonic() + budget_seconds
        fired = 0
        for trigger in await self._claim_triggers(worker):
            try:
                fired += await self._fire_trigger(trigger)
            except Exception:  # noqa: BLE001 - one tenant's failure must not block the others
                continue
        processed: list[str] = []
        while time.monotonic() < deadline:
            claimed = await self._claim_run(worker)
            if not claimed:
                break
            processed.append(await self._process_run(claimed, deadline))
        return {"runs_created": fired, "runs_processed": len(processed), "statuses": processed}


# ---------------------------------------------------------------- routes

# Kiara Automation is in early access: only the system administrator manages flows.
Admin = Annotated[RequestContext, Depends(system_administrator_context)]
Member = Annotated[RequestContext, Depends(authenticated_context)]


def create_automation_router(repository: AutomationRepository) -> APIRouter:
    router = APIRouter(tags=["automation"])

    @router.get("/v1/automation/flows")
    async def flows(context: Admin) -> dict[str, Any]:
        return {"items": await repository.list_flows(context.organization_id)}

    @router.put("/v1/automation/flows/{client_key}")
    async def save(client_key: str, payload: FlowSave, context: Admin) -> dict[str, Any]:
        return await repository.save_flow(context, client_key, payload)

    @router.delete("/v1/automation/flows/{client_key}", status_code=204)
    async def delete(client_key: str, context: Admin) -> None:
        await repository.delete_flow(context, client_key)

    @router.post("/v1/automation/flows/{client_key}/run", status_code=202)
    async def run(client_key: str, context: Admin) -> dict[str, Any]:
        return await repository.enqueue_manual(context, client_key)

    @router.get("/v1/automation/runs")
    async def runs(context: Admin, flow: Annotated[str | None, Query(max_length=80)] = None) -> dict[str, Any]:
        return {"items": await repository.list_runs(context.organization_id, flow)}

    @router.post("/v1/automation/internal/tick")
    async def tick(request: Request) -> dict[str, Any]:
        expected = os.getenv("KIARA_WORKER_TOKEN") or os.getenv("CRON_SECRET")
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            raise ApiError(401, "worker_unauthorized", "Worker não autorizado.")
        return await repository.tick(request.state.correlation_id)

    @router.get("/v1/approvals")
    async def approvals(context: Member, status: Annotated[Literal["pending", "history"], Query()] = "pending") -> dict[str, Any]:
        return await repository.list_requests(context.organization_id, status)

    @router.post("/v1/approvals/{request_id}/decision")
    async def decide(request_id: str, payload: Decision, context: Member) -> dict[str, Any]:
        return await repository.decide(context, request_id, payload)

    return router
