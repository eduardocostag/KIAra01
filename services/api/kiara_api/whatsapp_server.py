"""WhatsApp on the always-on Debian server: OpenWA behind the Kiara gateway.

Connects the session by QR and copies recent one-to-one conversations into the unified inbox.
Read-only towards WhatsApp: nothing here sends messages, and imported history never triggers
automations (only an operator reply queues an outbound message).
"""
from __future__ import annotations

import asyncio
import json
import random
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
# Gentle on the account: WhatsApp Web runs in a real browser page on the server, and heavy bursts of reads
# (parallel history loads, right after linking) preceded both observed unlinks. Read like a person would.
SYNC_CHATS = 10            # chats read per run; the rest come in the next runs
SYNC_MESSAGES = 30
SYNC_DEADLINE_SECONDS = 45
SYNC_PARALLEL = 1          # one chat at a time
SYNC_PAUSE_SECONDS = (0.4, 1.2)   # random pause between chats, never a fixed robot rhythm
SYNC_WARMUP_SECONDS = 300  # let WhatsApp Web finish its own first load (and reload) after linking
_PHONE_CHAT = re.compile(r"^([1-9][0-9]{7,14})@c\.us$")
# WhatsApp now identifies most contacts by a linked id (@lid) instead of the phone; OpenWA resolves it.
_LID_CHAT = re.compile(r"^[0-9]{5,20}@lid$")
_PHONE = re.compile(r"^[1-9][0-9]{7,14}$")
_STATE_LABELS = {"ready", "qr_ready", "initializing", "authenticating", "created", "disconnected", "failed"}


class OpenWARejected(OpenWAError):
    """OpenWA answered with an HTTP error: the message was definitely not sent (e.g. the anti-ban pacing said no)."""


class GatewayOpenWAClient(OpenWAClient):
    """The OpenWA REST client, routed through the gateway (Bearer token; the gateway injects the OpenWA key)."""

    def __init__(self, base_url: str, token: str, *, timeout_seconds: float = 40):  # noqa: D107 - no transport needed
        self.base_url = f"{base_url}/wa"
        self._token = token
        self._timeout = timeout_seconds

    def _request_sync(self, method: str, path: str, payload=None, idempotency_key=None):
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json", "Content-Type": "application/json"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            self.base_url + path, method=method,
            data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            with _opener.open(request, timeout=self._timeout) as response:
                raw = response.read(2_000_001)
        except urllib.error.HTTPError as error:
            raise OpenWARejected(f"OpenWA recusou ({error.code}).") from None
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


async def known_chats(connection, organization_id: str) -> dict[str, datetime]:
    """WhatsApp chat id -> newest message already in the inbox, to skip chats that did not change."""
    from .adapters.postgres import _uuid
    rows = await (await connection.execute(
        """SELECT metadata->>'wa_chat_id' AS chat, last_message_at FROM conversation_threads
           WHERE organization_id=%s AND channel='whatsapp' AND metadata ? 'wa_chat_id' AND last_message_at IS NOT NULL""",
        (_uuid("organization", organization_id),))).fetchall()
    return {row["chat"]: row["last_message_at"] for row in rows if row["chat"]}


async def remember_chat(connection, organization_id: str, phone: str, chat_id: str) -> None:
    from .adapters.postgres import _uuid
    await connection.execute(
        """UPDATE conversation_threads SET metadata=COALESCE(metadata,'{}'::jsonb) || jsonb_build_object('wa_chat_id', %s::text)
           WHERE organization_id=%s AND channel='whatsapp' AND provider_thread_id=%s""",
        (chat_id, _uuid("organization", organization_id), phone))


def _changed(chat: dict, known: dict[str, datetime]) -> bool:
    last = known.get(chat["id"])
    stamp = chat.get("timestamp")
    if last is None or type(stamp) not in (int, float):
        return True
    return _timestamp(stamp) > last


# Sessions already set to "unavailable" (session id -> connectedAt), per API instance.
_quiet_presence: dict[str, Any] = {}


async def keep_presence_unavailable(client, session: dict[str, Any]) -> None:
    """Do not look "online" all day: a linked device that never goes offline looks automated, and while
    WhatsApp Web is online the phone stops getting notifications. Sent once per connection."""
    marker = session.get("connectedAt") or True
    if _quiet_presence.get(session["id"]) == marker:
        return
    try:
        await client._request("PUT", f"/api/sessions/{session['id']}/presence", {"available": False})
        _quiet_presence[session["id"]] = marker
    except OpenWAError:
        pass  # cosmetic; retried on the next sync


