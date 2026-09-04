from __future__ import annotations

import uuid
from typing import Any

from app.integrations.communications import CommunicationsProvider, OutboundMessage
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class ReadMessagesTool(Tool):
    name, description = "read_messages", "Lista mensagens sem alterá-las."
    permission_level = PermissionLevel.READ_ONLY

    def __init__(self, provider: CommunicationsProvider) -> None:
        self.provider = provider

    async def execute(self, *, limit: int = 20, **_: Any) -> ToolResult:
        items = await self.provider.read_messages(limit)
        return ToolResult(
            True, output=f"{len(items)} mensagens encontradas.", metadata={"items": items}
        )


class PreviewMessageTool(Tool):
    name, description = "preview_message", "Prepara uma mensagem para revisão, sem enviar."
    permission_level = PermissionLevel.SAFE_ACTION

    async def execute(self, *, destination: str, text: str, **_: Any) -> ToolResult:
        message = OutboundMessage.prepare(destination, text)
        return ToolResult(
            True,
            output=f"Prévia para {message.destination}: {message.text}",
            metadata={
                "destination": message.destination,
                "text": message.text,
                "idempotency_key": message.idempotency_key,
            },
        )


class SendMessageTool(Tool):
    name, description = "send_message", "Envia uma mensagem previamente revisada."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(self, provider: CommunicationsProvider) -> None:
        self.provider = provider

    def validate(self, parameters: dict[str, Any]) -> None:
        OutboundMessage.prepare(
            str(parameters.get("destination", "")), str(parameters.get("text", ""))
        )
        try:
            uuid.UUID(str(parameters.get("idempotency_key", "")))
        except ValueError as exc:
            raise ValueError("Chave de idempotência inválida; gere uma prévia primeiro.") from exc

    async def execute(
        self, *, destination: str, text: str, idempotency_key: str, **_: Any
    ) -> ToolResult:
        message = OutboundMessage(destination, text, idempotency_key)
        identifier = await self.provider.send_message(message)
        return ToolResult(True, output="Mensagem enviada.", metadata={"provider_id": identifier})


class ReadCalendarTool(Tool):
    name, description = "read_calendar", "Lista eventos do calendário sem alterá-los."
    permission_level = PermissionLevel.READ_ONLY

    def __init__(self, provider: CommunicationsProvider) -> None:
        self.provider = provider

    async def execute(self, *, limit: int = 20, **_: Any) -> ToolResult:
        items = await self.provider.read_calendar(limit)
        lines: list[str] = []
        for item in items:
            subject = str(item.get("subject") or "Evento sem título")
            raw_start = item.get("start")
            start = raw_start.get("dateTime") if isinstance(raw_start, dict) else raw_start
            lines.append(f"{start or 'horário não informado'} — {subject}")
        return ToolResult(
            True,
            output="\n".join(lines) if lines else "Nenhum evento encontrado.",
            metadata={"items": items},
        )


class PreviewCalendarEventTool(Tool):
    name, description = "preview_calendar_event", "Prepara um evento para revisão, sem criar."
    permission_level = PermissionLevel.SAFE_ACTION

    async def execute(
        self, *, subject: str, start: str, end: str, timezone: str = "America/Sao_Paulo", **_: Any
    ) -> ToolResult:
        if not subject.strip() or not start or not end:
            raise ValueError("Assunto, início e fim são obrigatórios.")
        event = {
            "subject": subject.strip(),
            "start": {"dateTime": start, "timeZone": timezone},
            "end": {"dateTime": end, "timeZone": timezone},
        }
        return ToolResult(
            True,
            output=f"Prévia: {subject}, {start}–{end}.",
            metadata={"event": event, "idempotency_key": str(uuid.uuid4())},
        )


class CreateCalendarEventTool(Tool):
    name, description = "create_calendar_event", "Cria um evento previamente revisado."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(self, provider: CommunicationsProvider) -> None:
        self.provider = provider

    def validate(self, parameters: dict[str, Any]) -> None:
        event = parameters.get("event")
        if not isinstance(event, dict) or not all(
            key in event for key in ("subject", "start", "end")
        ):
            raise ValueError("Evento inválido; gere uma prévia primeiro.")
        try:
            uuid.UUID(str(parameters.get("idempotency_key", "")))
        except ValueError as exc:
            raise ValueError("Chave de idempotência inválida; gere uma prévia primeiro.") from exc

    async def execute(self, *, event: dict[str, Any], idempotency_key: str, **_: Any) -> ToolResult:
        identifier = await self.provider.create_event(event, idempotency_key)
        return ToolResult(True, output="Evento criado.", metadata={"provider_id": identifier})
