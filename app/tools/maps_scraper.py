from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from app.integrations.maps_scraper import MapsScraperClient, MapsScraperError, validate_search
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class GoogleMapsScraperTool(Tool):
    name = "google_maps_business_search"
    description = "Pesquisa fichas públicas via Google Maps Scraper local com limites de execução."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "query": {"type": "string", "maxLength": 300},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["query", "limit"],
    }

    def __init__(
        self, client: MapsScraperClient,
        verify_whatsapp: Callable[[str], Awaitable[bool]] | None = None,
        fallback_search: Callable[..., Awaitable[list[dict[str, Any]]]] | None = None,
    ) -> None:
        self.client = client
        self.verify_whatsapp = verify_whatsapp
        self.fallback_search = fallback_search

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"query", "limit"}:
            raise ValueError("Pesquisa requer somente query e limit.")
        validate_search(parameters["query"], parameters["limit"])

    async def execute(self, *, query: str, limit: int, **_: Any) -> ToolResult:
        validate_search(query, limit)
        try:
            businesses = await self.client.search(query=query, limit=limit)
        except MapsScraperError as exc:
            return await self._fallback(query, limit, str(exc))
        if not businesses and self.fallback_search is not None:
            return await self._fallback(query, limit, "A CLI Maps não retornou fichas.")
        if self.verify_whatsapp is not None:
            for business in businesses:
                if self.client.kill_switch.stopped:
                    return ToolResult(False, error="Pesquisa interrompida pelo kill switch.")
                if business["phone"] and not business["website"]:
                    try:
                        valid = await asyncio.wait_for(
                            self.verify_whatsapp(business["phone"]), timeout=30,
                        )
                    except Exception:  # noqa: BLE001 - failed verification is never confirmation
                        valid = False
                    if valid:
                        business["whatsapp"] = business["phone"]
        return ToolResult(
            True, output=f"{len(businesses)} ficha(s) lida(s) pelo Google Maps Scraper.",
            metadata={"businesses": businesses, "backend": "gosom/google-maps-scraper"},
        )

    async def _fallback(self, query: str, limit: int, reason: str) -> ToolResult:
        if self.client.kill_switch.stopped or self.fallback_search is None:
            return ToolResult(False, error=reason)
        try:
            businesses = await self.fallback_search(query=query, limit=limit)
        except Exception:  # noqa: BLE001 - Cancellation propagates; provider failures remain explicit.
            return ToolResult(False, error=f"{reason} A pesquisa alternativa pelo navegador também falhou.")
        if self.client.kill_switch.stopped:
            return ToolResult(False, error="Pesquisa interrompida pelo kill switch.")
        return ToolResult(
            True, output=f"{len(businesses)} ficha(s) lida(s) pelo navegador alternativo.",
            metadata={"businesses": businesses, "backend": "kiara_browser",
                      "warnings": [reason]},
        )
