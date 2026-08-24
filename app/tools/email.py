from __future__ import annotations

from typing import Any

from app.integrations.email import EmailService
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class DraftEmailTool(Tool):
    name = "draft_email"
    description = "Cria e persiste um rascunho de e-mail sem enviá-lo."
    permission_level = PermissionLevel.SAFE_ACTION

    def __init__(self, service: EmailService) -> None:
        self.service = service

    async def execute(self, *, to: str, subject: str, body: str, **_: Any) -> ToolResult:
        draft = self.service.draft(to, subject, body)
        return ToolResult(
            True,
            output=(
                f"Prévia do rascunho {draft.id}\nPara: {draft.to}\n"
                f"Assunto: {draft.subject}\n\n{draft.body}"
            ),
            metadata={"draft_id": draft.id},
        )


class SendEmailTool(Tool):
    name = "send_email"
    description = "Envia um rascunho previamente revisado."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(self, service: EmailService) -> None:
        self.service = service

    async def execute(self, *, draft_id: str, **_: Any) -> ToolResult:
        provider_id = await self.service.send(draft_id)
        return ToolResult(True, output="E-mail enviado.", metadata={"provider_id": provider_id})


class ReadEmailTool(Tool):
    name = "read_email"
    description = "Lista e-mails sem alterar a caixa postal."
    permission_level = PermissionLevel.READ_ONLY

    def __init__(self, service: EmailService) -> None:
        self.service = service

    async def execute(self, *, limit: int = 20, **_: Any) -> ToolResult:
        provider = self.service.provider
        if provider is None or not hasattr(provider, "read"):
            return ToolResult(False, error="Leitura de e-mail não configurada.")
        items = await provider.read(limit)
        return ToolResult(True, output=f"{len(items)} e-mails encontrados.", metadata={"items": items})
