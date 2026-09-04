from __future__ import annotations

from typing import Any, ClassVar

from app.browser import BrowserSession
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class BrowserNavigateTool(Tool):
    name = "browser_navigate"
    description = "Navega para uma página HTTPS usando Playwright."
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"url": {"type": "string", "format": "uri", "maxLength": 2048}},
        "required": ["url"],
    }

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"url"}:
            raise ValueError("A navegaÃ§Ã£o aceita somente o campo url.")
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
    permission_level = PermissionLevel.SAFE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "label": {"type": "string", "maxLength": 200},
            "value": {"type": "string", "maxLength": 20000},
        },
        "required": ["label", "value"],
    }

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"label", "value"}:
            raise ValueError("Preenchimento requer somente label e value.")
        if not isinstance(parameters["label"], str) or not parameters["label"].strip():
            raise ValueError("Informe o rÃ³tulo acessÃ­vel do campo.")
        if not isinstance(parameters["value"], str) or len(parameters["value"]) > 20_000:
            raise ValueError("Valor invÃ¡lido ou acima do limite.")

    def audit_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": parameters.get("label"),
            "value_chars": len(str(parameters.get("value", ""))),
        }

    async def execute(self, *, label: str, value: str, **_: Any) -> ToolResult:
        await self.browser.fill(label=label, value=value)
        return ToolResult(True, output=f"Campo {label} preenchido; formulário não enviado.")


class BrowserClickTool(Tool):
    name = "browser_click"
    description = "Clica em um elemento da página pelo papel e nome acessíveis."
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "role": {"type": "string", "maxLength": 40},
            "name": {"type": "string", "maxLength": 300},
        },
        "required": ["role", "name"],
    }

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"role", "name"}:
            raise ValueError("Clique requer somente role e name.")
        if not all(
            isinstance(parameters[key], str) and parameters[key].strip() for key in parameters
        ):
            raise ValueError("Papel e nome acessíveis são obrigatórios.")

    async def execute(self, *, role: str, name: str, **_: Any) -> ToolResult:
        page = await self.browser.click(role=role, name=name)
        return ToolResult(True, output=f"Clique concluído. Página atual: {page.title} — {page.url}")


class BrowserReadTool(Tool):
    name = "browser_read"
    description = "Lê o texto visível da página atual."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {"properties": {}, "required": []}

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    async def execute(self, **_: Any) -> ToolResult:
        page = await self.browser.snapshot()
        return ToolResult(
            True,
            output=f"{page.title} — {page.url}\n\n{page.text}",
            metadata={"url": page.url, "title": page.title},
        )


class GoogleMapsBusinessSearchTool(Tool):
    name = "google_maps_business_search"
    description = "Pesquisa empresas no Google Maps e lê telefone, endereço e site de cada ficha."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "query": {"type": "string", "maxLength": 300},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["query", "limit"],
    }

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"query", "limit"}:
            raise ValueError("Pesquisa requer somente query e limit.")
        if not isinstance(parameters["query"], str) or not parameters["query"].strip():
            raise ValueError("Informe a consulta local.")
        if not isinstance(parameters["limit"], int) or not 1 <= parameters["limit"] <= 50:
            raise ValueError("O limite deve estar entre 1 e 50.")

    async def execute(self, *, query: str, limit: int, **_: Any) -> ToolResult:
        businesses = await self.browser.search_google_maps_businesses(query=query, limit=limit)
        return ToolResult(
            True,
            output=f"{len(businesses)} ficha(s) do Google Maps lida(s).",
            metadata={"businesses": businesses},
        )


class OrganicConsumerSearchTool(Tool):
    name = "organic_consumer_search"
    description = "Localiza publicações públicas com intenção B2C sem coletar contatos pessoais."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "query": {"type": "string", "maxLength": 200},
            "location": {"type": "string", "maxLength": 120},
            "limit": {"type": "integer", "minimum": 1, "maximum": 40},
        },
        "required": ["query", "location", "limit"],
    }

    def __init__(self, browser: BrowserSession) -> None:
        self.browser = browser

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"query", "location", "limit"}:
            raise ValueError("Pesquisa orgânica requer query, location e limit.")
        if not str(parameters["query"]).strip() or not str(parameters["location"]).strip():
            raise ValueError("Nicho e localização são obrigatórios.")
        if not isinstance(parameters["limit"], int) or not 1 <= parameters["limit"] <= 40:
            raise ValueError("O limite deve estar entre 1 e 40.")

    async def execute(self, *, query: str, location: str, limit: int, **_: Any) -> ToolResult:
        results = await self.browser.search_public_consumer_intent(
            query=query, location=location, limit=limit
        )
        return ToolResult(
            True,
            output=f"{len(results)} sinal(is) público(s) localizado(s).",
            metadata={"results": results},
        )
