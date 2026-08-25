from __future__ import annotations

import re
from typing import Any, ClassVar

from app.browser import BrowserSession
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class SendSocialMessageTool(Tool):
    name = "send_social_message"
    description = "Envia mensagem social a um destinatário explícito após confirmação humana."
    permission_level = PermissionLevel.CRITICAL_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "platform": {"type": "string"},
            "recipient": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["platform", "recipient", "text"],
    }

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        platform = str(parameters.get("platform", "")).casefold()
        recipient = str(parameters.get("recipient", ""))
        text = str(parameters.get("text", ""))
        if platform not in {"instagram", "whatsapp", "telegram"}:
            raise ValueError("Plataforma não suportada.")
        if not re.fullmatch(r"[@+\w. -]{2,100}", recipient, re.UNICODE):
            raise ValueError("Destinatário inválido.")
        if not text.strip() or len(text) > 4000:
            raise ValueError("Mensagem vazia ou acima de 4000 caracteres.")

    async def execute(self, *, platform: str, recipient: str, text: str, **_: Any) -> ToolResult:
        output = await self.browser.send_social_message(
            platform=platform, recipient=recipient, message=text
        )
        return ToolResult(True, output=output)
