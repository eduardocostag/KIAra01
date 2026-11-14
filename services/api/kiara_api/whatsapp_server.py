"""WhatsApp on the always-on Debian server: OpenWA behind the Kiara gateway.

Connects the session by QR and copies recent one-to-one conversations into the unified inbox.
Read-only towards WhatsApp: nothing here sends messages, and imported history never triggers
automations (only an operator reply queues an outbound message).
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import quote, urlencode
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.integrations.openwa import OpenWAClient, OpenWAError

from .adapters.postgres import PostgresRepository
from .http.context import RequestContext
from .http.dependencies import system_administrator_context
from .http.errors import ApiError
from .server_gateway import _opener, gateway_configuration

SESSION_NAME = "kiara"
SYNC_CHATS = 25
SYNC_MESSAGES = 30
SYNC_DEADLINE_SECONDS = 45
SYNC_PARALLEL = 6  # concurrent WhatsApp reads; the database writes stay sequential
_PHONE_CHAT = re.compile(r"^([1-9][0-9]{7,14})@c\.us$")
# WhatsApp now identifies most contacts by a linked id (@lid) instead of the phone; OpenWA resolves it.
_LID_CHAT = re.compile(r"^[0-9]{5,20}@lid$")
_PHONE = re.compile(r"^[1-9][0-9]{7,14}$")
_STATE_LABELS = {"ready", "qr_ready", "initializing", "authenticating", "created", "disconnected", "failed"}


class GatewayOpenWAClient(OpenWAClient):
    """The OpenWA REST client, routed through the gateway (Bearer token; the gateway injects the OpenWA key)."""

    def __init__(self, base_url: str, token: str, *, timeout_seconds: float = 40):  # noqa: D107 - no transport needed
        self.base_url = f"{base_url}/wa"
        self._token = token
        self._timeout = timeout_seconds

    def _request_sync(self, method: str, path: str, payload=None, idempotency_key=None):
        if idempotency_key is not None:
            raise OpenWAError("Envio não é permitido por este cliente.")
        request = urllib.request.Request(
            self.base_url + path, method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json", "Content-Type": "application/json"})
        try:
            with _opener.open(request, timeout=self._timeout) as response:
                raw = response.read(2_000_001)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise OpenWAError("OpenWA indisponível; nenhuma repetição automática.") from None
        if len(raw) > 2_000_000:
            raise OpenWAError("Resposta OpenWA acima do limite.")
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OpenWAError("Resposta OpenWA inválida.") from None
        if not isinstance(data, (dict, list)):
            raise OpenWAError("Resposta OpenWA incompatível.")
        return data

    async def phone_for(self, identifier: str, chat_id: str) -> str:
        """Phone digits of a one-to-one chat (@c.us directly, @lid through OpenWA's mapping), or ""."""
        direct = _PHONE_CHAT.match(chat_id)
        if direct:
            return direct.group(1)
        if not _LID_CHAT.match(chat_id):
            return ""
        data = await self._request("GET", f"/api/sessions/{identifier}/contacts/{quote(chat_id, safe='')}/phone")
        phone = "".join(character for character in str((data or {}).get("phone") or "") if character.isdigit()) if isinstance(data, dict) else ""
        return phone if _PHONE.match(phone) else ""

    async def live_history(self, identifier: str, chat_id: str, *, limit: int) -> list[dict]:
        """Recent messages read live from WhatsApp (OpenWA's own DB only has what arrived after linking)."""
        data = await self._request("GET", f"/api/sessions/{identifier}/messages/{quote(chat_id, safe='')}/history?"
                                   + urlencode({"limit": limit}))
        rows = data if isinstance(data, list) else data.get("messages") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise OpenWAError("Histórico OpenWA incompatível.")
        return [row for row in rows if isinstance(row, dict) and row.get("chatId") == chat_id]


def _client() -> GatewayOpenWAClient:
    base, token = gateway_configuration()
    if not base:
        raise ApiError(503, "whatsapp_server_not_configured", "O servidor da Kiara não está configurado.")
    return GatewayOpenWAClient(base, token)


def _public(session: dict[str, Any] | None) -> dict[str, Any]:
    if not session:
        return {"connected": False, "state": "not_created", "phone": ""}
    state = session.get("status") if session.get("status") in _STATE_LABELS else "unknown"
    phone = str(session.get("phone") or "")
    return {"connected": state == "ready", "state": state, "phone": phone[:4] + "…" + phone[-4:] if len(phone) > 8 else ""}


def _timestamp(value: Any) -> datetime:
    if type(value) in (int, float) and value > 0:
        return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def conversation_messages(rows: list[dict]) -> list[dict[str, Any]]:
    """OpenWA rows -> inbox messages (oldest first); media without caption becomes a short label."""
    messages, seen = [], set()
    for row in rows:
        if row.get("isStatusBroadcast"):
            continue
        identifier = row.get("waMessageId") or row.get("id")
        direction = {"incoming": "inbound", "outgoing": "outbound"}.get(row.get("direction"))
        if direction is None and isinstance(row.get("fromMe"), bool):
            direction = "outbound" if row["fromMe"] else "inbound"
        if not isinstance(identifier, str) or not identifier or identifier in seen or not direction:
            continue
        seen.add(identifier)
        body = row.get("body") if isinstance(row.get("body"), str) else ""
        kind = str(row.get("type") or "").lower()
        if not body.strip():
            body = {"image": "[imagem]", "video": "[vídeo]", "audio": "[áudio]", "ptt": "[áudio]", "document": "[documento]",
                    "sticker": "[figurinha]", "location": "[localização]"}.get(kind, "[mensagem]")
        messages.append({"external_id": identifier[:250], "direction": direction, "text": body[:10000],
                         "occurred_at": _timestamp(row.get("timestamp"))})
    return sorted(messages, key=lambda item: item["occurred_at"])


async def last_message_at(connection, organization_id: str, phone: str) -> datetime | None:
    """Newest message already in the inbox for this WhatsApp contact, so each sync only writes what is new."""
    from .adapters.postgres import _uuid
    row = await (await connection.execute(
        """SELECT max(m.sent_at) AS last FROM messages m JOIN conversation_threads t
           ON t.organization_id=m.organization_id AND t.id=m.thread_id
           WHERE t.organization_id=%s AND t.channel='whatsapp' AND t.provider_thread_id=%s""",
        (_uuid("organization", organization_id), phone))).fetchone()
    return row["last"] if row else None


class WhatsAppServerService:
    def __init__(self, postgres: PostgresRepository | None, client_factory=_client):
        self.postgres = postgres
        self.client_factory = client_factory

    async def _session(self, client) -> dict[str, Any] | None:
        return await client.find_session(SESSION_NAME)

    async def status(self) -> dict[str, Any]:
        client = self.client_factory()
        try:
            return _public(await self._session(client))
        except OpenWAError:
            raise ApiError(503, "whatsapp_server_unreachable", "O servidor do WhatsApp não respondeu.") from None

    async def connect(self) -> dict[str, Any]:
        client = self.client_factory()
        try:
            session = await self._session(client) or await client.create_session(SESSION_NAME)
            if session["status"] in {"created", "disconnected", "failed"}:
                session = await client.start_session(session["id"])
            result = {**_public(session), "qr": ""}
            if session["status"] == "qr_ready":
                result["qr"] = (await client.qr_code(session["id"]))["qrCode"]
            return result
        except OpenWAError:
            raise ApiError(503, "whatsapp_server_unreachable", "Não foi possível preparar a conexão. Tente novamente.") from None

    async def sync(self, organization_id: str) -> dict[str, Any]:
        if self.postgres is None:
            raise ApiError(503, "database_not_configured", "Banco de dados não configurado.")
        from .unified_inbox import ingest_message
        client = self.client_factory()
        deadline = time.monotonic() + SYNC_DEADLINE_SECONDS
        try:
            session = await self._session(client)
            if not session or session["status"] != "ready":
                return {**_public(session), "conversations": 0, "messages": 0, "skipped": 0}
            chats = await client.list_chats(session["id"], limit=200)
        except OpenWAError:
            raise ApiError(503, "whatsapp_server_unreachable", "O servidor do WhatsApp não respondeu.") from None
        # One-to-one chats (phone or @lid), newest first. Groups, broadcasts and channels are skipped.
        people = [chat for chat in chats if not chat.get("isGroup") and (_PHONE_CHAT.match(chat["id"]) or _LID_CHAT.match(chat["id"]))]
        people.sort(key=lambda chat: chat.get("timestamp") or 0, reverse=True)
        conversations = imported = 0
        skipped = len(chats) - len(people)
        gate = asyncio.Semaphore(SYNC_PARALLEL)

        async def read(chat):
            async with gate:
                try:
                    phone = await client.phone_for(session["id"], chat["id"])
                    rows = await client.live_history(session["id"], chat["id"], limit=SYNC_MESSAGES) if phone else []
                except (OpenWAError, ValueError):
                    return chat, "", []
                return chat, phone, rows

        try:
            fetched = await asyncio.wait_for(asyncio.gather(*(read(chat) for chat in people[:SYNC_CHATS])),
                                             timeout=max(5.0, deadline - time.monotonic() - 15))
        except TimeoutError:
            raise ApiError(503, "whatsapp_server_slow", "O WhatsApp ainda está carregando. Tente de novo em instantes.") from None
        for chat, phone, rows in fetched:
            if not phone:
                skipped += 1
                continue
            # Newest chats first; whatever does not fit in this run is picked up by the next one.
            if time.monotonic() > deadline:
                break
            messages = conversation_messages(rows)
            if not messages:
                continue
            name = str(chat.get("name") or "")[:160]
            async with self.postgres._transaction(organization_id) as connection:
                last = await last_message_at(connection, organization_id, phone)
                for message in messages:
                    if last and message["occurred_at"] < last:
                        continue  # already in the inbox; the exact duplicate is also rejected by the insert
                    result = await ingest_message(connection, organization_id, channel="whatsapp", identity=phone,
                                                  name=name, **message)
                    imported += int(result["inserted"])
            conversations += 1
        return {**_public(session), "conversations": conversations, "messages": imported, "skipped": skipped}


def create_whatsapp_server_router(service: WhatsAppServerService) -> APIRouter:
    router = APIRouter(prefix="/v1/whatsapp-server", tags=["whatsapp-server"])

    @router.get("/status")
    async def status(response: Response, _context: Annotated[RequestContext, Depends(system_administrator_context)]):
        response.headers["Cache-Control"] = "no-store, private"
        return await service.status()

    @router.post("/connect")
    async def connect(response: Response, context: Annotated[RequestContext, Depends(system_administrator_context)]):
        if context.role not in {"owner", "admin"}:
            raise ApiError(403, "whatsapp_connect_forbidden", "Somente owner ou admin conectam o WhatsApp.")
        response.headers["Cache-Control"] = "no-store, private"
        return await service.connect()

    @router.post("/sync")
    async def sync(response: Response, context: Annotated[RequestContext, Depends(system_administrator_context)]):
        response.headers["Cache-Control"] = "no-store, private"
        return await service.sync(context.organization_id)

    return router
