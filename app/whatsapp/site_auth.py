"""Legacy noninteractive session client; the Chrome executor uses browser authentication."""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SiteLoginError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SiteSession:
    """Supabase password session, refreshed before its access token expires."""

    def __init__(self, url: str, public_key: str, *, clock=time.time, opener=None):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise SiteLoginError("SUPABASE_URL precisa ser uma URL HTTPS sem credenciais.")
        if not public_key.strip():
            raise SiteLoginError("Configure a chave pública do Supabase.")
        self.url = url.rstrip("/")
        self.public_key = public_key.strip()
        self.clock = clock
        self.opener = opener or build_opener(_NoRedirect())
        self._access = ""
        self._refresh = ""
        self._expires = 0.0

    def _exchange(self, grant: str, body: dict[str, str]) -> None:
        request = Request(
            self.url + "/auth/v1/token?grant_type=" + grant,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "apikey": self.public_key},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("oversized response")
            payload = json.loads(raw)
            access = payload.get("access_token")
            refresh = payload.get("refresh_token")
            lifetime = int(payload.get("expires_in", 0))
            if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh or lifetime <= 0:
                raise ValueError("invalid session")
        except (HTTPError, URLError, OSError, ValueError, TypeError, AttributeError) as exc:
            # Never surface provider bodies, passwords, or token-bearing requests.
            raise SiteLoginError("Não foi possível autenticar no site. Confira o login, a conexão e eventuais requisitos de MFA/CAPTCHA.") from None
        self._access, self._refresh = access, refresh
        self._expires = self.clock() + lifetime

    def login(self, email: str, password: str) -> None:
        self._exchange("password", {"email": email.strip(), "password": password})

    def token(self) -> str:
        if not self._refresh:
            raise SiteLoginError("Entre na conta da Kiara antes de sincronizar.")
        if self.clock() >= self._expires - 60:
            self._exchange("refresh_token", {"refresh_token": self._refresh})
        return self._access

