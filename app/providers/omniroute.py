"""Opt-in text adapter for a configured OmniRoute OpenAI-compatible gateway.

Running the router locally does not imply that its selected model is local or
free. Select the model/combo explicitly and configure its upstream cost policy
in OmniRoute before enabling customer automation.
"""
from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit

from app.providers.remote import (
    OllamaTransport,
    OpenAICompatibleProvider,
    ProviderConfigurationError,
)


class OmniRouteProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "http://127.0.0.1:20128/v1",
        timeout_seconds: float = 45.0,
        max_output_tokens: int = 1024,
        transport: OllamaTransport | None = None,
    ) -> None:
        try:
            parsed = urlsplit(base_url)
            # Force validation of malformed/out-of-range ports before any I/O.
            _ = parsed.port
            try:
                loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
            except ValueError:
                loopback = parsed.hostname == "localhost"
            valid = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and (parsed.scheme == "https" or loopback)
                and parsed.username is None
                and parsed.password is None
                and not parsed.query
                and not parsed.fragment
                and parsed.path.rstrip("/") == "/v1"
            )
        except ValueError:
            valid = False
        if not valid:
            raise ProviderConfigurationError(
                "OmniRoute requer URL /v1 sem credenciais; HTTP somente em loopback."
            )
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderConfigurationError("OMNIROUTE_API_KEY não foi definida.")
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ProviderConfigurationError("Selecione explicitamente OMNIROUTE_MODEL.")
        super().__init__(
            model=model.strip(),
            api_key=api_key.strip(),
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            transport=transport,
            vision_enabled=False,
            follow_redirects=False,
        )

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        """Preserve caller system/user boundaries without exposing tools or vision."""
        if not messages or len(messages) > 30:
            raise ValueError("Informe de 1 a 30 mensagens para o OmniRoute.")
        checked = []
        for item in messages:
            if (not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"}
                    or not isinstance(item.get("content"), str)
                    or len(item["content"]) > 20_000):
                raise ValueError("Mensagem inválida para o OmniRoute.")
            checked.append({"role": item["role"], "content": item["content"]})
        return await self._complete(checked)
