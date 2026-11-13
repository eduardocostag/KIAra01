import asyncio

import pytest
from kiara_api import hunter
from kiara_api.hunter_crm import _consumer_display_name, identity_keys
from kiara_api.hunter_research import (
    clean_summary,
    extract_contacts,
    normalize_result,
    phone_number,
)


@pytest.mark.parametrize("value,expected", [
    ("tel:(51)%203225-1122", "5132251122"),
    ("TEL:%2B55%20(51)%203225-1122", "+555132251122"),
    ("tel:+55-51-3225-1122;ext=999", "+555132251122"),
    ("(51) 3225-1122", "5132251122"),
    ("tel:%252B55%25205132251122", None),
    ("https://example.com/551132251122", None),
    ("id-2026-551132251122", None),
    ("tel:5132251122?tracking=123", None),
])
def test_phone_decodes_uri_without_concatenating_encoding_or_extensions(value, expected):
    assert phone_number(value) == expected


def test_extraction_uses_decoded_phone_and_does_not_invent_whatsapp():
    assert extract_contacts("", ["TEL:(51)%203225-1122"]) == {"phone": "5132251122", "whatsapp_url": None}


@pytest.mark.parametrize("source,urls,count", [
    ("facebook", ["https://facebook.com/profile.php?id=111", "https://facebook.com/profile.php?id=222"], 2),
    ("google_maps", ["https://google.com/maps?cid=111", "https://google.com/maps?cid=222"], 2),
    ("web", ["https://example.com/BusinessA", "https://example.com/businessa"], 2),
    ("web", ["https://example.com/?business=1", "https://example.com/?business=2"], 2),
    ("facebook", ["https://www.facebook.com/profile.php?id=111&utm_source=a", "https://facebook.com/profile.php?utm_source=b&id=111#about"], 1),
])
def test_discovery_preserves_identity_and_discards_only_tracking(monkeypatch, source, urls, count):
    async def found(_query, _source, _limit):
        return [{"source": source, "title": f"Business {index}", "url": url} for index, url in enumerate(urls)]

    monkeypatch.setattr(hunter, "public_search", found)
    rows = asyncio.run(hunter.multi_public_search(["search one", "search two"], source, 10))
    assert len(rows) == count
    if count == 2:
        assert identity_keys(rows[0]) != identity_keys(rows[1])


def test_web_name_is_readable_and_preserves_original_unverified_title():
    title = "Rede de Clínicas Médicas, Grande Porto Alegre - RS | Salute Saúde e Odontologia"
    row = normalize_result({"source": "web", "url": "https://www.clinicasalute.com.br/", "title": title})
    assert row["public_data"]["display_name"] == "Salute Saúde e Odontologia"
    assert row["public_data"]["source_title"] == title
    assert row["public_data"]["name_status"] == "source_title"
    assert _consumer_display_name(row, None) == "Salute Saúde e Odontologia"
    assert normalize_result(row)["public_data"]["source_title"] == title


def test_web_name_does_not_guess_brand_from_unrelated_title_segments():
    title = "Clínica Aurora | Promoções e notícias"
    row = normalize_result({"source": "web", "url": "https://unrelated.example/", "title": title})
    assert row["public_data"]["display_name"] == clean_summary(title)


def test_numeric_facebook_profiles_are_actually_inspected_but_posts_are_not(monkeypatch):
    inspected = []

    def about(url):
        inspected.append(url)
        return "Clínica odontológica em Porto Alegre. Telefone: (51) 3225-1122"

    monkeypatch.setattr(hunter, "_read_public_facebook_about", about)
    rows = [{"source": "facebook", "title": "Clínica", "url": url} for url in [
        "https://facebook.com/profile.php?id=111", "https://facebook.com/profile.php?id=222",
        "https://facebook.com/profile.php?id=invalid", "https://facebook.com/clinica/posts/123",
    ]]
    asyncio.run(hunter.inspect_facebook_pages(rows))
    assert set(inspected) == {rows[0]["url"], rows[1]["url"]}
    assert [row["public_data"]["profile_handle"] for row in rows[:2]] == ["111", "222"]
    assert all(row["public_data"]["page_status"] == "verified_public_page" for row in rows[:2])
    assert all("public_data" not in row for row in rows[2:])
