from __future__ import annotations

import asyncio
import hashlib
import io
import re
import time
from dataclasses import asdict, dataclass
from typing import Protocol

from app.config import Settings
from app.core.event_bus import EventBus
from app.models import ScreenContext
from app.perception.windows import WindowSnapshot, inspect_active_window


class WindowInspector(Protocol):
    def __call__(self) -> WindowSnapshot: ...


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    """An ephemeral in-memory capture of only the active window."""

    png: bytes
    width: int
    height: int
    visible_text: str | None = None


@dataclass(frozen=True, slots=True)
class PerceptionOptions:
    enabled: bool = True
    monitor_active_window: bool = True
    capture_active_window: bool = True
    ui_automation_enabled: bool = False
    ocr_enabled: bool = False
    poll_interval_seconds: float = 1.0
    content_change_enabled: bool = False
    content_change_threshold: float = 0.18
    content_change_cooldown_seconds: float = 5.0
    error_detection_enabled: bool = False
    vision_max_edge: int = 896

    @classmethod
    def from_settings(cls, settings: Settings) -> PerceptionOptions:
        return cls(
            enabled=bool(settings.get("screen.enabled", True)),
            monitor_active_window=bool(settings.get("screen.monitor_active_window", True)),
            capture_active_window=bool(settings.get("screen.capture_active_window", True)),
            ui_automation_enabled=bool(settings.get("screen.ui_automation_enabled", False)),
            ocr_enabled=bool(settings.get("screen.ocr_enabled", False)),
            poll_interval_seconds=float(settings.get("screen.poll_interval_seconds", 1.0)),
            content_change_enabled=bool(settings.get("screen.content_change_enabled", False)),
            content_change_threshold=float(settings.get("screen.content_change_threshold", 0.18)),
            content_change_cooldown_seconds=float(
                settings.get("screen.content_change_cooldown_seconds", 5.0)
            ),
            error_detection_enabled=bool(settings.get("screen.error_detection_enabled", False)),
            vision_max_edge=int(settings.get("screen.vision_max_edge", 896)),
        )


