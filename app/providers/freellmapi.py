from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.providers.remote import (
    OllamaTransport,
    OpenAICompatibleProvider,
    ProviderConfigurationError,
)


class FreeLLMAPIProvider(OpenAICompatibleProvider):
    """Text client for the self-hosted FreeLLMAPI router (which may forward to cloud)."""

    def __init__(
        self,
        api_key: str,
        model: str = "auto",
        base_url: str = "http://127.0.0.1:3001/v1",
        timeout_seconds: float = 30.0,
        max_output_tokens: int = 4096,
        transport: OllamaTransport | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        try:
            loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
        except ValueError:
            loopback = parsed.hostname == "localhost"
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or (parsed.scheme == "http" and not loopback)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/v1"
        ):
            raise ProviderConfigurationError(
                "FreeLLMAPI requer URL /v1 sem credenciais; HTTP somente em loopback."
            )
        if not api_key.strip():
            raise ProviderConfigurationError("FREELLMAPI_API_KEY não foi definida.")
        super().__init__(
            model=model or "auto",
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
            transport=transport,
            vision_enabled=False,
            follow_redirects=False,
        )
