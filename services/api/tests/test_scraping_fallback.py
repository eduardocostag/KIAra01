import sys
import types

import pytest

from kiara_api import scraping_adapters


class _Response:
    def __init__(self, status, headers, body=b""):
        self.status_code, self.headers, self._body = status, headers, body

    def iter_content(self):
        yield self._body

    def close(self):
        pass


def _install_fake_curl(monkeypatch, responses, calls):
    def get(url, **options):
        calls.append((url, options))
        return responses.pop(0)

    package = types.ModuleType("curl_cffi")
    package.requests = types.SimpleNamespace(get=get)
    monkeypatch.setitem(sys.modules, "curl_cffi", package)
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", None)  # as on Vercel


def test_vercel_fallback_impersonates_chrome_and_follows_safe_redirects(monkeypatch):
    calls, checked = [], []
    _install_fake_curl(monkeypatch, [
        _Response(301, {"location": "https://padaria.example/"}),
        _Response(200, {"content-type": "text/html; charset=utf-8"}, "<body>CNPJ 11.222.333/0001-81 <a href='/contato'>Contato</a></body>".encode()),
    ], calls)
    monkeypatch.setattr("kiara_api.hunter._assert_public_destination", checked.append)
    text, links, final_url = scraping_adapters.fetch_public_with_scrapling("http://padaria.example/")
    assert final_url == "https://padaria.example/" and "11.222.333/0001-81" in text
    assert links == ["https://padaria.example/contato"]
    assert checked == ["http://padaria.example/", "https://padaria.example/"]
    assert all(options["impersonate"] == "chrome" and options["allow_redirects"] is False for _, options in calls)


def test_vercel_fallback_blocks_redirects_to_private_hosts(monkeypatch):
    _install_fake_curl(monkeypatch, [_Response(302, {"location": "http://127.0.0.1/admin"})], [])

    def guard(url):
        if "127.0.0.1" in url:
            raise ValueError("unsafe_destination")

    monkeypatch.setattr("kiara_api.hunter._assert_public_destination", guard)
    with pytest.raises(ValueError, match="unsafe_destination"):
        scraping_adapters.fetch_public_with_scrapling("https://padaria.example/")


def test_vercel_fallback_rejects_non_html_and_errors(monkeypatch):
    monkeypatch.setattr("kiara_api.hunter._assert_public_destination", lambda url: None)
    _install_fake_curl(monkeypatch, [_Response(200, {"content-type": "application/pdf"}, b"%PDF")], [])
    with pytest.raises(ValueError, match="unsupported_content"):
        scraping_adapters.fetch_public_with_scrapling("https://padaria.example/menu.pdf")
    _install_fake_curl(monkeypatch, [_Response(503, {})], [])
    with pytest.raises(OSError):
        scraping_adapters.fetch_public_with_scrapling("https://padaria.example/")
