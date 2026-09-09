from __future__ import annotations

import json
import re
from typing import Annotated, Literal

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator

from .adapters.postgres import PostgresRepository, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

Provider = Literal["google", "instagram"]
ALLOWED_FIELDS = {
    "google": {"developer_token", "client_id", "client_secret", "refresh_token", "customer_id", "login_customer_id", "ga4_property_id"},
    "instagram": {"app_id", "app_secret", "access_token", "instagram_account_id", "page_id", "verify_token"},
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
        self._validate(provider, credentials)
        encrypted = self._cipher.encrypt(json.dumps(credentials, sort_keys=True).encode()).decode()
        fields = sorted(credentials)
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                """INSERT INTO integration_credentials (organization_id, provider, encrypted_credentials, configured_fields)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (organization_id,provider) DO UPDATE SET
                   encrypted_credentials=excluded.encrypted_credentials, configured_fields=excluded.configured_fields,
                   status='configured', last_error=NULL, updated_at=now()
                   RETURNING provider, configured_fields, status, last_error, updated_at""",
                (_uuid("organization", organization_id), provider, encrypted, fields),
            )).fetchone()
        return {**row, "updated_at": row["updated_at"].isoformat()}

    def decrypt_for_provider(self, encrypted: str) -> dict[str, str]:
        try:
            return json.loads(self._cipher.decrypt(encrypted.encode()))
        except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Stored integration credential cannot be decrypted") from exc

    @staticmethod
    def _validate(provider: Provider, credentials: dict[str, str]) -> None:
        required = {"developer_token", "client_id", "client_secret", "refresh_token", "customer_id"} if provider == "google" else {"app_id", "app_secret", "access_token", "instagram_account_id"}
        missing = required - set(credentials)
        if missing:
            raise ApiError(422, "missing_credentials", "Preencha os campos obrigatórios.", {"fields": sorted(missing)})
        if provider == "google":
            for field in ("customer_id", "login_customer_id"):
                if field in credentials and not re.fullmatch(r"\d{10}", credentials[field].replace("-", "")):
                    raise ApiError(422, "invalid_customer_id", "O ID da conta Google Ads deve ter 10 dígitos.", {"field": field})
        elif not credentials["app_id"].isdigit():
            raise ApiError(422, "invalid_app_id", "O App ID da Meta deve conter apenas números.")


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

    return router
