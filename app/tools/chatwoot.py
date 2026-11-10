from __future__ import annotations

import json
from typing import Any, ClassVar

from app.integrations.chatwoot import ChatwootClient, positive_id, validate_content
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class ChatwootReadTool(Tool):
    name = "chatwoot_read"
    description = "Le caixas, conversas e mensagens Chatwoot da conta configurada."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "type": "object", "properties": {
            "action": {"type": "string", "enum": ["inboxes", "conversations", "messages"]},
            "conversation_id": {"type": "integer", "minimum": 1},
            "status": {"type": "string", "enum": ["all", "open", "resolved", "pending", "snoozed"]},
            "page": {"type": "integer", "minimum": 1, "maximum": 10000},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "before": {"type": "integer", "minimum": 1},
        }, "required": ["action"], "additionalProperties": False,
    }

    def __init__(self, client: ChatwootClient) -> None:
        self.client = client

    def validate(self, parameters: dict[str, Any]) -> None:
        if parameters.keys() - self.schema["properties"].keys():
            raise ValueError("Parametro Chatwoot desconhecido.")
        if parameters.get("action") not in {"inboxes", "conversations", "messages"}:
            raise ValueError("Acao Chatwoot invalida.")
        if parameters["action"] == "messages":
            positive_id(parameters.get("conversation_id"), "conversation_id")
        self.client._limit(parameters.get("limit", 20))

    async def execute(self, *, action: str, **parameters: Any) -> ToolResult:
        self.validate({"action": action, **parameters})
        limit = parameters.get("limit", 20)
        if action == "inboxes":
            items = await self.client.list_inboxes(limit=limit)
        elif action == "conversations":
            items = await self.client.list_conversations(status=parameters.get("status", "open"),
                                                        page=parameters.get("page", 1), limit=limit)
        else:
            items = await self.client.list_messages(parameters["conversation_id"],
                                                   before=parameters.get("before"), limit=limit)
        return ToolResult(True, output=json.dumps(items, ensure_ascii=False), metadata={"items": items})


class ChatwootSendMessageTool(Tool):
    name = "chatwoot_send_message"
    description = "Envia resposta textual Chatwoot apos confirmacao humana; sem retry automatico."
    permission_level = PermissionLevel.CRITICAL_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "type": "object", "properties": {
            "conversation_id": {"type": "integer", "minimum": 1},
            "content": {"type": "string", "minLength": 1, "maxLength": 10000},
        }, "required": ["conversation_id", "content"], "additionalProperties": False,
    }

    def __init__(self, client: ChatwootClient) -> None:
        self.client = client

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"conversation_id", "content"}:
            raise ValueError("Envio requer conversation_id e content.")
        positive_id(parameters["conversation_id"], "conversation_id")
        validate_content(parameters["content"])

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        content = parameters.get("content")
        return {"conversation_id": parameters.get("conversation_id"),
                "content_length": len(content) if isinstance(content, str) else 0}

    def confirmation_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return self.audit_parameters(parameters)

    async def execute(self, *, conversation_id: int, content: str) -> ToolResult:
        self.validate({"conversation_id": conversation_id, "content": content})
        result = await self.client.send_message(conversation_id, content)
        return ToolResult(True, output="Resposta registrada no Chatwoot; entrega depende do canal.",
                          metadata=result)
