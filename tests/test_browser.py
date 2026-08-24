import socket

import pytest

from app.browser.session import BrowserSession


@pytest.mark.parametrize("url", ["http://example.com", "file:///tmp/x", "https://u:p@example.com", "javascript:alert(1)", "https://localhost", "https://127.0.0.1", "https://169.254.169.254"])
def test_browser_rejects_unsafe_urls(url: str):
    with pytest.raises(ValueError):
        BrowserSession.validate_url(url)


def test_browser_accepts_https():
    BrowserSession.validate_url("https://example.com/path")


@pytest.mark.asyncio
async def test_browser_rejects_hostname_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(ValueError, match="não público"):
        await BrowserSession().validate_resolved_host("https://attacker.example")


@pytest.mark.asyncio
async def test_request_guard_aborts_private_subresources(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )

    class Route:
        aborted = False

        async def abort(self, _reason):
            self.aborted = True

        async def continue_(self):
            raise AssertionError("private request must not continue")

    route = Route()
    await BrowserSession()._guard_request(route, type("Request", (), {"url": "https://evil.test"})())
    assert route.aborted is True
