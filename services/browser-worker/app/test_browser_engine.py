from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from . import browser_engine


def test_workspace_identity_is_stable_isolated_and_not_exposed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KIARA_PROFILE_SALT", "test-salt")
    first = browser_engine.workspace_digest("workspace-a")
    assert first == browser_engine.workspace_digest("workspace-a")
    assert first != browser_engine.workspace_digest("workspace-b")
    assert "workspace-a" not in first
    assert browser_engine.workspace_seed("workspace-a") == browser_engine.workspace_seed("workspace-a")
    assert 0 < browser_engine.workspace_seed("workspace-a") <= 0x7FFFFFFF
    assert browser_engine.profile_path(tmp_path, "workspace-a", "chromium") == tmp_path / first
    assert browser_engine.profile_path(tmp_path, "workspace-a", "invisible") == tmp_path / "invisible" / first


def test_engine_configuration_is_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIARA_BROWSER_ENGINE", raising=False)
    assert browser_engine.configured_engine() == "invisible"
    monkeypatch.setenv("KIARA_BROWSER_ENGINE", "chromium")
    assert browser_engine.configured_engine() == "chromium"
    monkeypatch.setenv("KIARA_BROWSER_ENGINE", "unknown")
    with pytest.raises(RuntimeError):
        browser_engine.configured_engine()


@pytest.mark.asyncio
async def test_runtime_closes_invisible_launcher_once() -> None:
    calls: list[tuple[object, ...]] = []

    class Launcher:
        async def __aexit__(self, *args: object) -> None:
            calls.append(args)

    runtime = browser_engine.BrowserRuntime("invisible", SimpleNamespace(), Launcher())
    await runtime.close()
    assert calls == [(None, None, None)]


@pytest.mark.asyncio
async def test_runtime_closes_chromium_context_before_playwright() -> None:
    calls: list[str] = []

    class Context:
        async def close(self) -> None:
            calls.append("context")

    class Playwright:
        async def stop(self) -> None:
            calls.append("playwright")

    runtime = browser_engine.BrowserRuntime("chromium", Context(), Playwright())
    await runtime.close()
    assert calls == ["context", "playwright"]
