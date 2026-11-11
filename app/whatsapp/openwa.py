"""Engine-compatible WhatsApp transport using OpenWA's persistent session API.

API acceptance is not delivery/read confirmation. This adapter never launches a
browser, reads Chrome cookies, or tears down a linked WhatsApp session on close.
"""
from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.integrations.openwa import OpenWAClient, OpenWAError, phone_chat_id, session_id
from app.whatsapp.browser import BrowserNotReady


class OpenWABrowser:
    read_only = False
    receipt_semantics = "gateway_accepted"

    def __init__(self, client: OpenWAClient, session: str, *,
                 send_authorizer: Callable[[str], Awaitable[None]] | None = None):
        self.client = client
        self.session_id = session_id(session)
        self._send_lock = asyncio.Lock()
        self.send_authorizer = send_authorizer

    async def start(self):
        # Lifecycle/linking belongs to setup: never create, reset, or unlink an
        # account just because the worker process restarted.
        return None

    async def close(self):
        return None

    async def status(self):
        try:
            state = await self.client.status(self.session_id)
        except OpenWAError:
            return "offline"
        if state["status"] == "ready" and state.get("engineLoaded") is True:
            return "ready"
        return "qr" if state["status"] == "qr_ready" else "offline"

    async def read(self, phone):
        phone_chat_id(phone)
        if await self.status() != "ready":
            raise BrowserNotReady("Conecte a sessão WhatsApp no OpenWA antes de continuar.")
        rows = await self.client.read_messages(self.session_id, phone, limit=100)
        messages = []
        seen = set()
        for index, row in enumerate(rows):
            identifier = row.get("waMessageId") or row.get("id")
            body = row.get("body")
            direction = row.get("direction")
            if (not isinstance(identifier, str) or not identifier or len(identifier) > 250
                    or not isinstance(body, str) or direction not in {"incoming", "outgoing"}):
                # An unrecognizable event cannot be silently omitted from a send
                # snapshot. Refuse the read so a human can review the chat.
                raise BrowserNotReady("Histórico OpenWA incompleto; envio suspenso para revisão.")
            if identifier in seen:
                continue
            seen.add(identifier)
            timestamp = row.get("timestamp")
            known_time = type(timestamp) in (int, float) and math.isfinite(timestamp)
            # OpenWA stores and returns newest-first by default. Unknown times
            # retain reversed API order instead of inventing a date.
            sort_key = (float(timestamp) if known_time else 0, -index)
            messages.append((sort_key, {"id": identifier, "direction": "in" if direction == "incoming" else "out", "text": body}))
        return [message for _, message in sorted(messages, key=lambda item: item[0])]

    async def send(self, phone, text, expected_ids=None):
        phone_chat_id(phone)
        async with self._send_lock:
            snapshot = await self.read(phone)
            current_ids = {message["id"] for message in snapshot}
            if expected_ids is not None and current_ids != set(expected_ids):
                raise BrowserNotReady("Conversa mudou antes do envio; revisão necessária.")
            if self.send_authorizer is not None:
                await self.send_authorizer(phone)
            # The gateway has no compare-and-send primitive. This fresh check
            # narrows, but cannot remove, a simultaneous human-message race.
            receipt = await self.client.send_text(self.session_id, phone, text,
                                                  idempotency_key="kiara-" + uuid4().hex)
            identifier = receipt.get("message_id")
            if not isinstance(identifier, str) or not identifier:
                return False
            return identifier
