from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError


class Contact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(pattern=r"^[1-9][0-9]{7,14}$")
    name: str = Field(default="", max_length=160)
    enabled: bool = True
    handoff: bool = False


class WhatsAppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pilot_mode: bool = True
    pilot_consent_confirmed: bool = False
    enabled: bool = False
    auto_reply_enabled: bool = True
    followup_enabled: bool = False
    daily_limit: int = Field(default=50, ge=1, le=500)
    initial_outreach_enabled: bool = False
    outreach_template: str = Field(default="Olá {name}! Posso apresentar como podemos ajudar?", min_length=1, max_length=4000)
    ai_context: str = Field(default="", max_length=6000)
    reply_template: str = Field(default="Olá {name}! Recebemos sua mensagem. Como podemos ajudar?", min_length=1, max_length=4000)
    followup_template: str = Field(default="Olá {name}! Podemos ajudar com mais alguma informação?", min_length=1, max_length=4000)
    followup_hours: int = Field(default=24, ge=1, le=720)
    contact_start: str = Field(default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    contact_end: str = Field(default="18:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    contacts: list[Contact] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_contacts(self):
        if len({c.phone for c in self.contacts}) != len(self.contacts):
            raise ValueError("Contatos duplicados.")
        enabled_contacts = sum(contact.enabled for contact in self.contacts)
        if self.pilot_mode and enabled_contacts > 1:
            raise ValueError("O piloto permite habilitar somente um contato por vez.")
        if self.enabled and enabled_contacts < 1:
            raise ValueError("Habilite ao menos um contato autorizado para iniciar a operação.")
        if self.enabled and not self.pilot_consent_confirmed:
            raise ValueError("Confirme que o contato autorizou o teste antes de habilitar a automação.")
        if self.enabled and not self.ai_context.strip():
            raise ValueError("Informe as informações autorizadas da empresa antes de habilitar a automação.")
        if self.contact_start >= self.contact_end:
            raise ValueError("O horário final deve ser posterior ao inicial.")
        return self


class WhatsAppEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9._:~-]+$")
    phone: str = Field(default="", pattern=r"^(?:[1-9][0-9]{7,14})?$")
    kind: Literal["inbound", "outbound", "outbound_observed", "heartbeat", "error", "unknown", "handoff", "followup", "cancelled"]
    text: str = Field(default="", max_length=10000)
    occurred_at: datetime
    status: str = Field(default="", max_length=80)
    external_message_id: str | None = Field(default=None, max_length=300)
    conversation_id: str | None = Field(default=None, max_length=160)
    direction: Literal["in", "out", "inbound", "outbound"] | None = None

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Informe o fuso horário.")
        return value.astimezone(UTC)


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[WhatsAppEvent] = Field(min_length=1, max_length=100)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=30, ge=1, le=30)


class AnalysisLead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(pattern=r"^[1-9][0-9]{7,14}$")
    name: str = Field(min_length=1, max_length=160)
    stage: Literal["new", "qualified", "contacted", "opportunity", "won", "lost"] = "new"
    summary: str = Field(default="", max_length=2000)
    next_action: str = Field(default="", max_length=300)
    confidence: float = Field(ge=0, le=1)


class AnalysisCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leads: list[AnalysisLead] = Field(default_factory=list, max_length=30)
    scanned: int = Field(default=0, ge=0, le=30)
    skipped: int = Field(default=0, ge=0, le=30)
    error: str | None = Field(default=None, max_length=500)


def writable(context: RequestContext):
    if context.role not in {"owner", "admin", "operator"}:
        raise ApiError(403, "whatsapp_forbidden", "Seu perfil permite apenas consultar o atendimento.")


