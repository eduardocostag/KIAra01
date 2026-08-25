from __future__ import annotations

import asyncio
import io

from PIL import Image

from app.config import Settings
from app.core.context import ContextManager
from app.core.event_bus import EventBus
from app.models import ScreenContext
from app.perception import PerceptionOptions, ScreenPerception
from app.perception.understanding import LiveScreenUnderstanding
from app.perception.windows import WindowSnapshot
from app.providers.llm import LLMProvider


def snapshot(title: str = "Documento") -> WindowSnapshot:
    return WindowSnapshot(
        ScreenContext(active_application="notepad.exe", active_process="42", window_title=title),
        handle=7,
        bounds=(10, 20, 300, 200),
    )


def test_uia_text_normalizer_flattens_nested_values() -> None:
    assert ScreenPerception._flatten_uia_text(["janela", ["erro", ["detalhe"]]]) == [
        "janela",
        "erro",
        "detalhe",
    ]


async def test_poll_publishes_only_when_context_changes() -> None:
    bus = EventBus()
    received: list[dict[str, object]] = []

    async def receive(payload: dict[str, object]) -> None:
        received.append(payload)

    bus.subscribe(ScreenPerception.CONTEXT_CHANGED, receive)
    perception = ScreenPerception(bus, inspector=snapshot)
    assert await perception.poll_once() is True
    assert await perception.poll_once() is False
    assert len(received) == 1
    assert received[0]["window_title"] == "Documento"


async def test_poll_loop_survives_optional_windows_backend_failure(monkeypatch) -> None:
    perception = ScreenPerception(
        EventBus(),
        PerceptionOptions(poll_interval_seconds=0.25),
        inspector=snapshot,
    )
    calls = 0

    async def failing_poll() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyError(None)
        perception._stop.set()
        return False

    monkeypatch.setattr(perception, "poll_once", failing_poll)
    await perception.start()
    await asyncio.sleep(0.35)
    await asyncio.wait_for(perception.stop(), timeout=1)

    assert calls >= 1


async def test_disabled_features_do_not_inspect_or_capture() -> None:
    calls = 0

    def inspector() -> WindowSnapshot:
        nonlocal calls
        calls += 1
        return snapshot()

    perception = ScreenPerception(EventBus(), PerceptionOptions(enabled=False), inspector=inspector)
    assert await perception.poll_once() is False
    assert await perception.capture_active_window() is None
    assert calls == 0


async def test_capture_is_active_window_only_and_in_memory(monkeypatch) -> None:
    perception = ScreenPerception(EventBus(), inspector=snapshot)
    requested: list[tuple[int, int, int, int]] = []

    def capture(left: int, top: int, width: int, height: int) -> bytes:
        requested.append((left, top, width, height))
        return b"png-data"

    monkeypatch.setattr(perception, "_capture_png", capture)
    result = await perception.capture_active_window()
    assert result is not None
    assert result.png == b"png-data"
    assert requested == [(10, 20, 300, 200)]
    assert not hasattr(result, "path")


async def test_virtual_desktop_capture_is_ephemeral_and_in_memory(monkeypatch) -> None:
    perception = ScreenPerception(EventBus(), inspector=snapshot)
    monkeypatch.setattr(
        perception, "_capture_virtual_desktop_png", lambda: (b"desktop-png", 1920, 1080)
    )
    monkeypatch.setattr(
        perception, "_resize_png", lambda png, width, height, _limit: (png, width, height)
    )

    result = await perception.capture_virtual_desktop()

    assert result is not None
    assert result.png == b"desktop-png"
    assert (result.width, result.height) == (1920, 1080)
    assert not hasattr(result, "path")


async def test_latest_capture_reuses_current_live_frame(monkeypatch) -> None:
    perception = ScreenPerception(
        EventBus(), PerceptionOptions(live_view_enabled=True), inspector=snapshot
    )
    monkeypatch.setattr(perception, "_capture_png", lambda *_: b"live-frame")
    identity = ("42", "notepad.exe", "Documento")

    assert await perception.poll_once() is True
    first = await perception.latest_capture(expected_identity=identity)

    assert first is not None
    assert first.png == b"live-frame"
    assert (
        await perception.latest_capture(expected_identity=("99", "other.exe", "Outra")) is not None
    )


def test_visual_capture_downscales_without_cropping() -> None:
    source = io.BytesIO()
    Image.new("RGB", (1920, 1080), "cyan").save(source, format="PNG")

    png, width, height = ScreenPerception._resize_png(source.getvalue(), 1920, 1080, 896)

    assert (width, height) == (896, 504)
    with Image.open(io.BytesIO(png)) as resized:
        assert resized.size == (896, 504)


async def test_minimized_window_is_not_captured() -> None:
    base = snapshot()
    minimized = WindowSnapshot(base.context, handle=7, bounds=(0, 0, 10, 10), minimized=True)
    perception = ScreenPerception(EventBus(), inspector=lambda: minimized)
    assert await perception.capture_active_window() is None


