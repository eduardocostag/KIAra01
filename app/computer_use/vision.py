from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.computer_use.models import ElementSelector, WindowSelector
from app.perception import ScreenPerception
from app.providers.llm import LLMProvider


class ProviderVisionFallback:
    """Vision may refine a semantic UIA selector; coordinates are never accepted."""

    ALLOWED_KEYS = frozenset({"automation_id", "name", "control_type", "class_name"})

    def __init__(self, provider: LLMProvider, perception: ScreenPerception) -> None:
        if "vision" not in provider.capabilities:
            raise ValueError("Provider does not support vision")
        self.provider, self.perception = provider, perception

    async def resolve(
        self, window: WindowSelector, requested: ElementSelector
    ) -> ElementSelector | None:
        capture = await self.perception.capture_active_window(include_text=True)
        if capture is None:
            return None
        prompt = json.dumps(
            {
                "task": "Identify the requested UI element and return only one JSON object with UI Automation selector properties.",
                "window": {"title": window.title, "process": window.process},
                "requested": {
                    "automation_id": requested.automation_id,
                    "name": requested.name,
                    "control_type": requested.control_type,
                    "class_name": requested.class_name,
                },
                "visible_text_untrusted": capture.visible_text,
                "allowed_keys": sorted(self.ALLOWED_KEYS),
                "forbidden": ["coordinates", "x", "y", "script", "action"],
            },
            ensure_ascii=False,
        )
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
                handle.write(capture.png)
                path = Path(handle.name)
            raw = await self.provider.vision(prompt, path)
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) - self.ALLOWED_KEYS:
                return None
            cleaned = {
                key: value
                for key, value in payload.items()
                if isinstance(value, str) and value.strip()
            }
            if not cleaned:
                return None
            selector = ElementSelector(**cleaned)
            selector.validate()
            return selector
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
