import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.adapters.identity_oidc import OidcIdentityVerifier, _principal_from_claims


def test_clerk_v2_organization_claim_is_supported() -> None:
    principal = _principal_from_claims({
        "sub": "user_123",
        "o": {"id": "org_123", "rol": "admin", "slg": "kiara"},
    })
    assert principal.user_id == "user_123"
    assert principal.organization_id == "org_123"
    assert principal.role == "admin"


def test_token_without_active_organization_is_rejected() -> None:
    with pytest.raises(jwt.InvalidTokenError):
        _principal_from_claims({"sub": "user_123"})


def test_supabase_claims_use_verified_subject_as_personal_workspace() -> None:
    principal = _principal_from_claims({
        "sub": "2f408462-c353-446f-880d-232c613d26f1",
        "iss": "https://project.supabase.co/auth/v1",
        "role": "authenticated",
    })
    assert principal.user_id == "2f408462-c353-446f-880d-232c613d26f1"
    assert principal.organization_id == principal.user_id
    assert principal.membership_id == f"{principal.user_id}:{principal.user_id}"
    assert principal.role == "owner"


def test_supabase_es256_token_is_verified_from_jwks() -> None:
    issuer = "https://project.supabase.co/auth/v1"
    private_key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": "supabase-key", "alg": "ES256", "use": "sig"})
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "4e55ba8d-06f7-4893-8d9e-18b50cfbeb94",
            "iss": issuer,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "supabase-key", "typ": "JWT"},
    )
    verifier = OidcIdentityVerifier(
        issuer=issuer,
        audience="authenticated",
        jwks_url=f"{issuer}/.well-known/jwks.json",
        fetcher=lambda _: {"keys": [jwk]},
    )

    principal = asyncio.run(verifier.verify(token))

    assert principal.user_id == "4e55ba8d-06f7-4893-8d9e-18b50cfbeb94"
    assert principal.organization_id == principal.user_id
