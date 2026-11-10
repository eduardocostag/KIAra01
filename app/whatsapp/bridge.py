from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirecionamento da ponte bloqueado")


class SiteBridge:
    def __init__(self, base_url=None, token_provider=None):
        self.base_url = (base_url or os.environ.get("KIARA_API_URL", "")).rstrip("/")
        self.token_provider = token_provider or (lambda: os.environ.get("KIARA_WHATSAPP_API_TOKEN", ""))
        if self.base_url:
            parsed = urlparse(self.base_url)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("KIARA_API_URL deve ser uma URL base sem credenciais")
            if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
                raise ValueError("Use HTTPS para conectar o site (HTTP somente localhost).")

    @property
    def configured(self):
        return bool(self.base_url)

    def _request(self, path, body=None):
        token = self.token_provider()
        if not token:
            raise RuntimeError("Autenticação da ponte com o site ausente")
        request = Request(self.base_url + "/v1/whatsapp-web/" + path,
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            return json.loads(response.read(2_000_000))

    def config(self):
        return self._request("config")

    def next_analysis(self):
        return self._request("analysis/next")

    def next_outbound(self):
        return self._request("outbox/next")

    def complete_outbound(self, identifier, *, status, provider_message_id=None):
        payload = {"status": status}
        if provider_message_id:
            payload["provider_message_id"] = provider_message_id
        return self._request("outbox/" + identifier + "/complete", payload)

    def complete_analysis(self, job_id, result):
        return self._request("analysis/" + job_id + "/complete", result)

    def sync(self, store):
        events = store.pending_events()
        if events:
            self._request("events", {"events": events})
            store.acknowledge_events([event["id"] for event in events])