class ScreenPerception:
    CONTEXT_CHANGED = "screen.context_changed"
    SCREEN_CHANGED = "SCREEN_CHANGED"
    ERROR_DETECTED = "ERROR_DETECTED"

    def __init__(
        self,
        event_bus: EventBus,
        options: PerceptionOptions | None = None,
        inspector: WindowInspector = inspect_active_window,
    ) -> None:
        self.event_bus = event_bus
        self.options = options or PerceptionOptions()
        self._inspector = inspector
        self._last_identity: tuple[str | None, str | None, str | None] | None = None
        self._last_visual_signature: bytes | None = None
        self._last_screen_event_at = float("-inf")
        self._last_error_fingerprint: str | None = None
        self._last_error_event_at = float("-inf")
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def get_context(self, *, include_visible_text: bool = False) -> ScreenContext:
        if not self.options.enabled:
            return ScreenContext()
        snapshot = await asyncio.to_thread(self._inspector)
        context = snapshot.context
        if include_visible_text and self.options.ui_automation_enabled and snapshot.handle:
            context.visible_text = await asyncio.to_thread(self._read_ui_automation, snapshot.handle)
        return context

    async def poll_once(self) -> bool:
        """Publish meaningful window changes; background polling never captures pixels."""
        if not self.options.enabled or not self.options.monitor_active_window:
            return False
        snapshot = await asyncio.to_thread(self._inspector)
        context = snapshot.context
        identity = (context.active_process, context.active_application, context.window_title)
        context_changed = identity != self._last_identity
        if context_changed:
            self._last_identity = identity
            self._last_visual_signature = None
            await self.event_bus.publish(self.CONTEXT_CHANGED, asdict(context))
        visual_changed = await self._detect_visual_change(snapshot, identity)
        title = context.window_title or ""
        if re.search(r"\b(error|erro|failed|falha|alerta|critical|crítico)\b", title, re.IGNORECASE):
            await self._publish_error(
                source="window_title", title=title, message=title, identity=identity
            )
        if self.options.error_detection_enabled and self.options.ui_automation_enabled:
            alert = await asyncio.to_thread(self._read_ui_automation_alert, snapshot.handle)
            if alert:
                await self._publish_error(identity=identity, **alert)
        return context_changed or visual_changed

    async def _detect_visual_change(
        self,
        snapshot: WindowSnapshot,
        identity: tuple[str | None, str | None, str | None],
    ) -> bool:
        """Compare an ephemeral active-window sample with its non-reversible signature."""
        if not self.options.content_change_enabled or snapshot.minimized or not snapshot.bounds:
            return False
        left, top, width, height = snapshot.bounds
        if width <= 0 or height <= 0:
            return False
        try:
            png = await asyncio.to_thread(self._capture_png, left, top, width, height)
            signature = await asyncio.to_thread(self._perceptual_signature, png)
        except (ImportError, RuntimeError, OSError, ValueError):
            return False
        previous = self._last_visual_signature
        self._last_visual_signature = signature
        if previous is None:
            return False
        difference = self._signature_difference(previous, signature)
        now = time.monotonic()
        threshold = min(1.0, max(0.0, self.options.content_change_threshold))
        cooldown = max(0.0, self.options.content_change_cooldown_seconds)
        if difference < threshold or now - self._last_screen_event_at < cooldown:
            return False
        self._last_screen_event_at = now
        await self.event_bus.publish(
            self.SCREEN_CHANGED,
            {
                "source": "active_window_visual_diff",
                "active_process": identity[0],
                "active_application": identity[1],
                "window_title": identity[2],
                "difference": round(difference, 4),
            },
        )
        return True

    async def _publish_error(
        self,
        *,
        source: str,
        title: str,
        message: str,
        identity: tuple[str | None, str | None, str | None],
    ) -> None:
        safe_title = title.strip()[:256]
        safe_message = message.strip()[:1000]
        fingerprint = hashlib.sha256(
            repr((source, safe_title, safe_message, identity)).encode("utf-8")
        ).hexdigest()
        now = time.monotonic()
        cooldown = max(0.0, self.options.content_change_cooldown_seconds)
        if fingerprint == self._last_error_fingerprint and now - self._last_error_event_at < cooldown:
            return
        self._last_error_fingerprint = fingerprint
        self._last_error_event_at = now
        await self.event_bus.publish(
            self.ERROR_DETECTED,
            {
                "source": source,
                "title": safe_title,
                "message": safe_message,
                "active_application": identity[1],
                "importance": 0.95,
            },
        )

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._poll_loop(), name="screen-perception")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _poll_loop(self) -> None:
        interval = max(0.25, self.options.poll_interval_seconds)
        while not self._stop.is_set():
            await self.poll_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except TimeoutError:
                pass

    async def capture_active_window(self, *, include_text: bool = False) -> ScreenCapture | None:
        if not self.options.enabled or not self.options.capture_active_window:
            return None
        snapshot = await asyncio.to_thread(self._inspector)
        if snapshot.minimized or not snapshot.bounds:
            return None
        left, top, width, height = snapshot.bounds
        if width <= 0 or height <= 0:
            return None
        png = await asyncio.to_thread(self._capture_png, left, top, width, height)
        text = None
        if include_text and self.options.ui_automation_enabled and snapshot.handle:
            text = await asyncio.to_thread(self._read_ui_automation, snapshot.handle)
        if include_text and not text and self.options.ocr_enabled:
            text = await asyncio.to_thread(self._read_ocr, png)
        return ScreenCapture(png=png, width=width, height=height, visible_text=text)

    async def capture_virtual_desktop(self) -> ScreenCapture | None:
        """Capture the authorized virtual desktop once without retaining pixel history."""
        if not self.options.enabled or not self.options.capture_active_window:
            return None
        try:
            png, width, height = await asyncio.to_thread(self._capture_virtual_desktop_png)
            png, width, height = await asyncio.to_thread(
                self._resize_png, png, width, height, self.options.vision_max_edge
            )
        except (ImportError, RuntimeError, OSError, ValueError):
            return None
        return ScreenCapture(png=png, width=width, height=height)

    @staticmethod
    def _capture_virtual_desktop_png() -> tuple[bytes, int, int]:
        import mss
        import mss.tools

        with mss.mss() as capture:
            monitor = capture.monitors[0]
            image = capture.grab(monitor)
            return mss.tools.to_png(image.rgb, image.size), image.width, image.height

    @staticmethod
    def _resize_png(
        png: bytes, width: int, height: int, max_edge: int
    ) -> tuple[bytes, int, int]:
        """Bound multimodal input cost while preserving the complete desktop view."""
        limit = max(256, min(int(max_edge), 2048))
        largest = max(width, height)
        if largest <= limit:
            return png, width, height
        from PIL import Image

        scale = limit / largest
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        output = io.BytesIO()
        with Image.open(io.BytesIO(png)) as image:
            image.convert("RGB").resize(
                (resized_width, resized_height), Image.Resampling.LANCZOS
            ).save(output, format="PNG", optimize=True)
        return output.getvalue(), resized_width, resized_height

    @staticmethod
    def _capture_png(left: int, top: int, width: int, height: int) -> bytes:
        import mss
        import mss.tools

        with mss.mss() as capture:
            image = capture.grab({"left": left, "top": top, "width": width, "height": height})
            return mss.tools.to_png(image.rgb, image.size)

    @staticmethod
    def _read_ui_automation(handle: int) -> str | None:
        try:
            from pywinauto import Desktop

            window = Desktop(backend="uia").window(handle=handle)
            texts = (text.strip() for item in window.descendants() for text in item.texts())
            content = "\n".join(text for text in texts if text)
            return content or None
        except (ImportError, RuntimeError, OSError):
            return None

    @staticmethod
    def _read_ui_automation_alert(handle: int | None) -> dict[str, str] | None:
        if not handle:
            return None
        try:
            from pywinauto import Desktop

            window = Desktop(backend="uia").window(handle=handle)
            error_words = re.compile(
                r"\b(error|erro|failed|falha|warning|aviso|alerta|critical|crítico)\b",
                re.IGNORECASE,
            )
            for item in [window, *window.descendants()]:
                control_type = str(getattr(item.element_info, "control_type", ""))
                texts = [text.strip() for text in item.texts() if text.strip()]
                message = " ".join(texts)
                if (
                    message
                    and control_type in {"Dialog", "Window", "Text"}
                    and error_words.search(message)
                ):
                    return {
                        "source": "ui_automation",
                        "title": texts[0],
                        "message": message,
                    }
        except (ImportError, RuntimeError, OSError, AttributeError):
            return None
        return None

    @staticmethod
    def _perceptual_signature(png: bytes) -> bytes:
        from PIL import Image

        with Image.open(io.BytesIO(png)) as image:
            grayscale = image.convert("L").resize((16, 16))
            values = bytes(grayscale.getdata())
        mean = sum(values) / len(values)
        return bytes(value >= mean for value in values)

    @staticmethod
    def _signature_difference(previous: bytes, current: bytes) -> float:
        if len(previous) != len(current) or not current:
            return 1.0
        changed = sum(
            left != right for left, right in zip(previous, current, strict=True)
        )
        return changed / len(current)

    @staticmethod
    def _read_ocr(png: bytes) -> str | None:
        try:
            import pytesseract
            from PIL import Image

            content = pytesseract.image_to_string(Image.open(io.BytesIO(png))).strip()
            return content or None
        except (ImportError, RuntimeError, OSError):
            return None
