from pathlib import Path

import pytest

from app.computer_use.models import ElementSelector, WindowSelector
from app.computer_use.vision import ProviderVisionFallback
from app.perception.screen import ScreenCapture
from app.providers.llm import LLMProvider


class VisionProvider(LLMProvider):
    def __init__(self, response):
        self.response = response

    @property
    def capabilities(self):
        return frozenset({"generate", "vision"})

    async def generate(self, prompt):
        return ""

    async def vision(self, prompt: str, image: Path) -> str:
        assert image.exists()
        return self.response


class Perception:
    async def capture_active_window(self, include_text=False):
        return ScreenCapture(b"png", 10, 10, "untrusted")


@pytest.mark.asyncio
async def test_vision_fallback_returns_only_semantic_selector():
    fallback = ProviderVisionFallback(
        VisionProvider('{"name":"Salvar","control_type":"Button"}'), Perception()
    )
    selector = await fallback.resolve(WindowSelector(title="App"), ElementSelector(name="save"))
    assert selector == ElementSelector(name="Salvar", control_type="Button")


@pytest.mark.asyncio
async def test_vision_fallback_rejects_coordinates():
    fallback = ProviderVisionFallback(VisionProvider('{"name":"Salvar","x":"10"}'), Perception())
    assert await fallback.resolve(WindowSelector(title="App"), ElementSelector(name="save")) is None
