"""Bounded Application API client for Chatwoot v4.19.1 (account-scoped)."""
from __future__ import annotations

import asyncio
import http.client
import ipaddress
import json
import math
import socket
import ssl
from typing import Any
from urllib.parse import urlencode, urlsplit


class ChatwootError(RuntimeError):
    """Errors contain no remote body, credentials, or message text."""


def positive_id(value: Any, name: str = "identificador") -> int:
    if type(value) is not int or not 1 <= value <= 2**53 - 1:
        raise ValueError(f"{name} deve ser um inteiro positivo.")
    return value


def validate_content(content: str) -> None:
    if not isinstance(content, str) or not content.strip() or len(content) > 10000:
        raise ValueError("A mensagem deve conter entre 1 e 10000 caracteres.")


def validate_base_url(base_url: str, *, allow_private_hosts: bool = False) -> str:
    if not isinstance(base_url, str) or len(base_url) > 2048 or any(ord(c) < 33 for c in base_url):
        raise ValueError("URL base Chatwoot invalida.")
    try:
        parsed = urlsplit(base_url)
        _ = parsed.port
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        address = None
    try:
        parsed = urlsplit(base_url)
        _ = parsed.port
    except ValueError:
        raise ValueError("URL base Chatwoot invalida.") from None
    loopback = bool(address and address.is_loopback) or parsed.hostname == "localhost"
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"} or parsed.scheme not in {"http", "https"}):
        raise ValueError("Informe somente a origem HTTPS do Chatwoot.")
    if loopback:
        if not allow_private_hosts:
            raise ValueError("Chatwoot local nao permitido neste contexto.")
    elif parsed.scheme != "https" or (address is not None and not address.is_global):
        raise ValueError("Chatwoot remoto exige destino HTTPS publico.")
    return base_url.rstrip("/")


