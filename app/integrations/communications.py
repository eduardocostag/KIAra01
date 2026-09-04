from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.integrations.credentials import CredentialProvider
from app.integrations.http import JsonHttpClient


@dataclass(frozen=True, slots=True)
class OutboundMessage:
    destination: str
    text: str
    idempotency_key: str

    @classmethod
    def prepare(cls, destination: str, text: str) -> OutboundMessage:
        if not destination.strip() or not text.strip():
            raise ValueError("Destino e mensagem são obrigatórios.")
        return cls(destination.strip(), text.strip(), str(uuid.uuid4()))


class CommunicationsProvider(Protocol):
    async def read_messages(self, limit: int = 20) -> list[dict[str, Any]]: ...
    async def send_message(self, message: OutboundMessage) -> str: ...
    async def read_calendar(self, limit: int = 20) -> list[dict[str, Any]]: ...
    async def create_event(self, event: dict[str, Any], idempotency_key: str) -> str: ...


class MicrosoftGraphCommunications:
    def __init__(
        self, credentials: CredentialProvider, client: JsonHttpClient | None = None
    ) -> None:
        self.credentials = credentials
        self.client = client or JsonHttpClient()

    def _token(self) -> str:
        token = self.credentials.get("KIARA_GRAPH_TOKEN")
        if not token:
            raise RuntimeError("Credencial Microsoft Graph não configurada.")
        return token

    async def read_messages(self, limit: int = 20) -> list[dict[str, Any]]:
        response = await self.client.request(
            "GET",
            f"https://graph.microsoft.com/v1.0/me/chats?$top={min(max(limit, 1), 50)}",
            token=self._token(),
        )
        return list(response.body.get("value", []))

    async def send_message(self, message: OutboundMessage) -> str:
        response = await self.client.request(
            "POST",
            f"https://graph.microsoft.com/v1.0/chats/{message.destination}/messages",
            token=self._token(),
            payload={"body": {"content": message.text}},
            idempotency_key=message.idempotency_key,
        )
        return str(response.body.get("id", message.idempotency_key))

    async def read_calendar(self, limit: int = 20) -> list[dict[str, Any]]:
        response = await self.client.request(
            "GET",
            f"https://graph.microsoft.com/v1.0/me/events?$top={min(max(limit, 1), 50)}",
            token=self._token(),
        )
        return list(response.body.get("value", []))

    async def create_event(self, event: dict[str, Any], idempotency_key: str) -> str:
        response = await self.client.request(
            "POST",
            "https://graph.microsoft.com/v1.0/me/events",
            token=self._token(),
            payload=event,
            idempotency_key=idempotency_key,
        )
        return str(response.body.get("id", idempotency_key))
