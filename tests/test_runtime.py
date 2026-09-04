from pathlib import Path

from app.config import Settings
from app.proactivity import ProactivityLevel
from app.runtime import BackgroundServices, _proactivity_level


class Tools:
    async def execute(self, name, **parameters):
        raise AssertionError("no automation should run")


def test_proactivity_level_handles_yaml_boolean_and_invalid_values_safely() -> None:
    assert _proactivity_level(False) is ProactivityLevel.OFF
    assert _proactivity_level(True) is ProactivityLevel.LOW
    assert _proactivity_level("off") is ProactivityLevel.OFF
    assert _proactivity_level("invalid") is ProactivityLevel.OFF


def test_background_services_start_and_stop(tmp_path: Path):
    settings = Settings(raw={"screen": {"enabled": False}, "automation": {"tick_seconds": 0.25}}, root=tmp_path)
    services = BackgroundServices(settings, Tools())
    services.start()
    assert services._thread is not None and services._thread.is_alive()
    services.stop()
    assert services._thread is None


async def test_explicit_only_mode_does_not_start_automation_or_proactivity(tmp_path: Path):
    settings = Settings(
        raw={
            "screen": {"enabled": False},
            "automation": {"enabled": False},
            "proactivity": {"level": "off"},
        },
        root=tmp_path,
    )
    services = BackgroundServices(settings, Tools())
    await services.astart()
    try:
        assert services.automations._task is None
        assert services.proactivity._unsubscribe == []
    finally:
        await services.astop()
