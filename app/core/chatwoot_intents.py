"""Explicit Chatwoot commands, without asking a model to choose a recipient."""
from __future__ import annotations

import re
import unicodedata

from app.core.intents import Intent


class ChatwootMatcher:
    def match(self, message: str) -> Intent | None:
        if not re.search(r"\bchatwoot\b", message, re.IGNORECASE):
            return None
        normalized = unicodedata.normalize("NFKD", message.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        command = re.sub(r"^\s*kiara\s*[,;:]?\s*", "", normalized).strip()
        if not re.match(r"(?:liste|mostre|leia|consulte|responda|envie|mande)\b", command):
            return None
        if re.match(r"(?:responda|envie|mande)\b", command):
            # Only text AFTER 'dizendo' or ':' is transmitted. Keep punctuation and case.
            found = re.search(
                r"\bchatwoot\b\s+(?:na\s+)?conversa\s+#?([1-9]\d{0,9})"
                r"\s*(?:dizendo\s+|:\s*)(.+)$", message, re.IGNORECASE | re.DOTALL,
            )
            if found:
                return Intent("chatwoot_operation", 1.0, {
                    "action": "send", "conversation_id": int(found[1]), "content": found[2],
                })
            return Intent("chatwoot_operation", 1.0, {"action": "help"})
        if re.search(r"\b(?:mensagens|mensagem)\b", command):
            found = re.search(r"\bconversa\s+#?([1-9]\d{0,9})\b", command)
            return Intent("chatwoot_operation", 1.0, {
                "action": "messages", "conversation_id": int(found[1]),
            } if found else {"action": "help"})
        if re.search(r"\b(?:caixas?|inboxes)\b", command):
            return Intent("chatwoot_operation", 1.0, {"action": "inboxes"})
        if re.search(r"\bconversas?\b", command):
            status = "resolved" if re.search(r"\bresolvidas?\b", command) else "open"
            if re.search(r"\bpendentes?\b", command):
                status = "pending"
            return Intent("chatwoot_operation", 1.0, {"action": "conversations", "status": status})
        return Intent("chatwoot_operation", 1.0, {"action": "help"})