class ChatwootClient:
    def __init__(
        self, base_url: str, api_access_token: str, account_id: int, *,
        allow_private_hosts: bool = False, timeout_seconds: float = 15,
    ) -> None:
        self.base_url = validate_base_url(base_url, allow_private_hosts=allow_private_hosts)
        self.account_id = positive_id(account_id, "account_id")
        if (not isinstance(api_access_token, str) or not api_access_token.strip()
                or len(api_access_token) > 4096 or any(ord(c) < 33 for c in api_access_token)):
            raise ValueError("Token Chatwoot invalido.")
        if (not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 60):
            raise ValueError("Timeout Chatwoot deve estar entre 0 e 60 segundos.")
        self._token = api_access_token
        self.allow_private_hosts = allow_private_hosts
        self.timeout = timeout_seconds

    def _validate_destination(self) -> tuple[Any, ...]:
        parsed = urlsplit(self.base_url)
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (
                443 if parsed.scheme == "https" else 80),
                                           type=socket.SOCK_STREAM)
        except OSError:
            raise ChatwootError("Destino Chatwoot indisponivel.") from None
        if not addresses:
            raise ChatwootError("Destino Chatwoot indisponivel.")
        for item in addresses:
            address = ipaddress.ip_address(item[4][0])
            if not address.is_global and not (self.allow_private_hosts and address.is_loopback):
                raise ChatwootError("Destino Chatwoot privado recusado.")
        # Select once. No automatic retry across addresses, particularly after a POST.
        return addresses[0]

    def _connection(self, destination: tuple[Any, ...]) -> http.client.HTTPConnection:
        parsed = urlsplit(self.base_url)
        family, socktype, protocol, _, sockaddr = destination
        # Connect to the validated numeric sockaddr directly: no second hostname lookup,
        # proxy, redirect, or tunnel can replace this destination.
        transport = socket.socket(family, socktype, protocol)
        try:
            transport.settimeout(self.timeout)
            transport.connect(sockaddr)
            if parsed.scheme == "https":
                context = ssl.create_default_context()
                transport = context.wrap_socket(transport, server_hostname=parsed.hostname)
                connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443,
                                                          timeout=self.timeout, context=context)
            else:
                connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80,
                                                        timeout=self.timeout)
            # HTTPConnection sends Host for the original hostname. HTTPS retains hostname
            # verification and SNI above, although TCP is pinned to the validated address.
            connection.sock = transport
            return connection
        except BaseException:
            transport.close()
            raise

    async def _request(self, method: str, suffix: str, payload=None) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, suffix, payload)

    def _request_sync(self, method: str, suffix: str, payload) -> dict[str, Any]:
        destination = self._validate_destination()
        connection = None
        try:
            connection = self._connection(destination)
            connection.request(method, f"/api/v1/accounts/{self.account_id}/{suffix}",
                               body=json.dumps(payload).encode("utf-8") if payload is not None else None,
                               headers={"api_access_token": self._token, "Accept": "application/json",
                                        "Content-Type": "application/json"})
            with connection.getresponse() as response:
                if 300 <= response.status < 400:
                    raise ChatwootError("Redirecionamento Chatwoot recusado.")
                if not 200 <= response.status < 300:
                    raise ChatwootError(f"Chatwoot retornou HTTP {response.status}.")
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ChatwootError("Resposta Chatwoot excedeu o limite.")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ChatwootError("Resposta Chatwoot incompativel.")
            return data
        except (OSError, http.client.HTTPException):
            raise ChatwootError("Chatwoot indisponivel; confirme o resultado antes de repetir um envio.") from None
        except (UnicodeError, json.JSONDecodeError):
            raise ChatwootError("Resposta Chatwoot incompativel.") from None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit deve estar entre 1 e 100.")

    @staticmethod
    def _items(data: dict[str, Any], *, conversations: bool = False) -> list[dict[str, Any]]:
        if conversations:
            data = data.get("data", data)
        items = data.get("payload") if isinstance(data, dict) else None
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ChatwootError("Lista Chatwoot incompativel.")
        return items

    async def list_inboxes(self, limit: int = 50) -> list[dict[str, Any]]:
        self._limit(limit)
        items = self._items(await self._request("GET", "inboxes"))
        allowed = {"id", "name", "channel_type", "avatar_url", "greeting_enabled"}
        return [{k: v for k, v in item.items() if k in allowed} for item in items[:limit]]

    async def list_conversations(
        self, status: str = "open", page: int = 1, limit: int = 25,
    ) -> list[dict[str, Any]]:
        if status not in {"all", "open", "resolved", "pending", "snoozed"}:
            raise ValueError("Status Chatwoot invalido.")
        positive_id(page, "page")
        if page > 10000:
            raise ValueError("page excede o limite.")
        self._limit(limit)
        suffix = "conversations?" + urlencode({"status": status, "page": page})
        return self._items(await self._request("GET", suffix), conversations=True)[:limit]

    async def list_messages(
        self, conversation_id: int, before: int | None = None, limit: int = 20,
    ) -> list[dict[str, Any]]:
        positive_id(conversation_id, "conversation_id")
        self._limit(limit)
        suffix = f"conversations/{conversation_id}/messages"
        if before is not None:
            suffix += "?" + urlencode({"before": positive_id(before, "before")})
        return self._items(await self._request("GET", suffix))[-limit:]

    async def send_message(self, conversation_id: int, content: str) -> dict[str, Any]:
        positive_id(conversation_id, "conversation_id")
        validate_content(content)
        data = await self._request("POST", f"conversations/{conversation_id}/messages", {
            "content": content, "message_type": "outgoing", "private": False,
            "content_type": "text",
        })
        if type(data.get("id")) is not int or data["id"] <= 0:
            raise ChatwootError("Envio sem identificador confirmado; confira Chatwoot antes de repetir.")
        return {key: data[key] for key in ("id", "status", "conversation_id") if key in data}
