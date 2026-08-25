from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from app.providers.llm import LLMProvider

StreamEventKind = Literal["started", "text_delta", "completed"]


@dataclass(frozen=True, slots=True)
class StreamEvent:
    kind: StreamEventKind
    delta: str = ""
    text: str = ""


async def provider_stream_events(provider: LLMProvider, prompt: str) -> AsyncIterator[StreamEvent]:
    """Convert provider deltas into the stable event contract consumed by core clients."""
    yield StreamEvent("started")
    parts: list[str] = []
    async for delta in provider.stream(prompt):
        if not delta:
            continue
        parts.append(delta)
        yield StreamEvent("text_delta", delta=delta)
    yield StreamEvent("completed", text="".join(parts))
