from __future__ import annotations

import hashlib

from app.perception.screen import ScreenPerception


class EphemeralVisualStateVerifier:
    """Hashes a downsampled active-window state; raw pixels are never retained."""

    def __init__(self, perception: ScreenPerception) -> None:
        self.perception = perception

    async def signature(self) -> str | None:
        capture = await self.perception.capture_active_window()
        if capture is None:
            return None
        compact = ScreenPerception._perceptual_signature(capture.png)
        return hashlib.sha256(compact).hexdigest()
