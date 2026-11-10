"""Tenant-scoped ingestion, qualification and durable delivery for the shared inbox."""
from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import os
import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .adapters.postgres import PostgresRepository, _uuid
from .commercial_qualification import qualify_messages
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError


def normalize_phone(value: str) -> str:
    digits = "".join(c for c in value if c.isdigit())
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValueError("Telefone internacional inválido.")
    return digits


async def refresh_qualification(connection, organization_uuid, thread_id, consumer_id):
    messages = await (await connection.execute(
        "SELECT direction,body FROM messages WHERE organization_id=%s AND thread_id=%s ORDER BY sent_at DESC,id DESC LIMIT 80",
        (organization_uuid, thread_id),
    )).fetchall()
    assessment = qualify_messages(list(reversed(messages)))
    await connection.execute(
        """INSERT INTO qualifications(organization_id,thread_id,score,temperature,recommendation,reasons,confidence)
           VALUES(%s,%s,%s,%s,%s,%s,%s)""",
        (organization_uuid, thread_id, assessment["score"], assessment["temperature"],
         assessment["recommendation"], Jsonb(assessment["reasons"]), assessment["confidence"]),
    )
    await connection.execute(
        """UPDATE consumers SET attributes=attributes || jsonb_build_object('qualification',%s::jsonb),
           consent_status=CASE WHEN %s THEN 'opted_out' ELSE consent_status END,updated_at=now()
           WHERE organization_id=%s AND id=%s""",
        (Jsonb(assessment), assessment["optout"], organization_uuid, consumer_id),
    )
    await connection.execute(
        """UPDATE pipeline_entries SET stage=CASE WHEN stage IN ('won','lost') THEN stage ELSE %s END,
           next_action=CASE WHEN stage IN ('won','lost') THEN next_action ELSE %s END,
           version=version+1,updated_at=now() WHERE organization_id=%s AND consumer_id=%s""",
        (assessment["stage"], assessment["recommendation"], organization_uuid, consumer_id),
    )
    if assessment["optout"] or assessment["handoff"]:
        await connection.execute(
            "UPDATE conversation_threads SET handoff=true,automation_enabled=false,status=CASE WHEN %s THEN 'blocked' ELSE status END WHERE organization_id=%s AND id=%s",
            (assessment["optout"], organization_uuid, thread_id),
        )
        thread = await (await connection.execute("SELECT channel,provider_thread_id FROM conversation_threads WHERE organization_id=%s AND id=%s", (organization_uuid, thread_id))).fetchone()
        if thread and thread["channel"] == "whatsapp":
            row = await (await connection.execute("SELECT config FROM whatsapp_web_config WHERE organization_id=%s FOR UPDATE", (organization_uuid,))).fetchone()
            if row:
                config = row["config"]
                for contact in config.get("contacts", []):
                    if contact["phone"] == thread["provider_thread_id"]:
                        contact["handoff"] = True
                await connection.execute("UPDATE whatsapp_web_config SET config=%s,updated_at=now() WHERE organization_id=%s", (Jsonb(config), organization_uuid))
    return assessment


