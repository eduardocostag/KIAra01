from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.providers.llm import LLMProvider


class ProviderConfigurationError(ValueError):
    """Raised when a selected provider lacks required safe configuration."""


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("OPENAI_API_KEY não foi definida.")
        self.model = model
        self.timeout_seconds = timeout_seconds
        if client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise ProviderConfigurationError(
                    'Instale o extra OpenAI com: pip install -e ".[openai]"'
                ) from exc
            client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self._client = client

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate", "vision"})

    async def generate(self, prompt: str) -> str:
        response = await asyncio.wait_for(
            self._client.responses.create(model=self.model, input=prompt),
            timeout=self.timeout_seconds,
        )
        return str(response.output_text)

    async def vision(self, prompt: str, image: Path) -> str:
        media_type = mimetypes.guess_type(image.name)[0] or "image/png"
        return await self.vision_bytes(prompt, image.read_bytes(), media_type=media_type)

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        encoded = base64.b64encode(image).decode("ascii")
        response = await asyncio.wait_for(
            self._client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:{media_type};base64,{encoded}",
                            },
                        ],
                    }
                ],
            ),
            timeout=self.timeout_seconds,
        )
        return str(response.output_text)

    async def aclose(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()


OllamaTransport = Callable[[str, dict[str, Any], float], dict[str, Any]]


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 60.0,
        vision_enabled: bool = False,
        vision_model: str | None = None,
        vision_options: dict[str, Any] | None = None,
        generation_options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
        transport: OllamaTransport = _post_json,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.vision_enabled = vision_enabled
        self.vision_model = vision_model or (model if vision_enabled else None)
        self.vision_options = dict(vision_options or {})
        self.generation_options = dict(generation_options or {})
        self.keep_alive = keep_alive
        self._transport = transport

    @property
    def capabilities(self) -> frozenset[str]:
        values = {"generate"}
        if self.vision_enabled and self.vision_model:
            values.add("vision")
        return frozenset(values)

    async def _generate(self, payload: dict[str, Any]) -> str:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                self._transport,
                f"{self.base_url}/api/generate",
                payload,
                self.timeout_seconds,
            ),
            timeout=self.timeout_seconds,
        )
        return str(result.get("response", ""))

    async def _chat(self, payload: dict[str, Any]) -> str:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                self._transport,
                f"{self.base_url}/api/chat",
                payload,
                self.timeout_seconds,
            ),
            timeout=self.timeout_seconds,
        )
        message = result.get("message", {})
        if isinstance(message, dict) and "content" in message:
            return str(message["content"])
        return str(result.get("response", ""))

    async def generate(self, prompt: str) -> str:
        return await self._generate(self._payload(prompt))

    async def vision(self, prompt: str, image: Path) -> str:
        return await self.vision_bytes(prompt, image.read_bytes())

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        del media_type
        if not self.vision_enabled or not self.vision_model:
            raise NotImplementedError("Este provider não oferece visão.")
        encoded = base64.b64encode(image).decode("ascii")
        # Do not reuse the text model's large context options for vision: on
        # modest Windows machines that can exhaust RAM/VRAM and Ollama returns 500.
        payload: dict[str, Any] = {
            "model": self.vision_model,
            "messages": [{"role": "user", "content": prompt, "images": [encoded]}],
            "stream": False,
            "keep_alive": 0,
        }
        if self.vision_options:
            payload["options"] = self.vision_options
        return await self._chat(payload)

    def _payload(
        self,
        prompt: str,
        *,
        images: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model or self.model, "prompt": prompt, "stream": False}
        if self.generation_options:
            payload["options"] = self.generation_options
        if self.keep_alive is not None:
            payload["keep_alive"] = self.keep_alive
        if images:
            payload["images"] = images
        return payload
