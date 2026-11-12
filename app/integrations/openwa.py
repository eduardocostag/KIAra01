"""Bounded OpenWA v0.30 REST adapter; no browser extension or automatic retries.

Only the gateway origin is configurable. WhatsApp linking still requires its QR.
The hardened Chatwoot transport is reused solely for origin validation and pinned
TCP/TLS connections; none of its account API paths or headers are used here.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import http.client
import json
import re
from typing import Any
from urllib.parse import urlencode

from app.integrations.chatwoot import ChatwootClient, ChatwootError


class OpenWAError(RuntimeError):
    """Sanitized gateway failure: never contains keys, messages, or response bodies."""


class OpenWADeliveryUnknown(OpenWAError):
    """A send was attempted without a confirmed receipt; do not blindly resend."""


def session_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", value):
        raise ValueError("ID da sessão OpenWA inválido.")
    return value


def phone_chat_id(phone: str) -> str:
    if not isinstance(phone, str) or not re.fullmatch(r"[+0-9 ()-]{8,40}", phone):
        raise ValueError("Informe o telefone com DDI e DDD; JIDs não são telefones.")
    digits = re.sub(r"[^0-9]", "", phone)
    if not re.fullmatch(r"[1-9][0-9]{7,14}", digits):
        raise ValueError("Telefone inválido.")
    # Never convert @lid digits into a phone or send into a group/broadcast.
    return digits + "@c.us"


def verify_webhook_signature(raw: bytes, signature: str | None, secret: str) -> bool:
    """Check raw bytes before JSON parsing; caller must durably deduplicate events.

    OpenWA's signature has no timestamp. Persist X-OpenWA-Idempotency-Key or the
    message ID with the session ID before accepting a delivery. This helper does
    not register a webhook, accept a message, or provide replay protection.
    """
    if not isinstance(raw, bytes) or not secret or not isinstance(signature, str):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.encode(), expected.encode())


class OpenWAClient:
    def __init__(self, base_url: str, api_key: str, *, allow_private_hosts: bool = False,
                 timeout_seconds: float = 15):
        self._transport = ChatwootClient(base_url, api_key, 1,
                                         allow_private_hosts=allow_private_hosts,
                                         timeout_seconds=timeout_seconds)
        self.base_url = self._transport.base_url
        self._api_key = api_key

    async def _request(self, method: str, path: str, payload=None, *, idempotency_key=None):
        return await asyncio.to_thread(self._request_sync, method, path, payload, idempotency_key)

    def _request_sync(self, method: str, path: str, payload=None, idempotency_key=None):
        connection = None
        try:
            destination = self._transport._validate_destination()
            connection = self._transport._connection(destination)
            headers = {"X-API-Key": self._api_key, "Accept": "application/json",
                       "Content-Type": "application/json"}
            if idempotency_key:
                headers["Idempotency-Key"] = idempotency_key
            connection.request(method, path, headers=headers,
                               body=json.dumps(payload).encode() if payload is not None else None)
            with connection.getresponse() as response:
                if not 200 <= response.status < 300:
                    raise OpenWAError(f"OpenWA retornou HTTP {response.status}; nenhuma repetição automática.")
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise OpenWAError("Resposta OpenWA acima do limite.")
            data = json.loads(raw)
            if not isinstance(data, (dict, list)):
                raise OpenWAError("Resposta OpenWA incompatível.")
            return data
        except (OSError, http.client.HTTPException, ChatwootError, ValueError, UnicodeError):
            raise OpenWAError("OpenWA indisponível ou resposta inválida; nenhuma repetição automática.") from None
        finally:
            if connection:
                connection.close()

    @staticmethod
    def _session(data: Any, expected_id: str | None = None) -> dict[str, Any]:
        if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not isinstance(data.get("status"), str):
            raise OpenWAError("Estado da sessão OpenWA incompatível.")
        if expected_id and data["id"] != expected_id:
            raise OpenWAError("OpenWA retornou outra sessão.")
        allowed = {"id", "name", "status", "phone", "pushName", "connectedAt", "lastActive", "engineLoaded"}
        return {key: value for key, value in data.items() if key in allowed}

    async def status(self, identifier: str) -> dict[str, Any]:
        identifier = session_id(identifier)
        return self._session(await self._request("GET", f"/api/sessions/{identifier}"), identifier)

    async def find_session(self, name: str) -> dict[str, Any] | None:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9-]{3,50}", name):
            raise ValueError("Nome de sessão OpenWA inválido.")
        data = await self._request("GET", "/api/sessions?" + urlencode({"name": name}))
        if not isinstance(data, list) or len(data) > 1:
            raise OpenWAError("Lista de sessões OpenWA incompatível.")
        return self._session(data[0]) if data else None

    async def create_session(self, name: str) -> dict[str, Any]:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9-]{3,50}", name):
            raise ValueError("Nome de sessão OpenWA inválido.")
        return self._session(await self._request("POST", "/api/sessions", {"name": name}))

    async def start_session(self, identifier: str) -> dict[str, Any]:
        identifier = session_id(identifier)
        return self._session(await self._request("POST", f"/api/sessions/{identifier}/start"), identifier)

    async def qr_code(self, identifier: str) -> dict[str, str]:
        data = await self._request("GET", f"/api/sessions/{session_id(identifier)}/qr")
        if (not isinstance(data, dict) or data.get("status") != "qr_ready"
                or not isinstance(data.get("qrCode"), str)
                or not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/=]+", data["qrCode"])
                or len(data["qrCode"]) > 500_000):
            raise OpenWAError("QR do OpenWA indisponível ou inválido.")
        return {"qrCode": data["qrCode"], "status": data["status"]}

    async def read_messages(self, identifier: str, phone: str, *, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Limite deve estar entre 1 e 100.")
        chat = phone_chat_id(phone)
        query = urlencode({"chatId": chat, "limit": limit, "inlineMedia": "false"})
        data = await self._request("GET", f"/api/sessions/{session_id(identifier)}/messages?{query}")
        messages = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(messages, list) or any(not isinstance(row, dict) or row.get("chatId") != chat for row in messages):
            raise OpenWAError("Histórico OpenWA incompatível com o contato solicitado.")
        allowed = {"id", "waMessageId", "chatId", "body", "direction", "timestamp", "status", "type", "chatName"}
        return [{k: v for k, v in row.items() if k in allowed} for row in messages[:limit]]

    async def send_text(self, identifier: str, phone: str, text: str, *, idempotency_key: str) -> dict:
        identifier, chat = session_id(identifier), phone_chat_id(phone)
        if not isinstance(text, str) or not text.strip() or len(text) > 4096:
            raise ValueError("Mensagem deve conter entre 1 e 4096 caracteres.")
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[\x21-\x7e]{1,255}", idempotency_key):
            raise ValueError("Chave de idempotência inválida.")
        try:
            data = await self._request("POST", f"/api/sessions/{identifier}/messages/send-text",
                                       {"chatId": chat, "text": text, "linkPreview": False},
                                       idempotency_key=idempotency_key)
            if not isinstance(data, dict) or not isinstance(data.get("messageId"), str) or not data["messageId"]:
                raise OpenWAError("Envio sem comprovante.")
        except OpenWAError:
            raise OpenWADeliveryUnknown("Não foi possível confirmar o envio. Confira a conversa antes de repetir.") from None
        # A receipt confirms gateway acceptance, NOT remote delivery or reading.
        return {"message_id": data["messageId"], "status": "accepted", "timestamp": data.get("timestamp")}
