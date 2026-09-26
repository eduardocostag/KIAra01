from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class BrowserWorkerError(Exception):
    status_code: int
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class BrowserWorkerClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("KIARA_BROWSER_WORKER_URL", "").strip().rstrip("/")
        self.token = os.getenv("KIARA_BROWSER_WORKER_TOKEN", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        expect_bytes: bool = False,
        timeout: int = 55,
    ) -> dict[str, Any] | bytes:
        if not self.configured:
            raise BrowserWorkerError(
                503,
                "browser_worker_not_configured",
                "O navegador da Kiara ainda não foi conectado à infraestrutura Oracle.",
            )
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Accept": "image/jpeg" if expect_bytes else "application/json",
                "Content-Type": "application/json",
                "X-Kiara-Worker-Token": self.token,
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(8_000_001)
        except HTTPError as error:
            raw = error.read(100_001)
            try:
                body = json.loads(raw)
                message = str(body.get("detail") or body.get("message") or "")
            except (UnicodeDecodeError, json.JSONDecodeError):
                message = ""
            code = {
                401: "browser_worker_auth_failed",
                404: "browser_session_expired",
                409: "instagram_connection_required",
                429: "browser_worker_busy",
            }.get(error.code, "browser_worker_failed")
            raise BrowserWorkerError(
                error.code if 400 <= error.code < 500 else 502,
                code,
                message or f"O navegador Oracle respondeu com HTTP {error.code}.",
            ) from None
        except (URLError, TimeoutError, OSError):
            raise BrowserWorkerError(
                503,
                "browser_worker_unavailable",
                "O navegador da Kiara está indisponível. Verifique a VM Oracle e tente novamente.",
            ) from None
        if len(raw) > 8_000_000:
            raise BrowserWorkerError(502, "browser_worker_response_too_large", "A resposta do navegador excedeu o limite seguro.")
        if expect_bytes:
            return raw
        try:
            parsed = json.loads(raw or b"{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BrowserWorkerError(502, "browser_worker_invalid_response", "O navegador retornou uma resposta inválida.") from None
        if not isinstance(parsed, dict):
            raise BrowserWorkerError(502, "browser_worker_invalid_response", "O navegador retornou uma resposta inválida.")
        return parsed

    def create_session(self, workspace_id: str) -> dict[str, Any]:
        return self._request("POST", "/v1/sessions", {"workspace_id": workspace_id})  # type: ignore[return-value]

    def _workspace_query(self, workspace_id: str) -> str:
        return "?workspace_id=" + quote(workspace_id, safe="")

    def session_status(self, workspace_id: str, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/sessions/{quote(session_id)}{self._workspace_query(workspace_id)}")  # type: ignore[return-value]

    def screenshot(self, workspace_id: str, session_id: str) -> bytes:
        return self._request("GET", f"/v1/sessions/{quote(session_id)}/screenshot{self._workspace_query(workspace_id)}", expect_bytes=True)  # type: ignore[return-value]

    def input(self, workspace_id: str, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/v1/sessions/{quote(session_id)}/input{self._workspace_query(workspace_id)}", payload)  # type: ignore[return-value]

    def complete(self, workspace_id: str, session_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/sessions/{quote(session_id)}/complete{self._workspace_query(workspace_id)}", {})  # type: ignore[return-value]

    def profile_status(self, workspace_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/profiles/{quote(workspace_id, safe='')}/status")  # type: ignore[return-value]

    def disconnect(self, workspace_id: str) -> None:
        self._request("DELETE", f"/v1/profiles/{quote(workspace_id, safe='')}")

    def profile(self, workspace_id: str, username: str) -> dict[str, Any]:
        return self._request("POST", "/v1/instagram/profile", {"workspace_id": workspace_id, "username": username})  # type: ignore[return-value]

    def analyse(self, workspace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/v1/instagram/analyse", {"workspace_id": workspace_id, **payload})  # type: ignore[return-value]
