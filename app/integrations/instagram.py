from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Any, Protocol


class InstagramContractError(ValueError):
    """The remote or inbound payload does not satisfy Kiara's Instagram contract."""


class InstagramApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int,
        code: int | None = None,
        subcode: int | None = None,
        trace_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code
        self.subcode = subcode
        self.trace_id = trace_id
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class InstagramMessage:
    instagram_account_id: str
    sender_id: str
    recipient_id: str
    message_id: str
    timestamp_ms: int
    text: str | None
    is_echo: bool
    raw_event: dict[str, Any]


class InstagramHttpClient(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        token: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any: ...


MAX_WEBHOOK_BYTES = 64 * 1024
MAX_WEBHOOK_ENTRIES = 100
MAX_EVENTS_PER_ENTRY = 100
MAX_MESSAGE_TEXT = 4096
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PLATFORM_ID = re.compile(r"[A-Za-z0-9._:-]{1,200}\Z")


def verify_webhook_challenge(
    *, mode: str | None, verify_token: str | None, challenge: str | None, expected_token: str
) -> str:
    """Validate Meta's GET subscription handshake and return the opaque challenge."""
    if not expected_token or not hmac.compare_digest(verify_token or "", expected_token):
        raise InstagramContractError("Webhook verify token invalido.")
    if mode != "subscribe" or challenge is None:
        raise InstagramContractError("Handshake de webhook invalido.")
    return challenge


def verify_webhook_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> None:
    """Authenticate the exact request bytes using Meta's X-Hub-Signature-256 contract."""
    if not isinstance(raw_body, bytes) or not raw_body or len(raw_body) > MAX_WEBHOOK_BYTES:
        raise InstagramContractError("Corpo de webhook ausente ou acima de 64 KiB.")
    if not app_secret:
        raise InstagramContractError("App secret nao configurado.")
    prefix = "sha256="
    if not signature_header or not signature_header.startswith(prefix):
        raise InstagramContractError("Assinatura de webhook ausente ou invalida.")
    supplied = signature_header[len(prefix) :]
    if not _HEX_SHA256.fullmatch(supplied):
        raise InstagramContractError("Assinatura de webhook invalida.")
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise InstagramContractError("Assinatura de webhook invalida.")


def parse_message_events(payload: dict[str, Any]) -> list[InstagramMessage]:
    """Normalize supported Instagram messaging events; ignore unrelated webhook fields."""
    if payload.get("object") != "instagram":
        raise InstagramContractError("Objeto de webhook nao suportado.")
    messages: list[InstagramMessage] = []
    entries = payload.get("entry")
    if not isinstance(entries, list) or len(entries) > MAX_WEBHOOK_ENTRIES:
        raise InstagramContractError("Webhook sem lista entry.")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        account_id = str(entry.get("id", ""))
        if not _PLATFORM_ID.fullmatch(account_id):
            raise InstagramContractError("Identificador de conta invalido.")
        events = entry.get("messaging", [])
        if not isinstance(events, list):
            continue
        if len(events) > MAX_EVENTS_PER_ENTRY:
            raise InstagramContractError("Webhook possui eventos demais.")
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("message"), dict):
                continue
            message = event["message"]
            mid = str(message.get("mid", ""))
            sender = event.get("sender", {})
            recipient = event.get("recipient", {})
            sender_id = str(sender.get("id", "")) if isinstance(sender, dict) else ""
            recipient_id = str(recipient.get("id", "")) if isinstance(recipient, dict) else ""
            timestamp = event.get("timestamp")
            text = message.get("text")
            if (
                not _PLATFORM_ID.fullmatch(mid)
                or not _PLATFORM_ID.fullmatch(sender_id)
                or not _PLATFORM_ID.fullmatch(recipient_id)
                or not isinstance(timestamp, int)
                or isinstance(timestamp, bool)
                or timestamp <= 0
                or (isinstance(text, str) and len(text) > MAX_MESSAGE_TEXT)
            ):
                continue
            messages.append(
                InstagramMessage(
                    instagram_account_id=account_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    message_id=mid,
                    timestamp_ms=timestamp,
                    text=text if isinstance(text, str) else None,
                    is_echo=bool(message.get("is_echo", False)),
                    raw_event=event,
                )
            )
    return messages


def error_from_response(status: int, body: dict[str, Any]) -> InstagramApiError:
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = error.get("code") if isinstance(error.get("code"), int) else None
    subcode = error.get("error_subcode") if isinstance(error.get("error_subcode"), int) else None
    return InstagramApiError(
        str(error.get("message") or f"Meta Graph API retornou HTTP {status}."),
        http_status=status,
        code=code,
        subcode=subcode,
        trace_id=error.get("fbtrace_id") if isinstance(error.get("fbtrace_id"), str) else None,
        retryable=status == 429 or status >= 500,
    )


class InstagramMessagingClient:
    def __init__(
        self, http: InstagramHttpClient, *, access_token: str, api_version: str, account_id: str
    ) -> None:
        if not access_token or not account_id or not api_version.startswith("v"):
            raise InstagramContractError("Token, conta e versao Graph explicita sao obrigatorios.")
        self.http = http
        self.access_token = access_token
        self.api_version = api_version
        self.account_id = account_id

    async def send_text(self, recipient_id: str, text: str) -> str:
        recipient_id, text = recipient_id.strip(), text.strip()
        if not recipient_id or not text:
            raise InstagramContractError("Destinatario e texto sao obrigatorios.")
        response = await self.http.request(
            "POST",
            f"https://graph.instagram.com/{self.api_version}/{self.account_id}/messages",
            token=self.access_token,
            payload={"recipient": {"id": recipient_id}, "message": {"text": text}},
        )
        status = int(response.status)
        body = response.body if isinstance(response.body, dict) else {}
        if status < 200 or status >= 300 or "error" in body:
            raise error_from_response(status, body)
        message_id = body.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            raise InstagramContractError("Resposta de envio sem message_id.")
        return message_id
