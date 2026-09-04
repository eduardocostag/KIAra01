from __future__ import annotations

import sqlite3

import pytest

from app.consumers import B2CStage, ConsumerStore


def test_deduplicates_by_platform_scoped_id_and_declared_contact(tmp_path):
    store = ConsumerStore(tmp_path / "consumers.db")
    first = store.upsert_person(display_name="Ana", platform="Instagram", scoped_id="ig-1")
    same_social = store.upsert_person(display_name="Ana Silva", platform="instagram", scoped_id="ig-1")
    with_email = store.upsert_person(display_name="Bia", email="BIA@EXAMPLE.COM")
    same_email = store.upsert_person(display_name="Beatriz", email="bia@example.com")

    assert first == same_social
    assert with_email == same_email
    assert len(store.list_people()) == 2
    assert store.get_person(first).display_name == "Ana Silva"


def test_refuses_ambiguous_identity_merge(tmp_path):
    store = ConsumerStore(tmp_path / "consumers.db")
    store.upsert_person(platform="instagram", scoped_id="one")
    store.upsert_person(email="person@example.com")

    with pytest.raises(ValueError, match="conflitantes"):
        store.upsert_person(platform="instagram", scoped_id="one", email="person@example.com")


def test_consent_expiration_and_global_opt_out(tmp_path):
    store = ConsumerStore(tmp_path / "consumers.db")
    person = store.upsert_person(email="client@example.com")
    store.record_consent(
        person, channel="email", purpose="marketing", expires_at="2030-01-01T00:00:00+00:00"
    )
    assert store.can_contact(
        person, channel="email", purpose="marketing", contact_kind="email",
        contact_value="CLIENT@example.com", at="2029-01-01T00:00:00+00:00",
    )
    assert not store.has_active_consent(
        person, channel="email", purpose="marketing", at="2031-01-01T00:00:00+00:00"
    )

    store.suppress_contact("email", "client@example.com")
    assert not store.can_contact(
        person, channel="email", purpose="marketing", contact_kind="email",
        contact_value="client@example.com", at="2029-01-01T00:00:00+00:00",
    )


def test_touchpoints_stage_and_retention_cascade_but_keep_suppression(tmp_path):
    path = tmp_path / "consumers.db"
    store = ConsumerStore(path)
    person = store.upsert_person(
        display_name="Carlos", phone="(11) 99999-0000", retained_until="2028-01-01T00:00:00+00:00"
    )
    assert store.set_stage(person, B2CStage.READY_TO_BUY)
    store.add_identity(person, platform="tiktok", scoped_id="tt-7", handle="carlos")
    store.add_touchpoint(person, platform="tiktok", kind="lead_form", direction="inbound")
    store.record_consent(person, channel="whatsapp", purpose="vendas")
    store.suppress_contact("phone", "11999990000")

    assert store.get_person(person).stage is B2CStage.READY_TO_BUY
    assert len(store.identities(person)) == 1
    assert len(store.touchpoints(person)) == 1
    assert store.purge_expired(at="2029-01-01T00:00:00+00:00") == 1
    assert store.get_person(person) is None
    assert store.is_suppressed("phone", "11 99999-0000")


def test_migration_is_additive(tmp_path):
    path = tmp_path / "consumers.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE legacy_data (value TEXT)")
    connection.execute("INSERT INTO legacy_data VALUES ('preserve')")
    connection.commit()
    connection.close()

    store = ConsumerStore(path)
    store.close()
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT value FROM legacy_data").fetchone()[0] == "preserve"
    assert connection.execute("PRAGMA user_version").fetchone()[0] >= 1
    connection.close()
