from __future__ import annotations

from typing import Any, ClassVar

from app.integrations.email import EmailService
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class DraftEmailTool(Tool):
    name = "draft_email"
    description = "Cria e persiste um rascunho de e-mail sem enviá-lo."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "to": {"type": "string", "maxLength": 320},
            "subject": {"type": "string", "maxLength": 300},
            "body": {"type": "string", "maxLength": 20000},
        },
        "required": ["to", "subject", "body"],
    }

    def __init__(self, service: EmailService) -> None:
        self.service = service

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"to", "subject", "body"}:
            raise ValueError("Informe to, subject e body.")
        if "@" not in str(parameters["to"]) or not str(parameters["subject"]).strip():
            raise ValueError("Destinatário ou assunto inválido.")
        if not str(parameters["body"]).strip() or len(str(parameters["body"])) > 20_000:
            raise ValueError("Corpo vazio ou acima do limite.")

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        recipient = str(parameters.get("to", ""))
        domain = recipient.rsplit("@", 1)[-1] if "@" in recipient else "invalid"
        return {
            "recipient_domain": domain,
            "subject_chars": len(str(parameters.get("subject", ""))),
            "body_chars": len(str(parameters.get("body", ""))),
        }

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
    plannable = False
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"draft_id": {"type": "string"}},
        "required": ["draft_id"],
    }

    def __init__(self, service: EmailService) -> None:
        self.service = service

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"draft_id"} or not isinstance(parameters["draft_id"], str):
            raise ValueError("Informe somente draft_id.")

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
        return ToolResult(
            True, output=f"{len(items)} e-mails encontrados.", metadata={"items": items}
        )
