from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import urllib.error
import urllib.request
from collections.abc import AsyncIterator, Callable
from functools import partial
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

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        stream_method = getattr(self._client.responses, "stream", None)
        if stream_method is None:
            async for delta in super().stream(prompt):
                yield delta
            return
        async with stream_method(model=self.model, input=prompt) as stream:
            async for event in stream:
                if getattr(event, "type", "") == "response.output_text.delta":
                    delta = str(getattr(event, "delta", ""))
                    if delta:
                        yield delta

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


class OpenAICompatibleProvider(LLMProvider):
    """Provider leve para endpoints OpenAI-compatible, sem SDK obrigatório."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 30.0,
        transport: OllamaTransport | None = None,
        vision_enabled: bool = True,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("A chave do provedor remoto não foi definida.")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.vision_enabled = vision_enabled
        self._transport = transport or partial(_post_authenticated_json, api_key=self.api_key)
        self._native_streaming = transport is None

    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate", "vision"} if self.vision_enabled else {"generate"})

    async def generate(self, prompt: str) -> str:
        return await self._complete(
            [{"role": "user", "content": prompt}]
        )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        if not self._native_streaming:
            async for delta in super().stream(prompt):
                yield delta
            return
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        async for event in _stream_http_json(
            f"{self.base_url}/chat/completions",
            payload,
            self.timeout_seconds,
            api_key=self.api_key,
            sse=True,
        ):
            choices = event.get("choices", [])
            if not choices or not isinstance(choices[0], dict):
                continue
            delta = choices[0].get("delta", {})
            content = delta.get("content") if isinstance(delta, dict) else None
            if content:
                yield str(content)

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        if not self.vision_enabled:
            raise NotImplementedError("Este provider remoto não oferece visão.")
        encoded = base64.b64encode(image).decode("ascii")
        return await self._complete(
            [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{media_type};base64,{encoded}"
                    }},
                ],
            }]
        )

    async def _complete(self, messages: list[dict[str, Any]]) -> str:
        payload = {"model": self.model, "messages": messages, "stream": False}
        result = await asyncio.wait_for(
            asyncio.to_thread(
                self._transport,
                f"{self.base_url}/chat/completions",
                payload,
                self.timeout_seconds,
            ),
            timeout=self.timeout_seconds,
        )
        choices = result.get("choices", [])
        if not choices or not isinstance(choices[0], dict):
            raise RuntimeError("O provedor remoto retornou uma resposta vazia.")
        message = choices[0].get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise RuntimeError("O provedor remoto não retornou conteúdo.")
        return str(content)


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


def _post_authenticated_json(
    url: str, payload: dict[str, Any], timeout: float, api_key: str | None = None
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or ''}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Provedor remoto HTTP {exc.code}: {detail}") from exc


async def _stream_http_json(
    url: str,
    payload: dict[str, Any],
    timeout: float,
    *,
    api_key: str | None = None,
    sse: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Bridge a blocking urllib byte stream to asyncio without buffering the response."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | BaseException | None] = asyncio.Queue()

    def worker() -> None:
        headers = {"Content-Type": "application/json"}
        if api_key is not None:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if sse:
                        if not line.startswith("data:"):
                            continue
                        line = line[5:].strip()
                        if line == "[DONE]":
                            break
                    loop.call_soon_threadsafe(queue.put_nowait, json.loads(line))
        except BaseException as exc:  # noqa: BLE001 - cross-thread error transport
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    asyncio.create_task(asyncio.to_thread(worker))
    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, BaseException):
            raise item
        yield item


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
        self._native_streaming = transport is _post_json

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

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        if not self._native_streaming:
            async for delta in super().stream(prompt):
                yield delta
            return
        payload = self._payload(prompt)
        payload["stream"] = True
        async for event in _stream_http_json(
            f"{self.base_url}/api/generate", payload, self.timeout_seconds
        ):
            delta = event.get("response")
            if delta:
                yield str(delta)

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
