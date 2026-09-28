from pathlib import Path

import pytest
from pydantic import ValidationError

from kiara_api.social import ChannelCreate, MediaCreate, PostCreate, PublicationConfirm


def test_social_models_forbid_tenant_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ChannelCreate(name="Canal", organization_id="other")
    with pytest.raises(ValidationError):
        PostCreate(content="Oi", channel_ids=["one"], provider="instagram")


def test_social_post_rejects_duplicate_resource_ids() -> None:
    with pytest.raises(ValidationError):
        PostCreate(content="Oi", channel_ids=["same", "same"])
    with pytest.raises(ValidationError):
        PostCreate(content="Oi", channel_ids=["channel"], media_ids=["same", "same"])


def test_social_media_accepts_only_declared_safe_types_and_size() -> None:
    MediaCreate(original_name="photo.jpg", content_type="image/jpeg", byte_size=42)
    with pytest.raises(ValidationError):
        MediaCreate(original_name="document.pdf", content_type="application/pdf", byte_size=42)
    with pytest.raises(ValidationError):
        MediaCreate(original_name="huge.mp4", content_type="video/mp4", byte_size=52_428_801)


def test_assisted_channels_and_public_confirmation_are_validated() -> None:
    assert ChannelCreate(name="Instagram", handle="@kiara", provider="instagram").provider == "instagram"
    assert PublicationConfirm(release_url="https://www.instagram.com/p/example/").release_url.startswith("https://")
    with pytest.raises(ValidationError):
        PublicationConfirm(release_url="http://localhost/private")


def test_social_migration_is_atomic_tenant_scoped_and_simulation_explicit() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0020_kiara_social.sql").read_text(encoding="utf-8")
    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    tables = ("social_channels", "social_media", "social_posts", "social_post_targets", "social_post_media", "social_publication_attempts")
    for table in tables:
        assert f"CREATE TABLE {table}" in sql
        assert f"'{table}'" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "FOREIGN KEY (organization_id,post_id)" in sql
    assert "FOREIGN KEY (organization_id,channel_id)" in sql
    assert "mode IN ('simulated','live')" in sql
    assert "status IN ('draft','pending_approval','approved','scheduled','publishing','simulated','published','failed','cancelled')" in sql


def test_assisted_delivery_migration_adds_local_storage_and_real_channels() -> None:
    sql = (Path(__file__).parents[1] / "migrations" / "0021_social_assisted_delivery.sql").read_text(encoding="utf-8")
    assert sql.lstrip().startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert "'instagram'" in sql
    assert "storage_kind IN ('local','metadata_only')" in sql
    assert "storage_key text" in sql
    assert "'ready_to_publish'" in sql
