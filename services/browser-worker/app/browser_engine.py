from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

BrowserEngineName = Literal["chromium", "invisible"]


@dataclass
class BrowserRuntime:
    engine: BrowserEngineName
    context: Any
    launcher: Any

    async def close(self) -> None:
        if self.engine == "invisible":
            await self.launcher.__aexit__(None, None, None)
            return
        try:
            await self.context.close()
        finally:
            await self.launcher.stop()


def configured_engine() -> BrowserEngineName:
    value = os.getenv("KIARA_BROWSER_ENGINE", "invisible").strip().lower()
    if value not in {"chromium", "invisible"}:
        raise RuntimeError("KIARA_BROWSER_ENGINE deve ser 'chromium' ou 'invisible'.")
    return value  # type: ignore[return-value]


def fallback_enabled() -> bool:
    return os.getenv("KIARA_BROWSER_ENGINE_FALLBACK", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def workspace_digest(workspace_id: str) -> str:
    salt = os.getenv("KIARA_PROFILE_SALT") or os.getenv("KIARA_WORKER_TOKEN", "")
    if not salt:
        raise RuntimeError("KIARA_PROFILE_SALT não foi configurado.")
    return hmac.new(salt.encode(), workspace_id.encode(), hashlib.sha256).hexdigest()


def workspace_seed(workspace_id: str) -> int:
    """Stable positive int31 seed; the identifier itself never leaves the HMAC boundary."""
    seed = int(workspace_digest(workspace_id)[:8], 16) & 0x7FFFFFFF
    return seed or 1


def profile_path(root: Path, workspace_id: str, engine: BrowserEngineName) -> Path:
    digest = workspace_digest(workspace_id)
    # Preserve existing Chromium profiles while keeping Firefox data incompatible by design.
    return root / digest if engine == "chromium" else root / "invisible" / digest


async def launch_browser(
    *,
    profile: Path,
    engine: BrowserEngineName,
    executable: str | None,
    seed: int,
) -> BrowserRuntime:
    profile.mkdir(parents=True, exist_ok=True)
    if engine == "invisible":
        from invisible_playwright.async_api import InvisiblePlaywright

        launcher = InvisiblePlaywright(
            seed=seed,
            profile_dir=profile,
            headless=True,
            humanize=True,
            locale="pt-BR",
            timezone="America/Sao_Paulo",
            show_cursor=False,
        )
        context = await launcher.__aenter__()
        return BrowserRuntime("invisible", context, launcher)

    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    launch_args: dict[str, Any] = {
        "headless": True,
        "viewport": {"width": 1280, "height": 800},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    if executable:
        launch_args["executable_path"] = executable
    try:
        context = await playwright.chromium.launch_persistent_context(str(profile), **launch_args)
    except BaseException:
        await playwright.stop()
        raise
    return BrowserRuntime("chromium", context, playwright)
