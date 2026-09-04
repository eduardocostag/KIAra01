from __future__ import annotations

from app.perception.screen import ScreenPerception


class EphemeralVisualStateVerifier:
    """Hashes a downsampled active-window state; raw pixels are never retained."""

    def __init__(self, perception: ScreenPerception, *, change_threshold: float = 0.02) -> None:
        if not 0 <= change_threshold <= 1:
            raise ValueError("change_threshold must be between 0 and 1")
        self.perception = perception
        self.change_threshold = change_threshold

    async def signature(self) -> str | None:
        capture = await self.perception.capture_active_window()
        if capture is None:
            return None
        compact = ScreenPerception._perceptual_signature(capture.png)
        return compact.hex()

    def changed(self, before: str, after: str) -> bool:
        try:
            previous = bytes.fromhex(before)
            current = bytes.fromhex(after)
        except ValueError:
            return before != after
        difference = ScreenPerception._signature_difference(previous, current)
        return difference >= self.change_threshold
