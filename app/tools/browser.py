from __future__ import annotations

from typing import Any

from app.browser import BrowserSession
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class BrowserNavigateTool(Tool):
    name = "browser_navigate"
    description = "Navega para uma página HTTPS usando Playwright."
    permission_level = PermissionLevel.SAFE_ACTION

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        self.browser.validate_url(
            str(parameters.get("url", "")),
            allow_private_hosts=self.browser.allow_private_hosts,
        )

    async def execute(self, *, url: str, **_: Any) -> ToolResult:
        page = await self.browser.navigate(url)
        return ToolResult(True, output=f"{page.title} — {page.url}", metadata={"text": page.text})


class BrowserFillTool(Tool):
    name = "browser_fill"
    description = "Preenche um campo identificado por seu rótulo acessível."
    permission_level = PermissionLevel.SENSITIVE_ACTION

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    async def execute(self, *, label: str, value: str, **_: Any) -> ToolResult:
        await self.browser.fill(label=label, value=value)
        return ToolResult(True, output=f"Campo {label} preenchido; formulário não enviado.")
