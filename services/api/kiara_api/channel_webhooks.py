"""Signed channel ingestion into the Kiara inbox; provider credentials never cross tenants."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from .http.errors import ApiError
from .integrations import IntegrationRepository
from .unified_inbox import ingest_message


def verify_chatwoot_signature(raw: bytes, timestamp: str, signature: str, secret: str):
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > 300:
        raise ValueError("Webhook expirado.")
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode()+b"."+raw, hashlib.sha256).hexdigest()
    if not secret or not hmac.compare_digest(signature, expected):
        raise ValueError("Assinatura inválida.")


async def credentials_for_webhook(repository: IntegrationRepository, organization_id: str, provider: str):
    try:
        org = UUID(organization_id)
    except ValueError:
        raise ApiError(404, "webhook_not_found", "Canal não encontrado.") from None
    # Unlike normal authenticated transactions, untrusted webhook paths must never
    # provision an organization merely by naming it.
    async with await repository._postgres._connect() as connection, connection.transaction():
        await connection.execute("SELECT set_config('app.organization_id',%s,true)", (str(org),))
        row = await (await connection.execute(
            "SELECT encrypted_credentials FROM integration_credentials WHERE organization_id=%s AND provider=%s AND status!='disabled'",
            (org, provider),
        )).fetchone()
    credentials = repository.decrypt_for_provider(row["encrypted_credentials"]) if row else None
    if not credentials:
        raise ApiError(404, "webhook_not_found", "Canal não encontrado.")
    return credentials


def chatwoot_message(payload: dict[str, Any], account_id: str):
    if payload.get("event") != "message_created" or payload.get("private"):
        return None
    if str((payload.get("account") or {}).get("id")) != account_id:
        raise ValueError("Conta divergente.")
    conversation = payload.get("conversation") or {}
    identifier = conversation.get("id")
    message_id = payload.get("id")
    text = payload.get("content")
    kind = payload.get("message_type")
    if not identifier or not message_id or not isinstance(text, str) or kind not in {"incoming", "outgoing", 0, 1}:
        return None
    timestamp = payload.get("created_at")
    occurred = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else datetime.now(UTC)
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    sender = payload.get("sender") or {}
    contact = (conversation.get("meta") or {}).get("sender") or sender
    return {"channel": "chatwoot", "identity": str(identifier), "external_id": str(message_id),
            "text": text[:10000], "occurred_at": occurred,
            "direction": "inbound" if kind in {"incoming", 0} else "outbound",
            "name": str(contact.get("name") or "Contato Chatwoot")[:160],
            "metadata": {"account_id": account_id, "conversation_id": identifier}}


def create_channel_webhook_router(repository: IntegrationRepository):
    router = APIRouter(prefix="/v1/channels", tags=["channel-webhooks"])

    async def bounded_body(request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise ApiError(413, "webhook_too_large", "Evento acima do limite.")
        return bytes(body)

    @router.post("/chatwoot/{organization_id}/webhook")
    async def chatwoot(organization_id: str, request: Request):
        credentials = await credentials_for_webhook(repository, organization_id, "chatwoot")
        raw = await bounded_body(request)
        if not raw or len(raw) > 65536:
            raise ApiError(413, "webhook_too_large", "Evento acima do limite.")
        try:
            verify_chatwoot_signature(raw, request.headers.get("x-chatwoot-timestamp", ""),
                                     request.headers.get("x-chatwoot-signature", ""), credentials.get("webhook_secret", ""))
            message = chatwoot_message(json.loads(raw), credentials["account_id"])
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ApiError(401, "webhook_invalid", "Evento não autenticado ou inválido.") from None
        if not message:
            return {"accepted": 0}
        async with repository._postgres._transaction(organization_id) as connection:
            result = await ingest_message(connection, organization_id, **message)
        return {"accepted": int(result["inserted"])}

    @router.get("/instagram/{organization_id}/webhook")
    async def instagram_challenge(organization_id: str, request: Request):
        credentials = await credentials_for_webhook(repository, organization_id, "instagram")
        query = request.query_params
        if (query.get("hub.mode") != "subscribe" or not credentials.get("verify_token")
                or not hmac.compare_digest(query.get("hub.verify_token", ""), credentials["verify_token"])):
            raise ApiError(401, "webhook_invalid", "Verificação de canal inválida.")
        return PlainTextResponse(query.get("hub.challenge", ""))

    @router.post("/instagram/{organization_id}/webhook")
    async def instagram(organization_id: str, request: Request):
        credentials = await credentials_for_webhook(repository, organization_id, "instagram")
        raw = await bounded_body(request)
        if not raw or len(raw) > 65536:
            raise ApiError(413, "webhook_too_large", "Evento acima do limite.")
        try:
            expected = "sha256=" + hmac.new(credentials["app_secret"].encode(), raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(request.headers.get("x-hub-signature-256", ""), expected):
                raise ValueError("Assinatura inválida.")
            payload = json.loads(raw)
            if payload.get("object") != "instagram" or not isinstance(payload.get("entry"), list):
                raise ValueError("Evento inválido.")
            messages = []
            for entry in payload["entry"][:100]:
                if str(entry.get("id")) != credentials["instagram_account_id"]:
                    raise ValueError("Conta divergente.")
                for event in entry.get("messaging", [])[:100]:
                    body = event.get("message") or {}
                    if not body.get("mid") or not isinstance(body.get("text"), str):
                        continue
                    echo = bool(body.get("is_echo"))
                    peer = str((event.get("recipient" if echo else "sender") or {}).get("id", ""))
                    if not peer.isdigit():
                        continue
                    messages.append({"channel": "instagram", "identity": f"{entry['id']}:{peer}",
                                     "external_id": str(body["mid"]), "text": body["text"][:10000],
                                     "occurred_at": datetime.fromtimestamp(event["timestamp"]/1000, UTC),
                                     "direction": "outbound" if echo else "inbound",
                                     "metadata": {"recipient_id": peer, "instagram_account_id": str(entry["id"])}})
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            raise ApiError(401, "webhook_invalid", "Evento não autenticado ou inválido.") from None
        accepted = 0
        async with repository._postgres._transaction(organization_id) as connection:
            for message in messages:
                result = await ingest_message(connection, organization_id, **message)
                accepted += int(result["inserted"])
        return {"accepted": accepted}

    return router
