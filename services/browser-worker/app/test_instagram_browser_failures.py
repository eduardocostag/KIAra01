from __future__ import annotations

import asyncio
import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from .instagram import InstagramSessionFailure
from .instagram_safety import InstagramSafetyGuard, InstagramSafetyLimit


@pytest.fixture
def worker(tmp_path, monkeypatch):
    monkeypatch.setenv("KIARA_BROWSER_DATA_DIR", str(tmp_path))
    return importlib.import_module(".main", __package__)


@pytest.mark.parametrize("status,body,url,code", [
    (429, "<html>limited</html>", "", "instagram_rate_limited"),
    (403, '{"message":"challenge_required"}', "", "instagram_verification_required"),
    (200, '{"status":"fail","message":"Please wait a few minutes"}', "", "instagram_rate_limited"),
    (200, '{"challenge":{"url":"/challenge/"}}', "", "instagram_verification_required"),
    (200, "<html>challenge</html>", "https://www.instagram.com/challenge/", "instagram_verification_required"),
    (200, "<html>login</html>", "https://www.instagram.com/accounts/login/", "instagram_session_expired"),
    (401, "", "", "instagram_session_expired"),
])
def test_browser_classifies_platform_failures(worker, status, body, url, code):
    session = SimpleNamespace(lock=asyncio.Lock(), page=SimpleNamespace(
        evaluate=AsyncMock(return_value={"status": status, "text": body, "url": url})))
    with pytest.raises(InstagramSessionFailure) as caught:
        asyncio.run(worker.sessions._page_json(session, "https://www.instagram.com/api/v1/test"))
    assert caught.value.code == code


@pytest.mark.parametrize("mode", ["commenters", "post_audience"])
@pytest.mark.parametrize("code,seconds", [
    ("instagram_rate_limited", 3600), ("instagram_verification_required", 86400),
])
def test_analysis_stops_fallback_and_persists_pause(worker, monkeypatch, tmp_path, mode, code, seconds):
    guard = InstagramSafetyGuard(tmp_path, clock=lambda: 1000000.0)
    monkeypatch.setattr(worker, "safety", guard)
    monkeypatch.setattr(worker, "instagram_cookie", AsyncMock(return_value="sessionid=test"))
    fetch = AsyncMock(side_effect=InstagramSessionFailure(429 if seconds == 3600 else 409, code, "blocked"))
    monkeypatch.setattr(worker.sessions, "fetch_instagram_comments", fetch)
    instagram = importlib.import_module(".instagram", __package__)
    fallback = Mock()
    monkeypatch.setattr(instagram, "collect_instagram_relationships", fallback)
    payload = worker.AnalysisRequest(workspace_id="workspace", mode=mode, username="target", media_id="123")
    with pytest.raises(InstagramSessionFailure) as first:
        asyncio.run(worker.instagram_analyse(payload))
    assert first.value.retry_after_seconds == seconds
    response = asyncio.run(worker.instagram_failure_handler(None, first.value))
    assert response.headers["Retry-After"] == str(seconds)
    assert json.loads(response.body)["retry_after"] == seconds
    fallback.assert_not_called()
    with pytest.raises(InstagramSafetyLimit) as caught:
        asyncio.run(worker.instagram_analyse(payload))
    assert caught.value.retry_after_seconds == seconds
    assert fetch.await_count == 1


def test_browser_returns_success_payload(worker):
    payload = {"comments": [{"pk": "1"}]}
    session = SimpleNamespace(lock=asyncio.Lock(), page=SimpleNamespace(
        evaluate=AsyncMock(return_value={"status": 200, "text": json.dumps(payload)})))
    assert asyncio.run(worker.sessions._page_json(session, "https://www.instagram.com/api/v1/test")) == payload
