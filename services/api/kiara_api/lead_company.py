"""Enrich a CRM lead with public company registry data (CNPJ) and return its fit score."""
from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from .adapters.postgres import PostgresRepository, _uuid
from .company_data import CompanyLookupError, clean_cnpj, fetch_company, find_cnpjs, lead_fit
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

WRITERS = {"owner", "admin", "operator"}


class CompanyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cnpj: str | None = Field(default=None, max_length=24)


def _lead_view(attributes: dict[str, Any]) -> dict[str, Any]:
    hunter = attributes.get("hunter") if isinstance(attributes.get("hunter"), dict) else {}
    view = {key: hunter.get(key) for key in ("phone", "email", "whatsapp_url", "website_status", "website_quality_score", "rating", "user_rating_count")}
    if isinstance(attributes.get("company"), dict):
        view["company"] = attributes["company"]
    return view


def cnpj_from_website(url: str) -> str | None:
    """First valid CNPJ printed on the lead's own website (usually in the footer)."""
    from .hunter import _fetch_public_page

    text, _links, _mode = _fetch_public_page(url)
    found = find_cnpjs(text)
    return found[0] if found else None


class LeadCompanyRepository:
    def __init__(self, postgres: PostgresRepository, *, lookup=fetch_company, discover=cnpj_from_website) -> None:
        self._postgres = postgres
        self._lookup = lookup
        self._discover = discover

    async def _attributes(self, organization_id: str, consumer_id: str) -> dict[str, Any]:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                "SELECT attributes FROM consumers WHERE organization_id=%s AND id=%s AND lifecycle_status='active'",
                (_uuid("organization", organization_id), _uuid("consumer", consumer_id)),
            )).fetchone()
        if not row:
            raise ApiError(404, "lead_not_found", "Lead não encontrado.")
        return dict(row["attributes"] or {})

    async def _save(self, organization_id: str, consumer_id: str, company: dict[str, Any] | None) -> dict[str, Any]:
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                "SELECT attributes FROM consumers WHERE organization_id=%s AND id=%s FOR UPDATE",
                (_uuid("organization", organization_id), _uuid("consumer", consumer_id)),
            )).fetchone()
            if not row:
                raise ApiError(404, "lead_not_found", "Lead não encontrado.")
            attributes = dict(row["attributes"] or {})
            if company is None:
                attributes.pop("company", None)
            else:
                attributes["company"] = company
            await connection.execute(
                "UPDATE consumers SET attributes=%s,version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s",
                (json.dumps(attributes), _uuid("organization", organization_id), _uuid("consumer", consumer_id)),
            )
        return attributes

    async def enrich(self, context: RequestContext, consumer_id: str, cnpj: str | None) -> dict[str, Any]:
        attributes = await self._attributes(context.organization_id, consumer_id)
        source = "manual"
        digits = clean_cnpj(cnpj) if cnpj else None
        if cnpj and not digits:
            raise ApiError(422, "cnpj_invalid", "CNPJ inválido. Confira os 14 dígitos.")
        if not digits:
            hunter = attributes.get("hunter") if isinstance(attributes.get("hunter"), dict) else {}
            website = hunter.get("website_url")
            if not isinstance(website, str) or not website:
                raise ApiError(422, "cnpj_required", "Este lead não tem site para procurar o CNPJ. Informe o CNPJ manualmente.")
            try:
                digits = await asyncio.wait_for(asyncio.to_thread(self._discover, website), timeout=25)
            except Exception:  # noqa: BLE001 - external site failures are reported without detail
                digits = None
            if not digits:
                raise ApiError(422, "cnpj_not_on_website", "Não encontramos o CNPJ no site da empresa. Informe o CNPJ manualmente.")
            source = "website"
        try:
            company = await asyncio.wait_for(asyncio.to_thread(self._lookup, digits), timeout=30)
        except CompanyLookupError as error:
            status = 422 if error.code in {"cnpj_invalid", "cnpj_not_found"} else 503
            raise ApiError(status, error.code, str(error)) from None
        except TimeoutError:
            raise ApiError(503, "cnpj_provider_unavailable", "A consulta pública de CNPJ não respondeu agora. Tente de novo em instantes.") from None
        company["cnpj_source"] = source
        saved = await self._save(context.organization_id, consumer_id, company)
        return {"company": company, "fit": lead_fit(_lead_view(saved))}

    async def remove(self, context: RequestContext, consumer_id: str) -> dict[str, Any]:
        saved = await self._save(context.organization_id, consumer_id, None)
        return {"company": None, "fit": lead_fit(_lead_view(saved))}


def create_lead_company_router(repository: LeadCompanyRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/leads", tags=["leads"])

    def can_write(context: RequestContext) -> None:
        if context.role not in WRITERS:
            raise ApiError(403, "insufficient_role", "Seu perfil não pode alterar leads.")

    @router.post("/{consumer_id}/company")
    async def enrich(consumer_id: str, payload: CompanyRequest,
                     context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        can_write(context)
        return await repository.enrich(context, consumer_id, payload.cnpj)

    @router.delete("/{consumer_id}/company")
    async def remove(consumer_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        can_write(context)
        return await repository.remove(context, consumer_id)

    return router
