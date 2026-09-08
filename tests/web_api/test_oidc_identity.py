from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

jwt = pytest.importorskip("jwt")
pytest.importorskip("cryptography")
from cryptography.hazmat.primitives.asymmetric import rsa

from services.api.kiara_api.adapters.identity_oidc import OidcIdentityVerifier
from services.api.kiara_api.config import ApiSettings
from services.api.kiara_api.http.errors import ApiError

ISSUER = "https://identity.kiara.test"
AUDIENCE = "kiara-api"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"


@pytest.fixture
def signing_material():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig"})
    return private_key, {"keys": [public_jwk]}


def token(private_key, **overrides):
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user_123",
        "user_id": "user_123",
        "org_id": "org_123",
        "org_role": "org:admin",
        "org_membership_id": "membership_123",
        "iat": now,
        "nbf": now - timedelta(seconds=1),
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "key-1"})


@pytest.mark.asyncio
async def test_verifies_signature_claims_and_uses_bounded_jwks_cache(signing_material) -> None:
    private_key, jwks = signing_material
    calls = 0

    async def fetcher(url: str):
        nonlocal calls
        calls += 1
        assert url == JWKS_URL
        return jwks

    verifier = OidcIdentityVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        fetcher=fetcher,
        cache_ttl_seconds=60,
    )
    principal = await verifier.verify(token(private_key))
    repeated = await verifier.verify(token(private_key))

    assert principal.user_id == "user_123"
    assert principal.organization_id == "org_123"
    assert principal.membership_id == "membership_123"
    assert principal.role == "admin"
    assert repeated == principal
    assert calls == 1


@pytest.mark.asyncio
async def test_derives_membership_key_only_from_verified_tenant_and_subject(
    signing_material,
) -> None:
    private_key, jwks = signing_material
    verifier = _verifier(jwks)
    principal = await verifier.verify(token(private_key, org_membership_id=None))
    assert principal.membership_id == "org_123:user_123"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://attacker.test"},
        {"aud": "different-api"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"nbf": datetime.now(UTC) + timedelta(minutes=2)},
        {"sub": ""},
        {"user_id": "different-user"},
        {"org_id": ""},
        {"org_role": "org:super-admin"},
    ],
)
async def test_rejects_invalid_identity_and_time_claims(signing_material, overrides) -> None:
    private_key, jwks = signing_material
    with pytest.raises(ApiError) as caught:
        await _verifier(jwks).verify(token(private_key, **overrides))
    assert caught.value.status_code == 401
    assert caught.value.code == "invalid_token"
    assert caught.value.details == {}


@pytest.mark.asyncio
async def test_rejects_forged_signature(signing_material) -> None:
    _, jwks = signing_material
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(ApiError) as caught:
        await _verifier(jwks).verify(token(attacker_key))
    assert caught.value.status_code == 401
    assert caught.value.code == "invalid_token"


@pytest.mark.asyncio
async def test_jwks_failure_is_fail_closed_without_leaking_provider_details(
    signing_material,
) -> None:
    private_key, _ = signing_material

    async def failed_fetch(_url: str):
        raise OSError("private DNS detail")

    verifier = OidcIdentityVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        fetcher=failed_fetch,
    )
    with pytest.raises(ApiError) as caught:
        await verifier.verify(token(private_key))
    assert caught.value.status_code == 503
    assert caught.value.code == "identity_unavailable"
    assert "DNS" not in caught.value.message


def test_oidc_configuration_is_complete_https_and_bounded() -> None:
    with pytest.raises(RuntimeError, match="configured together"):
        ApiSettings(oidc_issuer=ISSUER).validate()
    with pytest.raises(RuntimeError, match="HTTPS"):
        ApiSettings(
            oidc_issuer=ISSUER,
            oidc_audience=AUDIENCE,
            oidc_jwks_url="http://identity.test/jwks",
        ).validate()
    with pytest.raises(RuntimeError, match="between 30 and 3600"):
        ApiSettings(oidc_jwks_cache_ttl_seconds=86_400).validate()


def _verifier(jwks) -> OidcIdentityVerifier:
    return OidcIdentityVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        fetcher=lambda _url: jwks,
    )
