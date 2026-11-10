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


@pytest.mark.parametrize("status,version,expected_code", [("draft", 2, 412), ("published", 1, 409), (None, 1, 404)])
def test_edit_rejects_conflicts_and_completed_posts(status, version, expected_code):
    import asyncio
    from contextlib import asynccontextmanager
    from kiara_api.social import SocialRepository
    from kiara_api.http.context import RequestContext
    from kiara_api.http.errors import ApiError

    class Connection:
        async def execute(self, sql, params):
            assert "organization_id=%s AND id=%s FOR UPDATE" in sql
            return self
        async def fetchone(self):
            return {"status": status, "version": version} if status else None
    class Store:
        @asynccontextmanager
        async def _transaction(self, organization_id):
            assert organization_id == "org-test"
            yield Connection()
    context = RequestContext("user", "org-test", "member", "admin", "test")
    with pytest.raises(ApiError) as error:
        asyncio.run(SocialRepository(Store()).create_post(context, PostCreate(content="Edited", channel_ids=["channel"]), post_id="post", expected_version=1))
    assert error.value.status_code == expected_code


def test_edit_updates_same_post_and_replaces_resources_atomically():
    import asyncio
    from contextlib import asynccontextmanager
    from kiara_api.social import SocialRepository
    from kiara_api.http.context import RequestContext
    from kiara_api.adapters.postgres import _uuid
    from datetime import UTC, datetime

    queries = []
    class Connection:
        async def execute(self, sql, params):
            queries.append((sql, params))
            self.sql = sql
            return self
        async def fetchone(self):
            if "FOR UPDATE" in self.sql:
                return {"status": "draft", "version": 1}
            return {"id": _uuid("social-post", "post"), "content": "Edited", "status": "ready_to_publish", "version": 2, "created_at": datetime.now(UTC)}
        async def fetchall(self):
            return [{"id": "resource"}]
    class Store:
        @asynccontextmanager
        async def _transaction(self, organization_id):
            assert organization_id == "org-test"
            yield Connection()
    context = RequestContext("user", "org-test", "member", "admin", "test")
    result = asyncio.run(SocialRepository(Store()).create_post(context, PostCreate(content="Edited", channel_ids=["channel"], media_ids=["media"], action="prepare"), post_id="post", expected_version=1))
    assert result["id"] == str(_uuid("social-post", "post"))
    assert result["version"] == 2
    assert not any("INSERT INTO social_posts(" in sql for sql, _ in queries)
    assert any("DELETE FROM social_post_media" in sql for sql, _ in queries)
    assert all(_uuid("organization", "org-test") in params for _, params in queries)


@pytest.mark.parametrize("role,if_match,expected_status", [("admin", None, 428), ("admin", "bad", 422), ("admin", '"0"', 422), ("viewer", '"1"', 403), ("admin", '"1"', 200)])
def test_edit_http_requires_current_version_and_write_role(role, if_match, expected_status):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from fastapi.responses import JSONResponse
    from kiara_api.social import create_social_router
    from kiara_api.http.context import RequestContext
    from kiara_api.http.dependencies import authenticated_context
    from kiara_api.http.errors import ApiError

    class Repository:
        async def create_post(self, context, payload, *, post_id, expected_version):
            assert context.organization_id == "org-test"
            assert post_id == "post" and expected_version == 1
            return {"id": post_id, "version": 2}
    app = FastAPI()
    app.include_router(create_social_router(Repository()))
    app.dependency_overrides[authenticated_context] = lambda: RequestContext("user", "org-test", "member", role, "test")
    @app.exception_handler(ApiError)
    async def handle_error(request, error):
        return JSONResponse({"error": "rejected"}, status_code=error.status_code)
    headers = {"If-Match": if_match} if if_match else {}
    response = TestClient(app).put("/v1/social/posts/post", json={"content": "Edited", "channel_ids": ["channel"]}, headers=headers)
    assert response.status_code == expected_status
