from __future__ import annotations

import asyncio

from app.config import load_settings
from app.core.event_bus import EventBus
from app.perception.screen import PerceptionOptions, ScreenPerception
from app.providers.factory import build_llm_provider


async def main() -> None:
    settings = load_settings()
    perception = ScreenPerception(EventBus(), PerceptionOptions.from_settings(settings))
    capture = await perception.capture_virtual_desktop()
    if capture is None or not capture.png:
        raise RuntimeError("captura visual indisponível")
    provider = build_llm_provider(settings, {})
    description = await provider.vision_bytes(
        "Descreva objetivamente em português os elementos visíveis nesta captura. Não invente.",
        capture.png,
    )
    print(description)


if __name__ == "__main__":
    asyncio.run(main())