async def ingest_message(connection, organization_id: str, *, channel: str, identity: str,
                         external_id: str, text: str, occurred_at: datetime,
                         direction: str, name: str = "", metadata: dict | None = None):
    org = _uuid("organization", organization_id)
    if channel not in {"whatsapp", "instagram", "chatwoot", "email", "facebook"}:
        raise ValueError("Canal inválido.")
    phone = normalize_phone(identity) if channel == "whatsapp" else ""
    identity = phone or identity[:200]
    provider_id = hashlib.sha256(f"{channel}:{identity}:{external_id}".encode()).hexdigest()
    await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                             (f"{organization_id}:{channel}:{identity}",))
    existing = await (await connection.execute(
        """SELECT c.id,c.consent_status FROM consumers c LEFT JOIN conversation_threads t
           ON t.organization_id=c.organization_id AND t.consumer_id=c.id
           WHERE c.organization_id=%s AND ((%s<>'' AND
             (c.attributes->'whatsapp'->>'phone'=%s OR c.attributes->'hunter'->>'phone'=%s OR c.attributes->>'phone'=%s))
             OR (t.channel=%s AND t.provider_thread_id=%s)) LIMIT 1""",
        (org, phone, phone, phone, phone, channel, identity),
    )).fetchone()
    attributes = {"phone": phone, "hunter": {"phone": phone, "source": channel,
                  "whatsapp_url": f"https://wa.me/{phone}"}} if phone else {}
    if phone:
        attributes["whatsapp"] = {"phone": phone}
    if existing:
        consumer_id = existing["id"]
    else:
        row = await (await connection.execute(
            "INSERT INTO consumers(organization_id,display_name,consent_status,attributes) VALUES(%s,%s,%s,%s) RETURNING id",
            (org, name or phone or f"Contato {channel}", "observed_inbound" if direction == "inbound" else "unknown", Jsonb(attributes)),
        )).fetchone()
        consumer_id = row["id"]
    automation_enabled = handoff = False
    if phone:
        saved = await (await connection.execute("SELECT config FROM whatsapp_web_config WHERE organization_id=%s", (org,))).fetchone()
        config = saved["config"] if saved else {}
        contact = next((item for item in config.get("contacts", []) if item["phone"] == phone), {})
        handoff = bool(contact.get("handoff"))
        automation_enabled = bool(config.get("enabled") and config.get("auto_reply_enabled", True) and contact.get("enabled") and not handoff
                                  and not (existing and existing.get("consent_status") in {"opted_out", "revoked"}))
    await connection.execute(
        "INSERT INTO pipeline_entries(organization_id,consumer_id) VALUES(%s,%s) ON CONFLICT(organization_id,consumer_id) DO NOTHING",
        (org, consumer_id),
    )
    thread = await (await connection.execute(
        """INSERT INTO conversation_threads(organization_id,consumer_id,channel,provider_thread_id,last_message_at,metadata,automation_enabled,handoff)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(organization_id,channel,provider_thread_id)
           DO UPDATE SET last_message_at=GREATEST(conversation_threads.last_message_at,EXCLUDED.last_message_at),updated_at=now()
           RETURNING id""", (org, consumer_id, channel, identity, occurred_at, Jsonb(metadata or {}), automation_enabled, handoff),
    )).fetchone()
    inserted = await (await connection.execute(
        """INSERT INTO messages(organization_id,thread_id,direction,provider_message_id,body,sent_at)
           VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
        (org, thread["id"], direction, provider_id, text[:10000], occurred_at),
    )).fetchone()
    if inserted:
        await refresh_qualification(connection, org, thread["id"], consumer_id)
        if direction == "inbound":
            await connection.execute(
                "UPDATE commercial_outbox SET status='cancelled',updated_at=now() WHERE organization_id=%s AND thread_id=%s AND status='queued'",
                (org, thread["id"]),
            )
    return {"thread_id": str(thread["id"]), "consumer_id": str(consumer_id), "inserted": bool(inserted)}


class InboxReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=160)


class AutomationChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class OutboxCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["sent", "unknown", "failed"]
    provider_message_id: str | None = Field(default=None, max_length=300)


class UnifiedInboxRepository:
    def __init__(self, postgres: PostgresRepository, integrations=None):
        self.postgres = postgres
        self.integrations = integrations

    async def mark_read(self, organization_id: str, thread_id: str):
        async with self.postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                "UPDATE conversation_threads SET last_read_at=now() WHERE organization_id=%s AND id=%s RETURNING id",
                (_uuid("organization", organization_id), _uuid("thread", thread_id)),
            )).fetchone()
            if not row:
                raise ApiError(404, "thread_not_found", "Conversa não encontrada.")
        return {"read": True}

    async def reply(self, organization_id: str, thread_id: str, payload: InboxReply):
        if not payload.text.strip():
            raise ApiError(422, "empty_message", "Escreva a mensagem.")
        org, thread_uuid = _uuid("organization", organization_id), _uuid("thread", thread_id)
        async with self.postgres._transaction(organization_id) as connection:
            await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"{organization_id}:outbox:{payload.idempotency_key}",))
            thread = await (await connection.execute(
                "SELECT t.*,c.consent_status FROM conversation_threads t JOIN consumers c ON c.organization_id=t.organization_id AND c.id=t.consumer_id WHERE t.organization_id=%s AND t.id=%s FOR UPDATE OF t",
                (org, thread_uuid),
            )).fetchone()
            if not thread:
                raise ApiError(404, "thread_not_found", "Conversa não encontrada.")
            if thread["status"] == "blocked" or thread["consent_status"] in {"opted_out", "revoked"}:
                raise ApiError(409, "contact_blocked", "Este contato não pode receber mensagens.")
            if thread["channel"] not in {"whatsapp", "instagram", "chatwoot"} or (thread["channel"] != "whatsapp" and self.integrations is None):
                raise ApiError(409, "channel_delivery_not_connected", "Configure a entrega deste canal antes de enviar pela caixa unificada.")
            previous = await (await connection.execute(
                "SELECT id,status,body,thread_id FROM commercial_outbox WHERE organization_id=%s AND request_key=%s",
                (org, payload.idempotency_key),
            )).fetchone()
            if previous:
                if str(previous["thread_id"]) != str(thread_uuid) or previous["body"] != payload.text:
                    raise ApiError(409, "idempotency_conflict", "Chave já usada para outra mensagem.")
                return {"id": str(previous["id"]), "status": previous["status"]}
            row = await (await connection.execute(
                "INSERT INTO commercial_outbox(organization_id,thread_id,phone,body,request_key) VALUES(%s,%s,%s,%s,%s) RETURNING id,status",
                (org, thread_uuid, normalize_phone(thread["provider_thread_id"]) if thread["channel"] == "whatsapp" else thread["provider_thread_id"], payload.text, payload.idempotency_key),
            )).fetchone()
            await self._automation(connection, org, thread, enabled=False)
            if thread["channel"] == "whatsapp":
                return {"id": str(row["id"]), "status": row["status"]}
            await connection.execute("UPDATE commercial_outbox SET status='sending',lease_until=now()+interval '2 minutes' WHERE organization_id=%s AND id=%s", (org, row["id"]))
        # Reservation commits before any external POST, so uncertain outcomes cannot
        # cause a retry merely because a DB transaction was rolled back.
        receipt = None
        status = "unknown"
        try:
            credentials = await self.integrations.credentials_for(organization_id, thread["channel"])
            if not credentials:
                status = "failed"
            elif thread["channel"] == "chatwoot":
                from .chatwoot import _runtime_client
                result = await _runtime_client(credentials).send_message(int(thread["provider_thread_id"]), payload.text)
                receipt = str(result["id"])
            else:
                receipt = await asyncio.to_thread(self._instagram_send, credentials, thread, payload.text)
            if receipt:
                status = "sent"
        except (ValueError, TypeError, RuntimeError, OSError, KeyError, http.client.HTTPException):
            pass
        async with self.postgres._transaction(organization_id) as connection:
            await connection.execute("UPDATE commercial_outbox SET status=%s,provider_message_id=%s,lease_until=NULL,updated_at=now() WHERE organization_id=%s AND id=%s", (status, receipt, org, row["id"]))
            if status == "sent":
                await ingest_message(connection, organization_id, channel=thread["channel"], identity=thread["provider_thread_id"], external_id=receipt, text=payload.text, occurred_at=datetime.now(UTC), direction="outbound", metadata=thread.get("metadata") or {})
        return {"id": str(row["id"]), "status": status}

    @staticmethod
    def _instagram_send(credentials, thread, text):
        version = os.getenv("KIARA_INSTAGRAM_GRAPH_VERSION", "")
        if not re.fullmatch(r"v\d{1,2}\.\d", version):
            raise RuntimeError("Versão Graph API não configurada.")
        peer = (thread.get("metadata") or {}).get("recipient_id")
        account = credentials["instagram_account_id"]
        if not str(peer or "").isdigit() or not account.isdigit():
            raise ValueError("Destinatário Instagram inválido.")
        connection = http.client.HTTPSConnection("graph.instagram.com", timeout=15)
        try:
            connection.request("POST", f"/{version}/{account}/messages", body=json.dumps({"recipient": {"id": peer}, "message": {"text": text}}).encode(), headers={"Authorization": "Bearer " + credentials["access_token"], "Content-Type": "application/json"})
            with connection.getresponse() as response:
                raw = response.read(100001)
                if not 200 <= response.status < 300 or len(raw) > 100000:
                    raise RuntimeError("Envio Instagram não confirmado.")
            identifier = json.loads(raw).get("message_id")
            if not isinstance(identifier, str) or not identifier:
                raise RuntimeError("Recibo Instagram ausente.")
            return identifier
        finally:
            connection.close()

    async def _automation(self, connection, org, thread, *, enabled: bool):
        if enabled and thread["status"] == "blocked":
            raise ApiError(409, "contact_blocked", "Pedido de interrupção impede retomar automação.")
        if enabled:
            if thread["channel"] != "whatsapp":
                raise ApiError(409, "channel_automation_unavailable", "Automação deste canal ainda não foi conectada.")
            row = await (await connection.execute("SELECT config FROM whatsapp_web_config WHERE organization_id=%s", (org,))).fetchone()
            config = row["config"] if row else {}
            if not config.get("enabled") or not config.get("auto_reply_enabled", True) or not any(c["phone"] == thread["provider_thread_id"] and c.get("enabled") for c in config.get("contacts", [])):
                raise ApiError(409, "automation_not_configured", "Habilite esta operação e contato nas configurações do WhatsApp.")
        await connection.execute(
            "UPDATE conversation_threads SET automation_enabled=%s,handoff=%s,updated_at=now() WHERE organization_id=%s AND id=%s",
            (enabled, not enabled, org, thread["id"]),
        )
        if thread["channel"] == "whatsapp":
            row = await (await connection.execute("SELECT config FROM whatsapp_web_config WHERE organization_id=%s FOR UPDATE", (org,))).fetchone()
            if row:
                config = row["config"]
                for contact in config.get("contacts", []):
                    if contact["phone"] == thread["provider_thread_id"]:
                        contact["handoff"] = not enabled
                await connection.execute("UPDATE whatsapp_web_config SET config=%s,updated_at=now() WHERE organization_id=%s", (Jsonb(config), org))

    async def automation(self, organization_id: str, thread_id: str, enabled: bool):
        org = _uuid("organization", organization_id)
        async with self.postgres._transaction(organization_id) as connection:
            thread = await (await connection.execute("SELECT * FROM conversation_threads WHERE organization_id=%s AND id=%s FOR UPDATE", (org, _uuid("thread", thread_id)))).fetchone()
            if not thread:
                raise ApiError(404, "thread_not_found", "Conversa não encontrada.")
            await self._automation(connection, org, thread, enabled=enabled)
        return {"automation_enabled": enabled, "handoff": not enabled}

    async def next_outbound(self, organization_id: str):
        org = _uuid("organization", organization_id)
        async with self.postgres._transaction(organization_id) as connection:
            await connection.execute("UPDATE commercial_outbox SET status='unknown',updated_at=now() WHERE organization_id=%s AND status='sending' AND lease_until<now()", (org,))
            row = await (await connection.execute(
                """SELECT o.* FROM commercial_outbox o JOIN conversation_threads t ON t.organization_id=o.organization_id AND t.id=o.thread_id
                   JOIN consumers c ON c.organization_id=t.organization_id AND c.id=t.consumer_id
                   WHERE o.organization_id=%s AND o.status='queued' AND t.status!='blocked' AND t.channel='whatsapp'
                   AND c.lifecycle_status='active' AND c.consent_status NOT IN ('opted_out','revoked')
                   ORDER BY o.created_at LIMIT 1 FOR UPDATE OF o SKIP LOCKED""", (org,),
            )).fetchone()
            if not row:
                return None
            await connection.execute("UPDATE commercial_outbox SET status='sending',lease_until=now()+interval '2 minutes',updated_at=now() WHERE organization_id=%s AND id=%s", (org, row["id"]))
            return {"id": str(row["id"]), "phone": row["phone"], "text": row["body"], "kind": "manual", "expected_ids": []}

    async def complete_outbound(self, organization_id: str, identifier: str, payload: OutboxCompletion):
        org = _uuid("organization", organization_id)
        async with self.postgres._transaction(organization_id) as connection:
            row = await (await connection.execute("SELECT * FROM commercial_outbox WHERE organization_id=%s AND id=%s FOR UPDATE", (org, _uuid("outbound", identifier)))).fetchone()
            if not row:
                raise ApiError(404, "outbound_not_found", "Mensagem não encontrada.")
            if row["status"] in {"sent", "unknown", "failed", "cancelled"}:
                return {"status": row["status"]}
            if row["status"] != "sending":
                raise ApiError(409, "outbound_not_claimed", "Mensagem não reservada pelo executor.")
            status = payload.status if payload.status != "sent" or payload.provider_message_id else "unknown"
            await connection.execute("UPDATE commercial_outbox SET status=%s,provider_message_id=%s,updated_at=now(),lease_until=NULL WHERE organization_id=%s AND id=%s", (status, payload.provider_message_id, org, row["id"]))
            if status == "sent":
                await ingest_message(connection, organization_id, channel="whatsapp", identity=row["phone"], external_id=payload.provider_message_id, text=row["body"], occurred_at=datetime.now(UTC), direction="outbound")
            return {"status": status}


def create_unified_inbox_router(repository: UnifiedInboxRepository):
    router = APIRouter(tags=["unified-inbox"])
    def writable(context, *, sending=False):
        if context.role not in ({"owner", "admin"} if sending else {"owner", "admin", "operator"}):
            raise ApiError(403, "inbox_forbidden", "Seu perfil permite apenas leitura.")

    @router.post("/v1/inbox/threads/{thread_id}/read")
    async def mark_read(thread_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        return await repository.mark_read(context.organization_id, thread_id)

    @router.post("/v1/inbox/threads/{thread_id}/messages")
    async def reply(thread_id: str, payload: InboxReply, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context, sending=True)
        return await repository.reply(context.organization_id, thread_id, payload)

    @router.patch("/v1/inbox/threads/{thread_id}/automation")
    async def automation(thread_id: str, payload: AutomationChange, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context, sending=payload.enabled)
        return await repository.automation(context.organization_id, thread_id, payload.enabled)

    @router.get("/v1/whatsapp-web/outbox/next")
    async def next_outbound(context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context, sending=True)
        return await repository.next_outbound(context.organization_id)

    @router.post("/v1/whatsapp-web/outbox/{identifier}/complete")
    async def complete(identifier: str, payload: OutboxCompletion, context: Annotated[RequestContext, Depends(authenticated_context)]):
        writable(context, sending=True)
        return await repository.complete_outbound(context.organization_id, identifier, payload)

    return router
