from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
from typing import Annotated, Literal
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.request import Request as UrlRequest

import psycopg
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

SYSTEM_ADMIN_EMAIL = "admin@kiara.local"
Provider = Literal["google", "instagram", "instagram_session", "hermes", "mailerfind"]
ALLOWED_FIELDS = {
    "google": {"developer_token", "client_id", "client_secret", "refresh_token", "customer_id", "login_customer_id", "ga4_property_id"},
    "instagram": {"app_id", "app_secret", "access_token", "instagram_account_id", "page_id", "verify_token"},
    "instagram_session": {"session_id", "username"},
    "hermes": {"endpoint_url", "api_key", "instance_id"},
    "mailerfind": {"endpoint_url", "access_token", "refresh_token", "client_id", "client_secret", "expires_at", "scope", "token_type"},
}


class IntegrationInput(BaseModel):
    credentials: dict[str, str] = Field(min_length=1)

    @field_validator("credentials")
    @classmethod
    def clean_credentials(cls, value: dict[str, str]) -> dict[str, str]:
        clean = {key: item.strip() for key, item in value.items() if isinstance(item, str) and item.strip()}
        if not clean or any(len(item) > 4096 for item in clean.values()):
            raise ValueError("Credenciais inválidas.")
        return clean


class IntegrationRepository:
    def __init__(self, postgres: PostgresRepository, encryption_key: str) -> None:
        try:
            self._cipher = Fernet(encryption_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise RuntimeError("KIARA_INTEGRATION_ENCRYPTION_KEY must be a valid Fernet key") from exc
        self._postgres = postgres

    async def list(self, organization_id: str) -> list[dict[str, object]]:
        async with self._postgres._transaction(organization_id) as connection:
            rows = await (await connection.execute(
                """SELECT DISTINCT ON (provider) provider, configured_fields, status, last_error, updated_at, is_global
                   FROM integration_credentials
                   WHERE organization_id=%s OR (provider='mailerfind' AND is_global=true AND status!='disabled')
                   ORDER BY provider, (organization_id=%s) DESC, is_global DESC""",
                (_uuid("organization", organization_id), _uuid("organization", organization_id)),
            )).fetchall()
        return [{**row, "updated_at": row["updated_at"].isoformat()} for row in rows]

    async def save(self, organization_id: str, provider: Provider, credentials: dict[str, str], *, is_global: bool = False) -> dict[str, object]:
        unexpected = set(credentials) - ALLOWED_FIELDS[provider]
        if unexpected:
            raise ApiError(422, "unsupported_credential", "Um ou mais campos não são aceitos.", {"fields": sorted(unexpected)})
        _validate_credentials(provider, credentials)
        encrypted = self._cipher.encrypt(json.dumps(credentials, sort_keys=True).encode()).decode()
        fields = sorted(credentials)
        instance_id = credentials.get("instance_id") if provider == "hermes" else None
        endpoint_fingerprint = (hashlib.sha256(credentials["endpoint_url"].rstrip("/").lower().encode()).hexdigest()
                                if provider == "hermes" else None)
        try:
            async with self._postgres._transaction(organization_id) as connection:
                row = await (await connection.execute(
                """INSERT INTO integration_credentials (organization_id, provider, encrypted_credentials, configured_fields, hermes_instance_id, hermes_endpoint_fingerprint, is_global)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,provider) DO UPDATE SET
                   encrypted_credentials=excluded.encrypted_credentials, configured_fields=excluded.configured_fields,
                   hermes_instance_id=excluded.hermes_instance_id, hermes_endpoint_fingerprint=excluded.hermes_endpoint_fingerprint,
                   is_global=excluded.is_global, status='configured', last_error=NULL, updated_at=now()
                   RETURNING provider, configured_fields, status, last_error, updated_at, is_global""",
                (_uuid("organization", organization_id), provider, encrypted, fields, instance_id, endpoint_fingerprint, is_global),
                )).fetchone()
        except psycopg.errors.UniqueViolation:
            if provider == "mailerfind" and is_global:
                raise ApiError(409, "mailerfind_global_already_configured", "O MailerFind global já foi configurado por outro administrador.") from None
            raise ApiError(409, "hermes_instance_already_assigned", "Esta instância Hermes já pertence a outro workspace.") from None
        return {**row, "updated_at": row["updated_at"].isoformat()}

    def decrypt_for_provider(self, encrypted: str) -> dict[str, str]:
        try:
            return json.loads(self._cipher.decrypt(encrypted.encode()))
        except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Stored integration credential cannot be decrypted") from exc

    async def credentials_for(self, organization_id: str, provider: Provider) -> dict[str, str] | None:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """SELECT encrypted_credentials FROM integration_credentials
                   WHERE provider=%s AND status!='disabled' AND (organization_id=%s OR is_global=true)
                   ORDER BY (organization_id=%s) DESC, is_global DESC LIMIT 1""",
                (provider, _uuid("organization", organization_id), _uuid("organization", organization_id)),
            )).fetchone()
        return self.decrypt_for_provider(row["encrypted_credentials"]) if row else None


class _DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect_not_allowed")


