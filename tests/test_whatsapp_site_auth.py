import io
import json

import pytest

from app.whatsapp.site_auth import SiteLoginError, SiteSession


class Opener:
    def __init__(self):
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        n = len(self.requests)
        return io.BytesIO(json.dumps({"access_token": f"access-{n}", "refresh_token": f"refresh-{n}", "expires_in": 3600}).encode())


def test_refresh_rotates_token_without_reusing_password():
    clock = [100]
    opener = Opener()
    session = SiteSession("https://example.supabase.co", "public", clock=lambda: clock[0], opener=opener)
    session.login("owner@example.test", "not-a-real-password")
    assert session.token() == "access-1"
    clock[0] = 3650
    assert session.token() == "access-2"
    assert json.loads(opener.requests[1].data) == {"refresh_token": "refresh-1"}
    assert "grant_type=refresh_token" in opener.requests[1].full_url


@pytest.mark.parametrize("url", ["http://example.test", "https://user:pass@example.test", "https://example.test?secret=x"])
def test_rejects_insecure_or_credential_bearing_url(url):
    with pytest.raises(SiteLoginError):
        SiteSession(url, "public")


def test_invalid_provider_response_is_sanitized():
    class Broken:
        def open(self, request, timeout):
            raise ValueError("secret-password")
    session = SiteSession("https://example.supabase.co", "public", opener=Broken())
    with pytest.raises(SiteLoginError) as error:
        session.login("x", "secret-password")
    assert "secret-password" not in str(error.value)
    with pytest.raises(SiteLoginError):
        session.token()
