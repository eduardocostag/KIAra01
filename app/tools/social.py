from __future__ import annotations

import re
from typing import Any, ClassVar

from app.browser import BrowserSession
from app.leads.policy import ProspectingPolicyEngine
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

    def __init__(
        self, browser: BrowserSession, policy_engine: ProspectingPolicyEngine | None = None
    ) -> None:
        self.browser = browser
        self.policy_engine = policy_engine

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
        reservation_id = ""
        if self.policy_engine is not None:
            decision = self.policy_engine.reserve(recipient, operation_id=platform, automatic=False)
            if not decision.allowed:
                return ToolResult(False, error=decision.reason)
            reservation_id = decision.reservation_id
        try:
            output = await self.browser.send_social_message(
                platform=platform, recipient=recipient, message=text
            )
        except Exception:
            if reservation_id:
                self.policy_engine.complete(reservation_id, sent=False)
            raise
        if reservation_id:
            self.policy_engine.complete(reservation_id, sent=True)
        return ToolResult(True, output=output)