async def test_ocr_is_opt_in_and_used_only_as_fallback(monkeypatch) -> None:
    options = PerceptionOptions(ui_automation_enabled=True, ocr_enabled=True)
    perception = ScreenPerception(EventBus(), options, inspector=snapshot)
    monkeypatch.setattr(perception, "_capture_png", lambda *_: b"png")
    monkeypatch.setattr(perception, "_read_ui_automation", lambda *_: None)
    monkeypatch.setattr(perception, "_read_ocr", lambda *_: "texto")
    result = await perception.capture_active_window(include_text=True)
    assert result is not None
    assert result.visible_text == "texto"


async def test_visual_change_emits_metadata_only_and_obeys_cooldown(monkeypatch) -> None:
    bus = EventBus()
    received: list[dict[str, object]] = []

    async def receive(payload: dict[str, object]) -> None:
        received.append(payload)

    bus.subscribe(ScreenPerception.SCREEN_CHANGED, receive)
    options = PerceptionOptions(
        content_change_enabled=True,
        content_change_threshold=0.25,
        content_change_cooldown_seconds=60,
    )
    perception = ScreenPerception(bus, options, inspector=snapshot)
    signatures = iter((bytes([0]) * 8, bytes([1]) * 8, bytes([0]) * 8))
    monkeypatch.setattr(perception, "_capture_png", lambda *_: b"ephemeral-pixels")
    monkeypatch.setattr(perception, "_perceptual_signature", lambda _png: next(signatures))

    assert await perception.poll_once() is True  # context + visual baseline
    assert await perception.poll_once() is True
    assert await perception.poll_once() is False  # same change suppressed by cooldown
    assert len(received) == 1
    assert received[0]["source"] == "active_window_visual_diff"
    assert "png" not in received[0]
    assert "signature" not in received[0]
    assert not hasattr(perception, "_last_capture")


async def test_visual_sampling_is_opt_in(monkeypatch) -> None:
    perception = ScreenPerception(EventBus(), inspector=snapshot)

    def unexpected_capture(*_args) -> bytes:
        raise AssertionError("background capture must be opt-in")

    monkeypatch.setattr(perception, "_capture_png", unexpected_capture)
    await perception.poll_once()
    await perception.poll_once()


async def test_uia_error_detection_is_opt_in_and_deduplicated(monkeypatch) -> None:
    bus = EventBus()
    received: list[dict[str, object]] = []

    async def receive(payload: dict[str, object]) -> None:
        received.append(payload)

    bus.subscribe(ScreenPerception.ERROR_DETECTED, receive)
    options = PerceptionOptions(
        ui_automation_enabled=True,
        error_detection_enabled=True,
        content_change_cooldown_seconds=60,
    )
    perception = ScreenPerception(bus, options, inspector=snapshot)
    monkeypatch.setattr(
        perception,
        "_read_ui_automation_alert",
        lambda _handle: {
            "source": "ui_automation",
            "title": "Erro",
            "message": "Falha ao salvar",
        },
    )

    await perception.poll_once()
    await perception.poll_once()
    assert len(received) == 1
    assert received[0]["source"] == "ui_automation"
    assert received[0]["message"] == "Falha ao salvar"


def test_options_are_loaded_from_feature_flags(tmp_path) -> None:
    settings = Settings(
        {"screen": {"enabled": True, "capture_active_window": False, "ocr_enabled": True}},
        tmp_path,
    )
    options = PerceptionOptions.from_settings(settings)
    assert options.capture_active_window is False
    assert options.ocr_enabled is True
    assert options.ui_automation_enabled is False


def test_screen_intelligence_options_are_loaded(tmp_path) -> None:
    settings = Settings(
        {
            "screen": {
                "content_change_enabled": True,
                "content_change_threshold": 0.3,
                "content_change_cooldown_seconds": 9,
                "error_detection_enabled": True,
            }
        },
        tmp_path,
    )
    options = PerceptionOptions.from_settings(settings)
    assert options.content_change_enabled is True
    assert options.content_change_threshold == 0.3
    assert options.content_change_cooldown_seconds == 9
    assert options.error_detection_enabled is True


class _VisionProvider(LLMProvider):
    @property
    def capabilities(self) -> frozenset[str]:
        return frozenset({"generate", "vision"})

    async def generate(self, prompt: str) -> str:
        return prompt

    async def vision_bytes(
        self, prompt: str, image: bytes, *, media_type: str = "image/png"
    ) -> str:
        assert image == b"live-frame"
        return "Painel do Windows com erro de driver código 10."


async def test_live_understanding_keeps_semantics_without_pixels(monkeypatch) -> None:
    bus = EventBus()
    perception = ScreenPerception(
        bus, PerceptionOptions(live_view_enabled=True), inspector=snapshot
    )
    monkeypatch.setattr(perception, "_capture_png", lambda *_: b"live-frame")
    context = ContextManager(lambda: snapshot().context)
    service = LiveScreenUnderstanding(
        perception, _VisionProvider(), context, min_interval_seconds=2
    )
    service.start()
    await perception.poll_once()
    await asyncio.sleep(0)
    if service._analysis_task is not None:
        await service._analysis_task
    understanding = context.live_screen_understanding()
    assert understanding is not None
    assert "erro de driver" in understanding["summary"]
    assert understanding["pixels_persisted"] is False
    assert "png" not in understanding
    await service.stop()