class WhatsAppServerService:
    def __init__(self, postgres: PostgresRepository | None, client_factory=_client):
        self.postgres = postgres
        self.client_factory = client_factory

    async def _session(self, client) -> dict[str, Any] | None:
        return await client.find_session(SESSION_NAME)

    async def notify_owner(self, phone: str, text: str, key: str) -> bool:
        """A note to the business owner's own number (daily summary). Never used for customers."""
        try:
            return bool(await send_reply({"provider_thread_id": phone, "metadata": {}}, text, key, 0))
        except (OpenWAError, OpenWARejected):
            return False

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
            if session["status"] == "ready":
                await keep_presence_unavailable(client, session)
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
            await keep_presence_unavailable(client, session)
            linked = session.get("connectedAt")
            if isinstance(linked, str) and (datetime.now(UTC) - _timestamp(linked)).total_seconds() < SYNC_WARMUP_SECONDS:
                return {**_public(session), "conversations": 0, "messages": 0, "skipped": 0, "warming_up": True}
            chats = await client.list_chats(session["id"], limit=200)
        except OpenWAError:
            raise ApiError(503, "whatsapp_server_unreachable", "O servidor do WhatsApp não respondeu.") from None
        # One-to-one chats (phone or @lid), newest first. Groups, broadcasts and channels are skipped.
        people = [chat for chat in chats if not chat.get("isGroup") and (_PHONE_CHAT.match(chat["id"]) or _LID_CHAT.match(chat["id"]))]
        people.sort(key=lambda chat: chat.get("timestamp") or 0, reverse=True)
        conversations = imported = 0
        skipped = len(chats) - len(people)
        # Only chats with something new are read from WhatsApp: a quiet inbox costs one listing per sync.
        async with self.postgres._transaction(organization_id) as connection:
            known = await known_chats(connection, organization_id)
        people = [chat for chat in people if _changed(chat, known)][:SYNC_CHATS]
        gate = asyncio.Semaphore(SYNC_PARALLEL)

        async def read(chat):
            async with gate:
                await asyncio.sleep(random.uniform(*SYNC_PAUSE_SECONDS))
                try:
                    phone = await client.phone_for(session["id"], chat["id"])
                    rows = await client.live_history(session["id"], chat["id"], limit=SYNC_MESSAGES) if phone else []
                except (OpenWAError, ValueError):
                    return chat, "", []
                return chat, phone, rows

        try:
            fetched = await asyncio.wait_for(asyncio.gather(*(read(chat) for chat in people)),
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
                await remember_chat(connection, organization_id, phone, chat["id"])
            conversations += 1
        return {**_public(session), "conversations": conversations, "messages": imported, "skipped": skipped}


# ---- Safe sending through the linked number (manual replies from the inbox) --------------------------------
# WhatsApp bans accounts for bulk, unsolicited, robotic messaging. The Kiara only sends like a person answering
# a conversation: to contacts who already talked to the number, one at a time, with typing and human spacing.
REPLY_DAILY_LIMIT = 300            # safety ceiling per number per 24 h (OpenWA's own warm-up pacing applies on top)
BURST_MAX_CONTACTS = 3             # the same text to more than this many other contacts within an hour = a blast
SEND_GAP_SECONDS = (8.0, 15.0)     # random minimum spacing between two sends of the same number


def server_sending_available() -> bool:
    return bool(gateway_configuration()[0])


async def guard_reply(connection, organization_id: str, thread_uuid, text: str) -> float:
    """Anti-ban rules checked before anything is queued. Returns how long to wait before sending."""
    from .adapters.postgres import _uuid
    org = _uuid("organization", organization_id)
    inbound = await (await connection.execute(
        "SELECT 1 FROM messages WHERE organization_id=%s AND thread_id=%s AND direction='inbound' LIMIT 1", (org, thread_uuid))).fetchone()
    if not inbound:
        raise ApiError(409, "whatsapp_cold_message_blocked",
                       "Para proteger seu número, a Kiara só envia para quem já conversou com você no WhatsApp.")
    sent = await (await connection.execute(
        """SELECT count(*) AS total, max(o.updated_at) AS last FROM commercial_outbox o JOIN conversation_threads t
           ON t.organization_id=o.organization_id AND t.id=o.thread_id
           WHERE o.organization_id=%s AND t.channel='whatsapp' AND o.status IN ('sent','sending')
             AND o.updated_at > now() - interval '24 hours'""", (org,))).fetchone()
    if sent and sent["total"] >= REPLY_DAILY_LIMIT:
        raise ApiError(429, "whatsapp_daily_limit", "Limite diário de segurança do seu número atingido. Continue amanhã.")
    blast = await (await connection.execute(
        """SELECT count(DISTINCT thread_id) AS contacts FROM commercial_outbox
           WHERE organization_id=%s AND body=%s AND thread_id<>%s AND created_at > now() - interval '60 minutes'""",
        (org, text, thread_uuid))).fetchone()
    if blast and blast["contacts"] >= BURST_MAX_CONTACTS:
        raise ApiError(409, "whatsapp_bulk_blocked",
                       "A mesma mensagem já foi para vários contatos na última hora. Personalize o texto para proteger seu número.")
    last = sent["last"] if sent else None
    gap = random.uniform(*SEND_GAP_SECONDS)
    elapsed = (datetime.now(UTC) - last).total_seconds() if last else gap
    return max(0.0, min(gap - elapsed, SEND_GAP_SECONDS[1]))


async def send_reply(thread: dict[str, Any], text: str, outbox_id: str, wait: float) -> str | None:
    """Send one reply through the linked number like a person: spacing, "typing…", then the text.
    Returns OpenWA's message id, or None when the session is not connected (the reply stays queued)."""
    client = _client()
    session = await client.find_session(SESSION_NAME)
    if not session or session["status"] != "ready":
        return None
    from .unified_inbox import normalize_phone
    chat_id = str((thread.get("metadata") or {}).get("wa_chat_id") or f"{normalize_phone(thread['provider_thread_id'])}@c.us")
    if not (_PHONE_CHAT.match(chat_id) or _LID_CHAT.match(chat_id)):
        raise OpenWARejected("Conversa sem destino individual.")
    await asyncio.sleep(wait)
    try:
        await client._request("POST", f"/api/sessions/{session['id']}/chats/typing", {"chatId": chat_id, "state": "typing"})
    except OpenWAError:
        pass  # cosmetic
    await asyncio.sleep(min(1.5 + len(text) / 35, 6.0) + random.uniform(0.2, 1.2))
    data = await client._request("POST", f"/api/sessions/{session['id']}/messages/send-text",
                                 {"chatId": chat_id, "text": text[:4096], "linkPreview": False},
                                 idempotency_key=f"kiara-{outbox_id}")
    message_id = data.get("messageId") if isinstance(data, dict) else None
    if not isinstance(message_id, str) or not message_id:
        raise OpenWAError("Envio sem comprovante.")
    return message_id


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
