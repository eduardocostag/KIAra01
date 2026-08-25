from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import load_settings
from app.core.event_bus import EventBus
from app.perception.analysis import screen_analysis_prompt
from app.perception.screen import PerceptionOptions, ScreenPerception
from app.providers.factory import build_llm_provider


async def main(image_path: Path | None = None) -> None:
    settings = load_settings()
    if image_path is None:
        perception = ScreenPerception(EventBus(), PerceptionOptions.from_settings(settings))
        capture = await perception.capture_virtual_desktop()
        if capture is None or not capture.png:
            raise RuntimeError("captura visual indisponível")
        image = capture.png
    else:
        image = image_path.read_bytes()
    provider = build_llm_provider(settings, {})
    description = await provider.vision_bytes(
        screen_analysis_prompt(application=None, window_title=None),
        image,
    )
    if not description.strip():
        raise RuntimeError("modelo visual retornou resposta vazia")
    print(description)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="?", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.image))
