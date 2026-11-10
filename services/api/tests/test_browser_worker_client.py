import io
import json
from urllib.error import HTTPError
from unittest.mock import patch

import pytest
from kiara_api.browser_worker import BrowserWorkerClient, BrowserWorkerError
from kiara_api.competition import _browser_error

@pytest.mark.parametrize("payload,headers,expected", [
    ({"detail": "Pausa", "code": "instagram_safety_cooldown", "retry_after": 86400}, {}, 86400),
    ({"detail": "Pausa", "code": "instagram_rate_limited"}, {"Retry-After": "3600"}, 3600),
    ({"detail": "Pausa"}, {"Retry-After": "invalid"}, None),
])
def test_worker_pause_survives_api_boundary(monkeypatch, payload, headers, expected):
    monkeypatch.setenv("KIARA_BROWSER_WORKER_URL", "https://worker.example.test")
    monkeypatch.setenv("KIARA_BROWSER_WORKER_TOKEN", "test-only")
    error = HTTPError("https://worker.example.test", 429, "limited", headers, io.BytesIO(json.dumps(payload).encode()))
    with patch("kiara_api.browser_worker.urlopen", side_effect=error):
        with pytest.raises(BrowserWorkerError) as caught:
            BrowserWorkerClient().analyse("workspace", {})
    failure = caught.value
    assert failure.retry_after == expected
    assert failure.code == payload.get("code", "browser_worker_busy")
    api_error = _browser_error(failure)
    assert api_error.status_code == 429
    assert api_error.details.get("retry_after") == expected