class WhatsAppWebRepository:
    def __init__(self, postgres: PostgresRepository | None = None):
        self.postgres = postgres
        self.configs = {}
        self.events = {}
        self.analysis_jobs = {}

    async def config(self, organization_id: str):
        if self.postgres is None:
            return self.configs.get(organization_id, WhatsAppConfig().model_dump())
        async with self.postgres._transaction(organization_id) as connection:
            row = await (await connection.execute("SELECT config FROM whatsapp_web_config WHERE organization_id=%s", (_uuid("organization", organization_id),))).fetchone()
        return WhatsAppConfig.model_validate(row["config"]).model_dump() if row else WhatsAppConfig().model_dump()

    async def save_config(self, organization_id: str, config: WhatsAppConfig):
        data = config.model_dump()
        if self.postgres is None:
            self.configs[organization_id] = data
        else:
            async with self.postgres._transaction(organization_id) as connection:
                await connection.execute("INSERT INTO whatsapp_web_config(organization_id,config) VALUES(%s,%s) ON CONFLICT(organization_id) DO UPDATE SET config=EXCLUDED.config,updated_at=now()", (_uuid("organization", organization_id), Jsonb(data)))
                for contact in config.contacts:
                    await connection.execute("UPDATE conversation_threads SET automation_enabled=%s,handoff=%s,updated_at=now() WHERE organization_id=%s AND channel='whatsapp' AND provider_thread_id=%s AND status!='blocked'", (config.enabled and config.auto_reply_enabled and contact.enabled and not contact.handoff, contact.handoff, _uuid("organization", organization_id), contact.phone))
        return data

    async def ingest(self, organization_id: str, batch: EventBatch):
        accepted = 0
        now = datetime.now(UTC).isoformat()
        if self.postgres is None:
            events = self.events.setdefault(organization_id, {})
            for event in batch.events:
                if event.id not in events:
                    events[event.id] = {**event.model_dump(mode="json"), "received_at": now}
                    accepted += 1
        else:
            async with self.postgres._transaction(organization_id) as connection:
                for event in batch.events:
                    kind = "outbound" if event.kind == "outbound_observed" else event.kind
                    cursor = await connection.execute("INSERT INTO whatsapp_web_events(organization_id,id,phone,kind,text,occurred_at,status) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(organization_id,id) DO NOTHING RETURNING id", (_uuid("organization", organization_id), event.id, event.phone, kind, event.text, event.occurred_at, event.status))
                    inserted = await cursor.fetchone() is not None
                    accepted += int(inserted)
                    message_direction = kind if kind in {"inbound", "outbound"} else (
                        "outbound" if event.direction in {"out", "outbound"} and event.external_message_id else
                        "inbound" if event.direction in {"in", "inbound"} and event.external_message_id else None)
                    if inserted and event.phone and message_direction and event.status not in {"pending", "queued", "unknown", "failed"}:
                        from .unified_inbox import ingest_message
                        await ingest_message(connection, organization_id, channel="whatsapp", identity=event.phone,
                                             external_id=event.external_message_id or event.id, text=event.text,
                                             occurred_at=event.occurred_at, direction=message_direction)
                    if inserted and event.phone and event.kind == "handoff":
                        await connection.execute("UPDATE conversation_threads SET handoff=true,automation_enabled=false,updated_at=now() WHERE organization_id=%s AND channel='whatsapp' AND provider_thread_id=%s", (_uuid("organization", organization_id), event.phone))
                        row = await (await connection.execute("SELECT config FROM whatsapp_web_config WHERE organization_id=%s FOR UPDATE", (_uuid("organization", organization_id),))).fetchone()
                        if row:
                            config = row["config"]
                            for contact in config.get("contacts", []):
                                if contact["phone"] == event.phone:
                                    contact["handoff"] = True
                            await connection.execute("UPDATE whatsapp_web_config SET config=%s,updated_at=now() WHERE organization_id=%s", (Jsonb(config), _uuid("organization", organization_id)))
        return {"accepted": accepted, "duplicates": len(batch.events) - accepted}

    async def history(self, organization_id: str, limit: int = 100):
        if self.postgres is None:
            all_items = list(self.events.get(organization_id, {}).values())
            heartbeat = max((e["received_at"] for e in all_items if e["kind"] == "heartbeat"), default=None)
            items = sorted(all_items, key=lambda e: (e["received_at"], e["id"]), reverse=True)[:limit]
        else:
            async with self.postgres._transaction(organization_id) as connection:
                items = await (await connection.execute("SELECT id,phone,kind,text,occurred_at,status,received_at FROM whatsapp_web_events WHERE organization_id=%s ORDER BY received_at DESC,id DESC LIMIT %s", (_uuid("organization", organization_id), limit))).fetchall()
                row = await (await connection.execute("SELECT max(received_at) AS heartbeat FROM whatsapp_web_events WHERE organization_id=%s AND kind='heartbeat'", (_uuid("organization", organization_id),))).fetchone()
            heartbeat = row["heartbeat"].isoformat() if row["heartbeat"] else None
            items = [{**item, "occurred_at": item["occurred_at"].isoformat(), "received_at": item["received_at"].isoformat()} for item in items]
        online = heartbeat is not None and (datetime.now(UTC) - datetime.fromisoformat(heartbeat)).total_seconds() <= 120
        return {"items": items, "last_heartbeat_at": heartbeat, "online": online}

    async def request_analysis(self, organization_id: str, limit: int):
        if self.postgres is None:
            current = self.analysis_jobs.get(organization_id)
            if current and current["status"] in {"queued", "running"}:
                return current
            job = {"id": str(uuid4()), "status": "queued", "limit": limit, "result": None}
            self.analysis_jobs[organization_id] = job
            return job
        async with self.postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT id,status,result FROM whatsapp_web_analysis_jobs
                   WHERE organization_id=%s AND status IN ('queued','running')
                   ORDER BY created_at LIMIT 1 FOR UPDATE""",
                (_uuid("organization", organization_id),),
            )).fetchone()
            if row:
                return {"id": str(row["id"]), "status": row["status"], "result": row["result"] or None}
            row = await (await connection.execute(
                """INSERT INTO whatsapp_web_analysis_jobs (organization_id,result)
                   VALUES (%s,%s)
                   ON CONFLICT (organization_id) WHERE status IN ('queued','running') DO NOTHING
                   RETURNING id,status,result""",
                (_uuid("organization", organization_id), Jsonb({"limit": limit})),
            )).fetchone()
            if not row:
                row = await (await connection.execute(
                    """SELECT id,status,result FROM whatsapp_web_analysis_jobs
                       WHERE organization_id=%s AND status IN ('queued','running')
                       ORDER BY created_at LIMIT 1""",
                    (_uuid("organization", organization_id),),
                )).fetchone()
            return {"id": str(row["id"]), "status": row["status"], "result": None}

    async def next_analysis(self, organization_id: str):
        if self.postgres is None:
            job = self.analysis_jobs.get(organization_id)
            if not job or job["status"] != "queued":
                return None
            job["status"] = "running"
            return job
        async with self.postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT id,result FROM whatsapp_web_analysis_jobs
                   WHERE organization_id=%s
                     AND (status='queued' OR (status='running' AND lease_until < now()))
                   ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED""",
                (_uuid("organization", organization_id),),
            )).fetchone()
            if not row:
                return None
            await connection.execute(
                """UPDATE whatsapp_web_analysis_jobs
                   SET status='running',lease_until=now()+interval '45 minutes',updated_at=now()
                   WHERE organization_id=%s AND id=%s""",
                (_uuid("organization", organization_id), row["id"]),
            )
            return {"id": str(row["id"]), "status": "running", **(row["result"] or {})}

    async def analysis_status(self, organization_id: str, job_id: str):
        if self.postgres is None:
            job = self.analysis_jobs.get(organization_id)
            if not job or job["id"] != job_id:
                raise ApiError(404, "whatsapp_analysis_not_found", "Análise não encontrada.")
            return job
        async with self.postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT id,status,result FROM whatsapp_web_analysis_jobs
                   WHERE organization_id=%s AND id=%s""",
                (_uuid("organization", organization_id), _uuid("whatsapp_analysis", job_id)),
            )).fetchone()
        if not row:
            raise ApiError(404, "whatsapp_analysis_not_found", "Análise não encontrada.")
        return {"id": str(row["id"]), "status": row["status"], "result": row["result"] or None}

    async def complete_analysis(self, organization_id: str, job_id: str, payload: AnalysisCompletion):
        if self.postgres is None:
            job = self.analysis_jobs.get(organization_id)
            if not job or job["id"] != job_id:
                raise ApiError(404, "whatsapp_analysis_not_found", "Análise não encontrada.")
            if job["status"] in {"completed", "failed"}:
                return job["result"]
            result = {"imported": 0 if payload.error else len(payload.leads), "duplicates": 0,
                      "scanned": payload.scanned, "skipped": payload.skipped, "error": payload.error}
            job.update(status="failed" if payload.error else "completed", result=result)
            return result

        organization_uuid = _uuid("organization", organization_id)
        async with self.postgres._transaction(organization_id) as connection:
            job = await (await connection.execute(
                """SELECT status FROM whatsapp_web_analysis_jobs
                   WHERE organization_id=%s AND id=%s FOR UPDATE""",
                (organization_uuid, _uuid("whatsapp_analysis", job_id)),
            )).fetchone()
            if not job:
                raise ApiError(404, "whatsapp_analysis_not_found", "Análise não encontrada.")
            if job["status"] in {"completed", "failed"}:
                row = await (await connection.execute(
                    "SELECT result FROM whatsapp_web_analysis_jobs WHERE organization_id=%s AND id=%s",
                    (organization_uuid, _uuid("whatsapp_analysis", job_id)),
                )).fetchone()
                return row["result"]

            imported = duplicates = 0
            for lead in ([] if payload.error else payload.leads):
                phone = lead.phone
                existing = await (await connection.execute(
                    """SELECT id FROM consumers
                       WHERE organization_id=%s AND
                         (attributes->'whatsapp'->>'phone'=%s
                          OR attributes->'hunter'->>'phone'=%s
                          OR attributes->>'phone'=%s)
                       LIMIT 1""",
                    (organization_uuid, phone, phone, phone),
                )).fetchone()
                if existing:
                    duplicates += 1
                    await connection.execute(
                        """UPDATE consumers SET attributes=attributes || jsonb_build_object('whatsapp',
                           COALESCE(attributes->'whatsapp','{}'::jsonb) || %s::jsonb),updated_at=now()
                           WHERE organization_id=%s AND id=%s""",
                        (Jsonb({"phone": phone, "summary": lead.summary, "confidence": lead.confidence,
                                "analyzed_at": datetime.now(UTC).isoformat()}), organization_uuid, existing["id"]),
                    )
                    await connection.execute(
                        """UPDATE pipeline_entries SET stage=CASE WHEN stage IN ('won','lost') THEN stage ELSE %s END,
                           next_action=CASE WHEN stage IN ('won','lost') THEN next_action ELSE %s END,
                           version=version+1,updated_at=now() WHERE organization_id=%s AND consumer_id=%s""",
                        (lead.stage, lead.next_action or None, organization_uuid, existing["id"]),
                    )
                    continue

                whatsapp = {
                    "phone": phone,
                    "summary": lead.summary,
                    "confidence": lead.confidence,
                    "analyzed_at": datetime.now(UTC).isoformat(),
                }
                hunter = {
                    "phone": phone,
                    "whatsapp_url": f"https://wa.me/{phone}",
                    "source": "whatsapp_web",
                }
                notes = "Análise do WhatsApp: " + (lead.summary or "Conversa revisada pela Kiara.")
                consumer = await (await connection.execute(
                    """INSERT INTO consumers
                       (organization_id,display_name,consent_status,attributes)
                       VALUES (%s,%s,'observed_inbound',%s)
                       ON CONFLICT DO NOTHING RETURNING id""",
                    (organization_uuid, lead.name, Jsonb({"whatsapp": whatsapp, "hunter": hunter, "notes": notes})),
                )).fetchone()
                if not consumer:
                    duplicates += 1
                    continue
                await connection.execute(
                    """INSERT INTO pipeline_entries
                       (organization_id,consumer_id,stage,next_action)
                       VALUES (%s,%s,%s,%s)""",
                    (organization_uuid, consumer["id"], lead.stage, lead.next_action or None),
                )
                imported += 1

            result = {"imported": imported, "duplicates": duplicates,
                      "scanned": payload.scanned, "skipped": payload.skipped, "error": payload.error}
            await connection.execute(
                """UPDATE whatsapp_web_analysis_jobs
                   SET status=%s,result=%s,lease_until=NULL,updated_at=now()
                   WHERE organization_id=%s AND id=%s""",
                ("failed" if payload.error else "completed", Jsonb(result), organization_uuid, _uuid("whatsapp_analysis", job_id)),
            )
            return result


def create_whatsapp_web_router(repository: WhatsAppWebRepository):
    router = APIRouter(prefix="/v1/whatsapp-web", tags=["whatsapp-web"])

    @router.get("/config")
    async def get_config(context: Annotated[RequestContext, Depends(authenticated_context)]):
        return await repository.config(context.organization_id)

    @router.put("/config")
    async def put_config(payload: WhatsAppConfig, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context)
        if payload.enabled and context.role not in {"owner", "admin"}:
            raise ApiError(403, "outbound_approval_required", "Somente owner/admin pode ativar respostas autônomas.")
        return await repository.save_config(context.organization_id, payload)

    @router.post("/events")
    async def post_events(payload: EventBatch, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context)
        return await repository.ingest(context.organization_id, payload)

    @router.get("/events")
    async def get_events(context: Annotated[RequestContext, Depends(authenticated_context)], limit: int = Query(default=100, ge=1, le=500)):
        return await repository.history(context.organization_id, limit)

    @router.post("/analysis")
    async def request_analysis(payload: AnalysisRequest, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context)
        return await repository.request_analysis(context.organization_id, payload.limit)

    @router.get("/analysis/next")
    async def next_analysis(context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context)
        return await repository.next_analysis(context.organization_id)

    @router.get("/analysis/{job_id}")
    async def analysis_status(job_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context)
        return await repository.analysis_status(context.organization_id, job_id)

    @router.post("/analysis/{job_id}/complete")
    async def complete_analysis(job_id: str, payload: AnalysisCompletion,
                                context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context)
        return await repository.complete_analysis(context.organization_id, job_id, payload)

    return router
