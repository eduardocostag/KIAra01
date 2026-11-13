from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from app.whatsapp.site_auth import _NoRedirect


class AuthorizationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SiteIdentity:
    user_id: str
    organization_id: str
    role: str


class SupabaseAuthorizationVerifier:
    """Verify both the Supabase identity and its current Kiara membership per call."""

    def __init__(self, supabase_url: str, public_key: str, api_url: str, *, opener=None):
        for value in (supabase_url, api_url):
            parts = urlsplit(value)
            if (parts.scheme != "https" or not parts.hostname or parts.username
                    or parts.password or parts.query or parts.fragment):
                raise ValueError("Configure URLs HTTPS sem credenciais para autenticação.")
        if not public_key.strip():
            raise ValueError("Configure a chave pública Supabase usada pelo site.")
        self.supabase_url = supabase_url.rstrip("/")
        self.public_key = public_key
        self.api_url = api_url.rstrip("/")
        self.opener = opener or build_opener(_NoRedirect())

    def _read(self, url: str, token: str, *, supabase: bool = False) -> dict:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if supabase:
            headers["apikey"] = self.public_key
        request = Request(url, headers=headers)
        with self.opener.open(request, timeout=12) as response:
            raw = response.read(64_001)
        if len(raw) > 64_000:
            raise ValueError("oversized identity")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TypeError("invalid identity")
        return result

    def verify(self, token: str) -> SiteIdentity:
        if not isinstance(token, str) or not 10 <= len(token) <= 8_000:
            raise AuthorizationError("Entre na Kiara para acessar a ponte local.")
        try:
            user = self._read(self.supabase_url + "/auth/v1/user", token, supabase=True)
            member = self._read(self.api_url + "/v1/me", token)
            organization = member.get("organization")
            if (not isinstance(user.get("id"), str) or not user["id"]
                    or str(user.get("email") or "").strip().lower() != "admin@kiara.local"
                    or member.get("user_id") != user["id"]
                    or member.get("role") not in {"owner", "admin"}
                    or not isinstance(organization, dict)
                    or not isinstance(organization.get("id"), str) or not organization["id"]):
                raise ValueError("membership denied")
            return SiteIdentity(user["id"], organization["id"], member["role"])
        except Exception:  # noqa: BLE001 - identity/provider errors must never expose tokens
            # Provider responses can contain tokens and private identity fields.
            raise AuthorizationError("Sessão inválida ou sem acesso administrativo à Kiara. Entre novamente na Kiara.") from None
