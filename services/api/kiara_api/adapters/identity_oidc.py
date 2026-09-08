from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen

import jwt

from ..http.errors import ApiError
from ..ports.identity import IdentityPrincipal

JwksFetcher = Callable[[str], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]

_ALGORITHMS = ("RS256",)
_ROLE_MAP = {
    "org:admin": "admin",
    "org:member": "operator",
    "owner": "owner",
    "admin": "admin",
    "operator": "operator",
    "viewer": "viewer",
}
_MAX_JWKS_BYTES = 1_000_000
_MAX_JWKS_KEYS = 32


class OidcIdentityVerifier:
    """Verify OIDC access tokens locally and derive tenant identity from signed claims."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str | None,
        jwks_url: str,
        cache_ttl_seconds: int = 300,
        fetcher: JwksFetcher | None = None,
        clock_skew_seconds: int = 30,
    ) -> None:
        if not issuer or not jwks_url:
            raise ValueError("issuer and jwks_url are required")
        if not 30 <= cache_ttl_seconds <= 3600:
            raise ValueError("cache_ttl_seconds must be between 30 and 3600")
        if not 0 <= clock_skew_seconds <= 120:
            raise ValueError("clock_skew_seconds must be between 0 and 120")
        self._issuer = issuer.rstrip("/")
        self._audience = audience
        self._jwks_url = jwks_url
        self._cache_ttl_seconds = cache_ttl_seconds
        self._clock_skew_seconds = clock_skew_seconds
        self._fetcher = fetcher or _fetch_jwks
        self._keys: dict[str, Mapping[str, Any]] = {}
        self._cache_expires_at = 0.0
        self._cache_lock = asyncio.Lock()

    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        try:
            header = jwt.get_unverified_header(bearer_token)
            kid = _required_text(header, "kid")
            if header.get("alg") not in _ALGORITHMS:
                raise jwt.InvalidAlgorithmError("unsupported algorithm")
            if header.get("typ") not in (None, "JWT"):
                raise jwt.InvalidTokenError("unexpected token type")

            jwk = await self._key_for(kid)
            key = jwt.PyJWK.from_dict(dict(jwk), algorithm="RS256").key
            decode_options = {"require": ["exp", "iss", "sub"]}
            if not self._audience:
                decode_options["verify_aud"] = False
            claims = jwt.decode(
                bearer_token,
                key=key,
                algorithms=list(_ALGORITHMS),
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._clock_skew_seconds,
                options=decode_options,
            )
            return _principal_from_claims(claims)
        except ApiError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise ApiError(401, "invalid_token", "Token de acesso inválido.") from exc

    async def _key_for(self, kid: str) -> Mapping[str, Any]:
        now = monotonic()
        if now >= self._cache_expires_at:
            await self._refresh_keys()
        key = self._keys.get(kid)
        if key is None:
            # A rotation can introduce a key before the bounded cache expires.
            await self._refresh_keys()
            key = self._keys.get(kid)
        if key is None:
            raise jwt.InvalidTokenError("unknown signing key")
        return key

    async def _refresh_keys(self) -> None:
        async with self._cache_lock:
            result = self._fetcher(self._jwks_url)
            try:
                document = await result if isinstance(result, Awaitable) else result
                keys = document.get("keys")
                if not isinstance(keys, list) or not 1 <= len(keys) <= _MAX_JWKS_KEYS:
                    raise ValueError("invalid JWKS key set")
                parsed: dict[str, Mapping[str, Any]] = {}
                for item in keys:
                    if not isinstance(item, Mapping):
                        raise TypeError("invalid JWK")
                    kid = _required_text(item, "kid")
                    if item.get("kty") != "RSA" or item.get("alg") not in (None, "RS256"):
                        continue
                    parsed[kid] = item
                if not parsed:
                    raise ValueError("JWKS has no supported signing keys")
            except (OSError, TypeError, ValueError) as exc:
                raise ApiError(
                    503, "identity_unavailable", "Provedor de identidade indisponível."
                ) from exc
            self._keys = parsed
            self._cache_expires_at = monotonic() + self._cache_ttl_seconds


def _principal_from_claims(claims: Mapping[str, Any]) -> IdentityPrincipal:
    subject = _required_text(claims, "sub")
    claimed_user = claims.get("user_id")
    if claimed_user is not None and claimed_user != subject:
        raise jwt.InvalidTokenError("user identity mismatch")
    organization = claims.get("o")
    if isinstance(organization, Mapping):
        organization_id = _required_text(organization, "id")
        provider_role = _required_text(organization, "rol")
    else:
        organization_id = _required_text(claims, "org_id")
        provider_role = _required_text(claims, "org_role")
    role = _ROLE_MAP.get(provider_role)
    if role is None:
        raise jwt.InvalidTokenError("unsupported organization role")
    membership_id = claims.get("org_membership_id") or claims.get("membership_id")
    if membership_id is None:
        membership_id = f"{organization_id}:{subject}"
    if not isinstance(membership_id, str) or not membership_id.strip():
        raise jwt.InvalidTokenError("invalid membership identity")
    return IdentityPrincipal(subject, organization_id, membership_id, role)


def _required_text(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise jwt.InvalidTokenError(f"invalid {key}")
    return value


async def _fetch_jwks(url: str) -> Mapping[str, Any]:
    def fetch() -> Mapping[str, Any]:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=5) as response:
            raw = response.read(_MAX_JWKS_BYTES + 1)
        if len(raw) > _MAX_JWKS_BYTES:
            raise ValueError("JWKS response is too large")
        document = json.loads(raw)
        if not isinstance(document, Mapping):
            raise TypeError("JWKS must be an object")
        return document

    return await asyncio.to_thread(fetch)
