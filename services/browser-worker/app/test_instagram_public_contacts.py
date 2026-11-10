from __future__ import annotations

import pytest

from .instagram import _profile, collect_instagram_followers


def profile(**fields):
    return _profile({"pk": "123", "username": "example", **fields}, relationship="follows")


def test_preserves_explicit_public_contacts_with_evidence():
    result = profile(public_email="sales@example.com", public_phone_number="+55 (11) 99999-1234")
    assert result["email"] == "sales@example.com"
    assert result["phone_number"] == "+55 (11) 99999-1234"
    assert result["contact_evidence"]["email"]["field"] == "public_email"
    assert result["contact_evidence"]["phone_number"]["profile_url"] == result["profile_url"]


def test_extracts_email_written_in_biography():
    result = profile(biography="Contato: hello@example.com. Obrigado!")
    assert result["email"] == "hello@example.com"
    assert result["contact_evidence"]["email"]["field"] == "biography"


def test_prefers_explicit_public_email_over_biography():
    assert profile(public_email="sales@example.com", biography="hello@example.com")["email"] == "sales@example.com"


def test_private_profile_never_exports_contacts():
    result = profile(is_private=True, public_email="sales@example.com", public_phone_number="5511999991234", biography="hello@example.com")
    assert not {"email", "phone_number", "contact_evidence"} & result.keys()


@pytest.mark.parametrize("fields", [
    {},
    {"email": "private@example.com", "phone_number": "5511999991234"},
    {"public_email": "invalid", "public_phone_number": "123"},
    {"biography": "contato em example ponto com"},
])
def test_does_not_infer_contacts_or_use_nonpublic_fields(fields):
    result = profile(**fields)
    assert not {"email", "phone_number", "contact_evidence"} & result.keys()


def test_collection_preserves_contact_without_changing_limit_or_cursor():
    items, snapshot = collect_instagram_followers("example", {"users": [
        {"pk": "1", "username": "first", "public_email": "first@example.com"},
        {"pk": "2", "username": "second", "public_email": "second@example.com"},
    ], "next_max_id": "next-page"}, limit=1)
    assert len(items) == 1
    assert items[0]["email"] == "first@example.com"
    assert snapshot["next_max_id"] == "next-page"
