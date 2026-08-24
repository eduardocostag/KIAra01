from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    body: dict[str, Any]


class JsonHttpClient:
    def __init__(self, timeout_seconds: float = 20) -> None:
        self.timeout = timeout_seconds

    async def request(
        self, method: str, url: str, *, token: str, payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> HttpResponse:
        return await asyncio.to_thread(
            self._request_sync, method, url, token, payload, idempotency_key
        )

    def _request_sync(self, method, url, token, payload, idempotency_key) -> HttpResponse:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode() if payload is not None else None,
            method=method, headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                return HttpResponse(response.status, json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Serviço remoto retornou HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Serviço remoto indisponível.") from exc
