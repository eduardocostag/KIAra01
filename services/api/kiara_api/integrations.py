from __future__ import annotations

import json
import ipaddress
import hashlib
import re
import asyncio
import socket
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as UrlRequest, build_opener
from typing import Annotated, Literal

from cryptography.fernet import Fernet, InvalidToken
import psycopg
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

Provider = Literal["google", "instagram", "hermes"]
ALLOWED_FIELDS = {
    "google": {"developer_token", "client_id", "client_secret", "refresh_token", "customer_id", "login_customer_id", "ga4_property_id"},
    "instagram": {"app_id", "app_secret", "access_token", "instagram_account_id", "page_id", "verify_token"},
    "hermes": {"endpoint_url", "api_key", "instance_id"},
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
                "SELECT provider, configured_fields, status, last_error, updated_at FROM integration_credentials WHERE organization_id=%s ORDER BY provider",
                (_uuid("organization", organization_id),),
            )).fetchall()
        return [{**row, "updated_at": row["updated_at"].isoformat()} for row in rows]

    async def save(self, organization_id: str, provider: Provider, credentials: dict[str, str]) -> dict[str, object]:
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
                """INSERT INTO integration_credentials (organization_id, provider, encrypted_credentials, configured_fields, hermes_instance_id, hermes_endpoint_fingerprint)
                   VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (organization_id,provider) DO UPDATE SET
                   encrypted_credentials=excluded.encrypted_credentials, configured_fields=excluded.configured_fields,
                   hermes_instance_id=excluded.hermes_instance_id, hermes_endpoint_fingerprint=excluded.hermes_endpoint_fingerprint,
                   status='configured', last_error=NULL, updated_at=now()
                   RETURNING provider, configured_fields, status, last_error, updated_at""",
                (_uuid("organization", organization_id), provider, encrypted, fields, instance_id, endpoint_fingerprint),
                )).fetchone()
        except psycopg.errors.UniqueViolation:
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
                "SELECT encrypted_credentials FROM integration_credentials WHERE organization_id=%s AND provider=%s AND status!='disabled'",
                (_uuid("organization", organization_id), provider),
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
                    {"endpoint_url", "api_key", "instance_id"})
        missing = required - set(credentials)
        if missing:
            raise ApiError(422, "missing_credentials", "Preencha os campos obrigatórios.", {"fields": sorted(missing)})
        if provider == "google":
            for field in ("customer_id", "login_customer_id"):
                if field in credentials and not re.fullmatch(r"\d{10}", credentials[field].replace("-", "")):
                    raise ApiError(422, "invalid_customer_id", "O ID da conta Google Ads deve ter 10 dígitos.", {"field": field})
        elif provider == "instagram" and not credentials["app_id"].isdigit():
            raise ApiError(422, "invalid_app_id", "O App ID da Meta deve conter apenas números.")
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


def create_integration_router(repository: IntegrationRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/integrations", tags=["integrations"])

    def ensure_admin(context: RequestContext) -> None:
        if context.role not in {"owner", "admin"}:
            raise ApiError(403, "insufficient_permission", "Somente administradores podem gerenciar integrações.")

    @router.get("")
    async def list_integrations(context: Annotated[RequestContext, Depends(authenticated_context)]):
        return {"items": await repository.list(context.organization_id)}

    @router.put("/{provider}")
    async def save_integration(provider: Provider, payload: IntegrationInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        ensure_admin(context)
        return await repository.save(context.organization_id, provider, payload.credentials)

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
