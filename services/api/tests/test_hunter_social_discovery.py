import asyncio
from email.message import Message

import pytest
from kiara_api import hunter


@pytest.mark.parametrize(("source", "url", "valid"), [
    ("instagram", "https://instagram.com/clinica.real/", True),
    ("instagram", "https://instagram.com/p/ABCDEF/", False),
    ("instagram", "https://instagram.com/accounts/login/", False),
    ("facebook", "https://facebook.com/profile.php?id=12345", True),
    ("facebook", "https://facebook.com/profile.php?id=abc", False),
    ("facebook", "https://facebook.com/clinica/posts/123", False),
    ("facebook", "https://facebook.com/groups/123", False),
    ("facebook", "https://facebook.com.evil.test/clinica", False),
])
def test_discovery_accepts_only_profile_identities(source, url, valid):
    assert bool(hunter._social_profile_url(url, source)) is valid


def test_website_discovery_uses_observed_links_without_promoting_them_to_verified(monkeypatch):
    async def search(query, source, limit):
        assert source == "web"
        return [{"title": "Clínica", "url": "https://clinic.example/"}]

    def fetch(url):
        return "", ["https://instagram.com/clinica/", "https://instagram.com/p/abcdef/",
                    "https://instagram.com/clinica/"], "native"

    monkeypatch.setattr(hunter, "exa_search", search)
    monkeypatch.setattr(hunter, "_fetch_public_page", fetch)
    rows = asyncio.run(hunter.website_social_search("clínicas RS", "instagram", 5))
    assert len(rows) == 1
    assert rows[0]["url"] == "https://instagram.com/clinica/"
    assert rows[0]["public_data"] == {
        "provider": "website_profile_link", "discovery_url": "https://clinic.example/",
    }
    assert not hunter._instagram_profile_matches(rows[0], {"query": "clínicas", "location": "RS"})


def test_social_search_recovers_from_empty_indexes_using_website_links(monkeypatch):
    async def empty(*_):
        return []

    async def linked(query, source, limit):
        assert query == "dentistas Porto Alegre"
        return [{"source": source, "url": "https://facebook.com/clinica/", "title": "Clínica"}]

    async def broken(*_):
        raise AssertionError("Do not call the unavailable HTML index after recovering profiles")

    monkeypatch.setattr(hunter, "exa_search", empty)
    monkeypatch.setattr(hunter, "firecrawl_search", empty)
    monkeypatch.setattr(hunter, "website_social_search", linked)
    monkeypatch.setattr(hunter, "indexed_search", broken)
    rows = asyncio.run(hunter.public_search("dentistas Porto Alegre", "facebook", 2))
    assert rows[0]["url"] == "https://facebook.com/clinica/"


@pytest.mark.parametrize(("final_url", "description", "accepted"), [
    ("https://instagram.com/clinica/", "Odontologia em Porto Alegre. Telefone: 5132251122", True),
    ("https://instagram.com/accounts/login/", "Odontologia em Porto Alegre", False),
    ("https://instagram.com/clinica/", "Log in to Instagram", False),
    ("https://instagram.com/clinica/", "Faça login para ver fotos", False),
    ("https://instagram.com/outra/", "Odontologia em Porto Alegre", False),
])
def test_login_and_unrelated_redirects_are_never_profile_evidence(monkeypatch, final_url, description, accepted):
    class Response:
        headers = Message()
        headers["Content-Type"] = "text/html"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def geturl(self):
            return final_url

        def read(self, _):
            return f'<meta property="og:description" content="{description}">'.encode()

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(hunter, "_assert_public_destination", lambda _: None)
    monkeypatch.setattr(hunter, "build_opener", lambda *_: Opener())
    result = hunter._read_public_instagram_bio("https://instagram.com/clinica/")
    assert bool(result) is accepted


@pytest.mark.parametrize(("source", "status", "final_path", "description", "accepted"), [
    ("instagram", 200, "clinica/", "Clínica odontológica em Porto Alegre", True),
    ("facebook", 200, "clinica/", "Clínica odontológica em Porto Alegre", True),
    ("instagram", 200, "accounts/login/", "Clínica odontológica em Porto Alegre", False),
    ("facebook", 200, "clinica/", "Log in to Facebook", False),
    ("facebook", 403, "clinica/", "Clínica odontológica em Porto Alegre", False),
])
def test_firecrawl_profile_fallback_requires_current_successful_profile_metadata(
    monkeypatch, source, status, final_path, description, accepted,
):
    captured = {}

    def post(url, headers, body):
        captured.update(body)
        return {"success": True, "data": {"metadata": {
            "statusCode": status, "url": f"https://{source}.com/{final_path}", "description": description,
        }}}

    monkeypatch.setenv("FIRECRAWL_API_KEY", "test")
    monkeypatch.setattr(hunter, "_assert_public_destination", lambda _: None)
    monkeypatch.setattr(hunter, "_post_json", post)
    value = hunter._firecrawl_social_description(f"https://{source}.com/clinica/", source)
    assert bool(value) is accepted
    assert captured["maxAge"] == 0
    assert captured["proxy"] == "basic"
    assert "cookies" not in captured
