from __future__ import annotations

import asyncio
import json

import pytest

from .instagram_safety import InstagramSafetyGuard, InstagramSafetyLimit


def test_safety_guard_enforces_cooldown_without_storing_workspace_id(tmp_path) -> None:
    now = [1_000_000.0]
    guard = InstagramSafetyGuard(
        tmp_path,
        clock=lambda: now[0],
        analysis_cooldown_seconds=300,
        hourly_limit=4,
        daily_limit=12,
    )

    asyncio.run(guard.reserve_analysis("workspace-sensitive-id"))
    with pytest.raises(InstagramSafetyLimit) as caught:
        asyncio.run(guard.reserve_analysis("workspace-sensitive-id"))

    assert caught.value.retry_after_seconds == 300
    persisted = (tmp_path / "instagram-safety.json").read_text(encoding="utf-8")
    assert "workspace-sensitive-id" not in persisted


def test_safety_guard_enforces_hourly_budget(tmp_path) -> None:
    now = [1_000_000.0]
    guard = InstagramSafetyGuard(
        tmp_path,
        clock=lambda: now[0],
        analysis_cooldown_seconds=60,
        hourly_limit=2,
        daily_limit=12,
    )

    asyncio.run(guard.reserve_analysis("workspace"))
    now[0] += 61
    asyncio.run(guard.reserve_analysis("workspace"))
    now[0] += 61

    with pytest.raises(InstagramSafetyLimit) as caught:
        asyncio.run(guard.reserve_analysis("workspace"))

    assert caught.value.retry_after_seconds > 0
    assert "por hora" in caught.value.message


def test_safety_guard_persists_platform_pause(tmp_path) -> None:
    now = [1_000_000.0]
    guard = InstagramSafetyGuard(tmp_path, clock=lambda: now[0])

    asyncio.run(guard.pause("workspace", 3_600))
    with pytest.raises(InstagramSafetyLimit) as caught:
        asyncio.run(guard.reserve_analysis("workspace"))

    assert caught.value.retry_after_seconds == 3_600
    payload = json.loads((tmp_path / "instagram-safety.json").read_text(encoding="utf-8"))
    assert len(payload) == 1