def _hermes_capabilities(credentials: dict[str, str]) -> dict[str, object]:
    endpoint = credentials["endpoint_url"].rstrip("/")
    hostname = urlsplit(endpoint).hostname or ""
    for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("unsafe_destination")
    target = endpoint + "/v1/capabilities"
    request = UrlRequest(target, headers={"Authorization": "Bearer " + credentials["api_key"], "Accept": "application/json"})
    with build_opener(_DenyRedirects()).open(request, timeout=8) as response:
        payload = response.read(100_001)
        if len(payload) > 100_000:
            raise ValueError("response_too_large")
    data = json.loads(payload)
    if data.get("platform") != "hermes-agent" or not isinstance(data.get("features"), dict):
        raise ValueError("not_hermes")
    return {"platform": "hermes-agent", "instance_id": credentials["instance_id"],
            "features": {key: bool(data["features"].get(key)) for key in ("responses_api", "run_submission", "run_status", "run_stop")}}

def _validate_credentials(provider: Provider, credentials: dict[str, str]) -> None:
        required = ({"developer_token", "client_id", "client_secret", "refresh_token", "customer_id"} if provider == "google" else
                    {"app_id", "app_secret", "access_token", "instagram_account_id"} if provider == "instagram" else
                    {"session_id"} if provider == "instagram_session" else
                    {"endpoint_url", "api_key", "instance_id"} if provider == "hermes" else
                    {"endpoint_url", "access_token", "client_id"})
        missing = required - set(credentials)
        if missing:
            raise ApiError(422, "missing_credentials", "Preencha os campos obrigatórios.", {"fields": sorted(missing)})
        if provider == "google":
            for field in ("customer_id", "login_customer_id"):
                if field in credentials and not re.fullmatch(r"\d{10}", credentials[field].replace("-", "")):
                    raise ApiError(422, "invalid_customer_id", "O ID da conta Google Ads deve ter 10 dígitos.", {"field": field})
        elif provider == "instagram" and not credentials["app_id"].isdigit():
            raise ApiError(422, "invalid_app_id", "O App ID da Meta deve conter apenas números.")
        elif provider == "instagram_session":
            if not re.fullmatch(r"[A-Za-z0-9%:_-]{20,4096}", credentials["session_id"]):
                raise ApiError(422, "invalid_instagram_session", "A sessão do Instagram não possui um formato válido.")
        elif provider == "hermes":
            parsed = urlsplit(credentials["endpoint_url"])
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
                raise ApiError(422, "invalid_hermes_endpoint", "Informe uma URL HTTPS base para a instância Hermes.")
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
                    raise ApiError(422, "invalid_hermes_endpoint", "A instância precisa de uma URL HTTPS pública.") from None
            else:
                if not address.is_global:
                    raise ApiError(422, "invalid_hermes_endpoint", "A instância precisa de uma URL HTTPS pública.")
            if not re.fullmatch(r"[a-zA-Z0-9_-]{3,80}", credentials["instance_id"]):
                raise ApiError(422, "invalid_hermes_instance", "ID de instância Hermes inválido.")
        elif provider == "mailerfind":
            if credentials["endpoint_url"] != "https://mcp.mailerfind.com/mcp":
                raise ApiError(422, "invalid_mailerfind_endpoint", "O endpoint oficial do MailerFind não foi reconhecido.")
            if credentials.get("token_type", "Bearer").lower() != "bearer":
                raise ApiError(422, "invalid_mailerfind_token", "O MailerFind não retornou um token Bearer compatível.")


def create_integration_router(repository: IntegrationRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/integrations", tags=["integrations"])

    def ensure_admin(context: RequestContext) -> None:
        if context.role not in {"owner", "admin"}:
            raise ApiError(403, "insufficient_permission", "Somente administradores podem gerenciar integrações.")

    def ensure_system_admin(context: RequestContext) -> None:
        if context.email != SYSTEM_ADMIN_EMAIL:
            raise ApiError(403, "system_admin_required", "Somente o administrador geral pode configurar o MailerFind global.")

    @router.get("")
    async def list_integrations(context: Annotated[RequestContext, Depends(authenticated_context)]):
        return {"items": await repository.list(context.organization_id)}

    @router.put("/{provider}")
    async def save_integration(provider: Provider, payload: IntegrationInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        ensure_admin(context)
        if provider in {"mailerfind", "instagram_session"}:
            ensure_system_admin(context)
        return await repository.save(context.organization_id, provider, payload.credentials)

    @router.get("/instagram-session/status")
    async def instagram_session_status(context: Annotated[RequestContext, Depends(authenticated_context)]):
        ensure_system_admin(context)
        credentials = await repository.credentials_for(context.organization_id, "instagram_session")
        if not credentials:
            raise ApiError(404, "instagram_session_not_configured", "Conecte uma sessão do Instagram no painel administrativo.")
        from .instagram_private import InstagramSessionFailure, verify_instagram_session
        try:
            return await asyncio.to_thread(verify_instagram_session, credentials["session_id"])
        except InstagramSessionFailure as error:
            raise ApiError(error.status_code, error.code, error.message) from None

    @router.put("/mailerfind/global")
    async def save_global_mailerfind(payload: IntegrationInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        ensure_system_admin(context)
        return await repository.save(context.organization_id, "mailerfind", payload.credentials, is_global=True)

    @router.get("/hermes/capabilities")
    async def hermes_capabilities(context: Annotated[RequestContext, Depends(authenticated_context)]):
        ensure_admin(context)
        credentials = await repository.credentials_for(context.organization_id, "hermes")
        if not credentials:
            raise ApiError(404, "hermes_not_configured", "Conecte uma instância Hermes neste workspace.")
        try:
            return await asyncio.to_thread(_hermes_capabilities, credentials)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            raise ApiError(502, "hermes_unavailable", "A instância Hermes não respondeu ou não é compatível.") from None

    return router
