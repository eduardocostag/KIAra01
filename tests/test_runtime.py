from pathlib import Path

from app.config import Settings
from app.runtime import BackgroundServices


class Tools:
    async def execute(self, name, **parameters):
        raise AssertionError("no automation should run")


def test_background_services_start_and_stop(tmp_path: Path):
    settings = Settings(raw={"screen": {"enabled": False}, "automation": {"tick_seconds": 0.25}}, root=tmp_path)
    services = BackgroundServices(settings, Tools())
    services.start()
    assert services._thread is not None and services._thread.is_alive()
    services.stop()
    assert services._thread is None
