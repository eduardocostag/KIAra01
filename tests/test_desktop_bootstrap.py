from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from app.bootstrap import run_desktop_app
from app.config import Settings


def test_desktop_bootstrap_lazily_delegates(monkeypatch) -> None:
    desktop = ModuleType("app.ui.desktop")
    observed = {}

    def fake_run(factory, argv, *_optional_services):
        observed["argv"] = argv
        core, kill_switch = factory(lambda _summary: True)
        observed["built"] = core is not None and kill_switch is not None
        return 17

    desktop.run_desktop = fake_run
    monkeypatch.setitem(sys.modules, "app.ui.desktop", desktop)
    settings = Settings(raw={"security": {"allowlisted_commands": []}}, root=Path.cwd())

    assert run_desktop_app(settings, ["kiara"]) == 17
    assert observed == {"argv": ["kiara"], "built": True}
