from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError


SocialProvider = Literal["instagram", "facebook", "threads", "linkedin", "tiktok", "youtube", "generic", "simulated"]


class ChannelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    handle: str | None = Field(default=None, max_length=160)
    provider: SocialProvider = "instagram"


class MediaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_name: str = Field(min_length=1, max_length=255)
    content_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp", "video/mp4"]
    byte_size: int = Field(ge=1, le=52_428_800)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(default="", max_length=10_000)
    channel_ids: list[str] = Field(min_length=1, max_length=20)
    media_ids: list[str] = Field(default_factory=list, max_length=20)
    action: Literal["draft", "schedule", "prepare"] = "draft"
    scheduled_at: datetime | None = None

    @field_validator("channel_ids", "media_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        clean = [item.strip() for item in value if item.strip()]
        if len(clean) != len(set(clean)):
            raise ValueError("Identificadores duplicados não são permitidos.")
        return clean


class PublicationConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    release_url: str = Field(min_length=10, max_length=2000)

    @field_validator("release_url")
    @classmethod
    def public_https_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Informe uma URL HTTPS pública da publicação.")
        return value.strip()


class SocialRepository:
    def __init__(self, postgres: PostgresRepository | None, media_root: Path | None = None) -> None:
        self._postgres = postgres
        self._media_root = (media_root or Path(os.getenv("KIARA_SOCIAL_MEDIA_DIR", "data/social-media"))).resolve()

    def _store(self) -> PostgresRepository:
        if self._postgres is None:
            raise ApiError(503, "social_store_unavailable", "A Kiara Social API requer o banco PostgreSQL configurado.")
        return self._postgres

    def media_path(self, storage_key: str) -> Path:
        candidate = (self._media_root / storage_key).resolve()
        if self._media_root not in candidate.parents:
            raise ApiError(422, "social_media_path_invalid", "Arquivo de mídia inválido.")
        return candidate

    @staticmethod
    def _channel(row: dict[str, Any]) -> dict[str, Any]:
        return {**row, "id": str(row["id"]), "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"])}

    @staticmethod
    def _post(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for key in ("id",):
            result[key] = str(result[key])
        for key in ("scheduled_at", "approved_at", "published_at", "created_at", "updated_at"):
            result[key] = _iso(result.get(key))
        return result

    async def dashboard(self, organization_id: str) -> dict[str, Any]:
        organization_uuid = _uuid("organization", organization_id)
        async with self._store()._transaction(organization_id) as connection:
            channels = await (await connection.execute(
                "SELECT id,provider,name,handle,status,capabilities,created_at,updated_at FROM social_channels WHERE organization_id=%s ORDER BY created_at,id",
                (organization_uuid,),
            )).fetchall()
            posts = await (await connection.execute(
                """SELECT p.id,p.content,p.status,p.scheduled_at,p.approved_at,p.published_at,p.version,p.created_at,p.updated_at,
                          COALESCE((SELECT jsonb_agg(jsonb_build_object('id',t.id,'status',t.status,'channel_id',t.channel_id,'channel_name',c.name,'provider',c.provider,'release_url',t.release_url,'provider_post_id',t.provider_post_id) ORDER BY t.created_at) FROM social_post_targets t JOIN social_channels c ON c.organization_id=t.organization_id AND c.id=t.channel_id WHERE t.organization_id=p.organization_id AND t.post_id=p.id),'[]'::jsonb) targets,
                          COALESCE((SELECT jsonb_agg(jsonb_build_object('id',m.id,'name',m.original_name,'content_type',m.content_type,'byte_size',m.byte_size,'status',m.status) ORDER BY pm.position) FROM social_post_media pm JOIN social_media m ON m.organization_id=pm.organization_id AND m.id=pm.media_id WHERE pm.organization_id=p.organization_id AND pm.post_id=p.id),'[]'::jsonb) media
                   FROM social_posts p WHERE p.organization_id=%s ORDER BY p.created_at DESC LIMIT 200""",
                (organization_uuid,),
            )).fetchall()
        return {"channels": [self._channel(row) for row in channels], "posts": [self._post(row) for row in posts], "capabilities": {"drafts": True, "scheduling": True, "publishing": "assisted", "analytics": "manual", "media_storage": "local"}}

    async def create_channel(self, context: RequestContext, payload: ChannelCreate) -> dict[str, Any]:
        organization_uuid = _uuid("organization", context.organization_id)
        async with self._store()._transaction(context.organization_id) as connection:
            row = await (await connection.execute(
                """INSERT INTO social_channels(organization_id,id,provider,name,handle)
                   VALUES(%s,%s,%s,%s,%s) RETURNING id,provider,name,handle,status,capabilities,created_at,updated_at""",
                (organization_uuid, uuid4(), payload.provider, payload.name.strip(), payload.handle.strip() if payload.handle else None),
            )).fetchone()
        return self._channel(row)

    async def create_media(self, context: RequestContext, payload: MediaCreate, raw: bytes) -> dict[str, Any]:
        if len(raw) != payload.byte_size:
            raise ApiError(422, "social_media_size_mismatch", "O tamanho da mídia não corresponde ao arquivo recebido.")
        digest = hashlib.sha256(raw).hexdigest()
        if payload.checksum_sha256 and payload.checksum_sha256 != digest:
            raise ApiError(422, "social_media_checksum_mismatch", "A integridade da mídia não pôde ser confirmada.")
        organization_uuid, user_uuid = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        media_id = uuid4()
        suffixes = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp", "video/mp4": ".mp4"}
        storage_key = f"{organization_uuid.hex}/{media_id.hex}{suffixes[payload.content_type]}"
        destination = self.media_path(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(destination.write_bytes, raw)
        try:
            async with self._store()._transaction(context.organization_id) as connection:
                row = await (await connection.execute(
                    """INSERT INTO social_media(organization_id,id,original_name,content_type,byte_size,checksum_sha256,storage_kind,storage_key,status,created_by)
                       VALUES(%s,%s,%s,%s,%s,%s,'local',%s,'available',%s) RETURNING id,original_name,content_type,byte_size,checksum_sha256,storage_kind,status,created_at""",
                    (organization_uuid, media_id, payload.original_name.strip(), payload.content_type, payload.byte_size, digest, storage_key, user_uuid),
                )).fetchone()
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return {**row, "id": str(row["id"]), "created_at": _iso(row["created_at"])}

    async def get_media(self, organization_id: str, media_id: str) -> tuple[Path, str, str]:
        organization_uuid, media_uuid = _uuid("organization", organization_id), _uuid("social-media", media_id)
        async with self._store()._transaction(organization_id) as connection:
            row = await (await connection.execute("SELECT original_name,content_type,storage_key,status FROM social_media WHERE organization_id=%s AND id=%s", (organization_uuid, media_uuid))).fetchone()
        if not row or row["status"] != "available" or not row["storage_key"]:
            raise ApiError(404, "social_media_not_found", "Mídia não encontrada.")
        path = self.media_path(row["storage_key"])
        if not path.is_file():
            raise ApiError(404, "social_media_not_found", "O arquivo de mídia não está disponível.")
        return path, row["content_type"], row["original_name"]

    async def create_post(self, context: RequestContext, payload: PostCreate) -> dict[str, Any]:
        if not payload.content.strip() and not payload.media_ids:
            raise ApiError(422, "social_content_required", "Adicione texto ou mídia ao conteúdo.")
        scheduled = payload.scheduled_at
        if payload.action == "schedule" and (scheduled is None or scheduled.astimezone(UTC) <= datetime.now(UTC)):
            raise ApiError(422, "social_schedule_invalid", "O agendamento precisa estar no futuro.")
        organization_uuid, user_uuid = _uuid("organization", context.organization_id), _uuid("user", context.user_id)
        channel_uuids = [_uuid("social-channel", item) for item in payload.channel_ids]
        media_uuids = [_uuid("social-media", item) for item in payload.media_ids]
        async with self._store()._transaction(context.organization_id) as connection:
            channels = await (await connection.execute("SELECT id FROM social_channels WHERE organization_id=%s AND id=ANY(%s) AND status='active'", (organization_uuid, channel_uuids))).fetchall()
            if len(channels) != len(channel_uuids):
                raise ApiError(422, "social_channel_invalid", "Um ou mais canais não estão disponíveis.")
            if media_uuids:
                media = await (await connection.execute("SELECT id FROM social_media WHERE organization_id=%s AND id=ANY(%s)", (organization_uuid, media_uuids))).fetchall()
                if len(media) != len(media_uuids):
                    raise ApiError(422, "social_media_invalid", "Uma ou mais mídias não pertencem ao workspace.")
            status = "draft" if payload.action == "draft" else "scheduled" if payload.action == "schedule" else "ready_to_publish"
            post_id = uuid4()
            row = await (await connection.execute(
                """INSERT INTO social_posts(organization_id,id,content,status,scheduled_at,approved_by,approved_at,created_by)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,content,status,scheduled_at,approved_at,published_at,version,created_at,updated_at""",
                (organization_uuid, post_id, payload.content.strip(), status, scheduled if payload.action == "schedule" else None, user_uuid if payload.action == "prepare" else None, datetime.now(UTC) if payload.action == "prepare" else None, user_uuid),
            )).fetchone()
            for channel_id in channel_uuids:
                target_status = "scheduled" if payload.action == "schedule" else "ready_to_publish" if payload.action == "prepare" else "draft"
                await connection.execute("INSERT INTO social_post_targets(organization_id,id,post_id,channel_id,status) VALUES(%s,%s,%s,%s,%s)", (organization_uuid, uuid4(), post_id, channel_id, target_status))
            for position, media_id in enumerate(media_uuids):
                await connection.execute("INSERT INTO social_post_media(organization_id,post_id,media_id,position) VALUES(%s,%s,%s,%s)", (organization_uuid, post_id, media_id, position))
        return self._post(row)

    async def publication_package(self, organization_id: str, post_id: str) -> dict[str, Any]:
        organization_uuid, post_uuid = _uuid("organization", organization_id), _uuid("social-post", post_id)
        async with self._store()._transaction(organization_id) as connection:
            post = await (await connection.execute("SELECT id,content,status,scheduled_at,version FROM social_posts WHERE organization_id=%s AND id=%s", (organization_uuid, post_uuid))).fetchone()
            if not post:
                raise ApiError(404, "social_post_not_found", "Conteúdo não encontrado.")
            targets = await (await connection.execute("SELECT c.name,c.handle,c.provider,t.status,t.release_url FROM social_post_targets t JOIN social_channels c ON c.organization_id=t.organization_id AND c.id=t.channel_id WHERE t.organization_id=%s AND t.post_id=%s ORDER BY t.created_at", (organization_uuid, post_uuid))).fetchall()
            media = await (await connection.execute("SELECT m.id,m.original_name,m.content_type,m.byte_size FROM social_post_media pm JOIN social_media m ON m.organization_id=pm.organization_id AND m.id=pm.media_id WHERE pm.organization_id=%s AND pm.post_id=%s ORDER BY pm.position", (organization_uuid, post_uuid))).fetchall()
        return {"id": str(post["id"]), "content": post["content"], "status": post["status"], "scheduled_at": _iso(post["scheduled_at"]), "version": post["version"], "delivery_mode": "assisted", "targets": targets, "media": [{**item, "id": str(item["id"]), "download_url": f"/api/content/media/{item['id']}"} for item in media]}

    async def confirm_publication(self, context: RequestContext, post_id: str, expected_version: int, payload: PublicationConfirm) -> dict[str, Any]:
        organization_uuid, post_uuid = _uuid("organization", context.organization_id), _uuid("social-post", post_id)
        async with self._store()._transaction(context.organization_id) as connection:
            post = await (await connection.execute("SELECT status,version FROM social_posts WHERE organization_id=%s AND id=%s FOR UPDATE", (organization_uuid, post_uuid))).fetchone()
            if not post:
                raise ApiError(404, "social_post_not_found", "Conteúdo não encontrado.")
            if post["version"] != expected_version:
                raise ApiError(412, "version_conflict", "O conteúdo foi alterado. Atualize a página.")
            if post["status"] not in {"ready_to_publish", "scheduled", "simulated"}:
                raise ApiError(409, "social_post_not_confirmable", "Prepare o pacote antes de confirmar a publicação.")
            await connection.execute("UPDATE social_post_targets SET status='published',release_url=%s,provider_snapshot=%s,updated_at=now() WHERE organization_id=%s AND post_id=%s", (payload.release_url, Jsonb({"delivery_mode": "assisted", "confirmed_by_user": True}), organization_uuid, post_uuid))
            row = await (await connection.execute("UPDATE social_posts SET status='published',published_at=now(),version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s RETURNING id,content,status,scheduled_at,approved_at,published_at,version,created_at,updated_at", (organization_uuid, post_uuid))).fetchone()
        return self._post(row)

    async def simulate_publish(self, context: RequestContext, post_id: str, expected_version: int) -> dict[str, Any]:
        organization_uuid, post_uuid = _uuid("organization", context.organization_id), _uuid("social-post", post_id)
        async with self._store()._transaction(context.organization_id) as connection:
            post = await (await connection.execute("SELECT id,status,version FROM social_posts WHERE organization_id=%s AND id=%s FOR UPDATE", (organization_uuid, post_uuid))).fetchone()
            if not post:
                raise ApiError(404, "social_post_not_found", "Conteúdo não encontrado.")
            if post["version"] != expected_version:
                raise ApiError(412, "version_conflict", "O conteúdo foi alterado. Atualize a página.")
            if post["status"] not in {"approved", "scheduled"}:
                raise ApiError(409, "social_post_not_publishable", "O conteúdo precisa estar aprovado ou agendado.")
            targets = await (await connection.execute("SELECT id FROM social_post_targets WHERE organization_id=%s AND post_id=%s FOR UPDATE", (organization_uuid, post_uuid))).fetchall()
            for target in targets:
                simulated_id = f"sim_{uuid4().hex}"
                await connection.execute("UPDATE social_post_targets SET status='simulated',provider_post_id=%s,provider_snapshot=%s,updated_at=now() WHERE organization_id=%s AND id=%s", (simulated_id, Jsonb({"mode": "simulated", "network_request": False}), organization_uuid, target["id"]))
                await connection.execute("INSERT INTO social_publication_attempts(organization_id,id,post_id,target_id,mode,outcome,response_snapshot) VALUES(%s,%s,%s,%s,'simulated','simulated',%s)", (organization_uuid, uuid4(), post_uuid, target["id"], Jsonb({"network_request": False})))
            row = await (await connection.execute("UPDATE social_posts SET status='simulated',published_at=now(),version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s RETURNING id,content,status,scheduled_at,approved_at,published_at,version,created_at,updated_at", (organization_uuid, post_uuid))).fetchone()
        result = self._post(row)
        result["publication_mode"] = "simulated"
        return result

    async def delete_post(self, context: RequestContext, post_id: str) -> None:
        organization_uuid, post_uuid = _uuid("organization", context.organization_id), _uuid("social-post", post_id)
        async with self._store()._transaction(context.organization_id) as connection:
            current = await (await connection.execute("SELECT status FROM social_posts WHERE organization_id=%s AND id=%s FOR UPDATE", (organization_uuid, post_uuid))).fetchone()
            if not current:
                raise ApiError(404, "social_post_not_found", "Conteúdo não encontrado.")
            if current["status"] in {"simulated", "published", "publishing"}:
                await connection.execute("UPDATE social_posts SET status='cancelled',version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s", (organization_uuid, post_uuid))
                await connection.execute("UPDATE social_post_targets SET status='cancelled',updated_at=now() WHERE organization_id=%s AND post_id=%s", (organization_uuid, post_uuid))
            else:
                await connection.execute("DELETE FROM social_posts WHERE organization_id=%s AND id=%s", (organization_uuid, post_uuid))


def create_social_router(repository: SocialRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/social", tags=["social"])

    def can_write(context: RequestContext) -> None:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Acesso restrito a operadores.")

    @router.get("/dashboard")
    async def dashboard(context: Annotated[RequestContext, Depends(authenticated_context)]):
        return await repository.dashboard(context.organization_id)

    @router.get("/channels")
    async def channels(context: Annotated[RequestContext, Depends(authenticated_context)]):
        return {"items": (await repository.dashboard(context.organization_id))["channels"]}

    @router.post("/channels", status_code=201)
    async def create_channel(payload: ChannelCreate, context: Annotated[RequestContext, Depends(authenticated_context)]):
        can_write(context)
        return await repository.create_channel(context, payload)

    @router.post("/media", status_code=201)
    async def create_media(
        request: Request,
        context: Annotated[RequestContext, Depends(authenticated_context)],
        original_name: Annotated[str, Header(alias="X-Kiara-Filename")],
        content_type: Annotated[str, Header(alias="Content-Type")],
    ):
        can_write(context)
        raw = await request.body()
        payload = MediaCreate(original_name=unquote(original_name), content_type=content_type, byte_size=len(raw))
        return await repository.create_media(context, payload, raw)

    @router.get("/media/{media_id}/download")
    async def download_media(media_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        path, content_type, filename = await repository.get_media(context.organization_id, media_id)
        return FileResponse(path, media_type=content_type, filename=filename)

    @router.get("/posts")
    async def posts(context: Annotated[RequestContext, Depends(authenticated_context)]):
        return {"items": (await repository.dashboard(context.organization_id))["posts"]}

    @router.post("/posts", status_code=201)
    async def create_post(payload: PostCreate, context: Annotated[RequestContext, Depends(authenticated_context)]):
        can_write(context)
        return await repository.create_post(context, payload)

    @router.get("/posts/{post_id}/package")
    async def publication_package(post_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        return await repository.publication_package(context.organization_id, post_id)

    @router.post("/posts/{post_id}/publish")
    async def publish(post_id: str, context: Annotated[RequestContext, Depends(authenticated_context)], if_match: Annotated[str | None, Header(alias="If-Match")] = None):
        if context.role not in {"owner", "admin"}:
            raise ApiError(403, "insufficient_role", "Somente administradores podem aprovar publicações.")
        if not if_match:
            raise ApiError(428, "precondition_required", "Envie If-Match com a versão atual.")
        try:
            version = int(if_match.strip('"'))
        except ValueError:
            raise ApiError(422, "invalid_version", "Versão inválida.") from None
        return await repository.simulate_publish(context, post_id, version)

    @router.post("/posts/{post_id}/confirm")
    async def confirm_publication(post_id: str, payload: PublicationConfirm, context: Annotated[RequestContext, Depends(authenticated_context)], if_match: Annotated[str | None, Header(alias="If-Match")] = None):
        can_write(context)
        if not if_match:
            raise ApiError(428, "precondition_required", "Envie If-Match com a versão atual.")
        try:
            version = int(if_match.strip('"'))
        except ValueError:
            raise ApiError(422, "invalid_version", "Versão inválida.") from None
        return await repository.confirm_publication(context, post_id, version, payload)

    @router.delete("/posts/{post_id}", status_code=204)
    async def delete_post(post_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        can_write(context)
        await repository.delete_post(context, post_id)

    return router
