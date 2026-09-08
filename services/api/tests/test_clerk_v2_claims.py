from pathlib import Path
import sys

import jwt
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from kiara_api.adapters.identity_oidc import _principal_from_claims


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
