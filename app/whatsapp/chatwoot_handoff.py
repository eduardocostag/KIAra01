"""Fail-closed, bounded Chatwoot human-handoff check for the OpenWA worker.

OpenWA's plugin handover gate does not authorize an independent REST sender.
This guard therefore checks Chatwoot immediately before that sender writes.
There is no distributed compare-and-send primitive: an agent can still assign
the conversation after the check. No claim of atomic handover is made here.
"""
from __future__ import annotations

from app.integrations.chatwoot import ChatwootClient, positive_id
from app.integrations.openwa import phone_chat_id
from app.whatsapp.browser import BrowserNotReady


class ChatwootHandoffGuard:
    def __init__(self, client: ChatwootClient, inbox_id: int):
        self.client = client
        self.inbox_id = positive_id(inbox_id, "inbox_id")

    async def __call__(self, phone: str) -> None:
        target = phone_chat_id(phone)
        matching = []
        exhausted = False
        try:
            for page in range(1, 6):
                rows = await self.client.list_conversations(status="all", page=page, limit=50)
                if not isinstance(rows, list) or len(rows) > 50:
                    raise ValueError("invalid conversation page")
                # Chatwoot controls page size; our adapter's limit only caps the
                # returned rows. A short page therefore does not prove the end.
                if not rows:
                    exhausted = True
                    break
                for row in rows:
                    if not isinstance(row, dict):
                        raise TypeError("invalid conversation")
                    # Treat inbox IDs as numeric wire identifiers; do not match
                    # malformed strings, bools or ids supplied in another field.
                    if type(row.get("inbox_id")) is not int or row["inbox_id"] != self.inbox_id:
                        continue
                    meta = row.get("meta")
                    if not isinstance(meta, dict):
                        continue
                    sender = meta.get("sender")
                    if not isinstance(sender, dict):
                        continue
                    try:
                        sender_phone = phone_chat_id(sender.get("phone_number"))
                    except ValueError:
                        continue
                    if sender_phone == target:
                        matching.append(row)
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            # Never expose API bodies, keys or customer details in an error.
            raise BrowserNotReady("Não foi possível verificar o atendimento humano no Chatwoot. Envio suspenso.") from None
        if not exhausted or len(matching) != 1:
            # New outreach needs an API-channel conversation first. An absent
            # conversation is not permission to start one or bypass the inbox.
            raise BrowserNotReady("Conversa única não confirmada no Chatwoot. Revise a caixa de entrada antes de enviar.")
        conversation = matching[0]
        meta = conversation["meta"]
        attributes = conversation.get("custom_attributes", {})
        if not isinstance(attributes, dict):
            raise BrowserNotReady("Configuração de atendimento Chatwoot inválida. Envio suspenso.")
        automation = attributes.get("kiara_automation_enabled", True)
        if (conversation.get("status") not in {"open", "pending"}
                or conversation.get("assignee_id") is not None
                or meta.get("assignee") is not None
                or automation is not True):
            raise BrowserNotReady("Conversa pausada ou assumida no Chatwoot. A Kiara não enviará mensagens.")
