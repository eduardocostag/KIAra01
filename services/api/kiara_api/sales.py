from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from .adapters.postgres import PostgresRepository, _iso, _uuid
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

DEFAULT_TEMPLATES = {
    "first_contact": "Olá! Tudo bem? Meu nome é {remetente} e encontrei {nome} durante uma pesquisa sobre {nicho} em {cidade}. Notei uma oportunidade para fortalecer sua presença digital. Posso compartilhar uma sugestão breve?",
    "no_website": "Olá! Sou {remetente}. Encontrei {nome} ao pesquisar {nicho} em {cidade} e não localizei um site informado na fonte consultada. Posso compartilhar uma ideia para melhorar sua presença digital?",
    "website_opportunity": "Olá! Sou {remetente}. Conheci {nome} pesquisando {nicho} em {cidade} e identifiquei algumas oportunidades de melhoria na experiência digital. Posso enviar uma análise breve?",
    "instagram_opportunity": "Olá! Sou {remetente}. Conheci o perfil de {nome} e preparei uma sugestão rápida para fortalecer sua presença no Instagram. Posso compartilhar?",
    "follow_up": "Olá! Passando para retomar minha mensagem anterior. A sugestão para {nome} continua disponível; posso resumir os principais pontos por aqui?",
    "reactivation": "Olá! Sou {remetente}. Retomando nosso contato sobre {nome}: ainda faz sentido conversar sobre oportunidades para sua presença digital?",
    "objection": "Entendo perfeitamente. Para respeitar seu tempo, posso enviar apenas um resumo objetivo da oportunidade, sem compromisso?",
    "interest": "Ótimo, obrigado pelo retorno! Para eu direcionar a sugestão, qual resultado seria mais importante para {nome} neste momento?",
}


class SalesProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_name: str = Field(max_length=160)
    sender_name: str = Field(max_length=160)
    offer: str = Field(max_length=4000)
    tone: str = Field(max_length=500)
    follow_up_hours: int = Field(ge=1, le=720)
    contact_start: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    contact_end: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    templates: dict[str, str]


class OutreachCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pipeline_entry_id: str = Field(min_length=1, max_length=128)
    channel: Literal["whatsapp", "instagram", "phone"]
    status: Literal["opened", "sent", "replied", "no_response"]
    body: str = Field(default="", max_length=20000)
    follow_up_hours: int | None = Field(default=None, ge=1, le=720)


class SalesRepository:
    def __init__(self, postgres: PostgresRepository) -> None:
        self._postgres = postgres

    async def get_profile(self, organization_id: str) -> dict[str, Any]:
        organization_uuid = _uuid("organization", organization_id)
        async with self._postgres._transaction(organization_id) as connection:
            row = await (await connection.execute(
                "SELECT business_name,sender_name,offer,tone,follow_up_hours,contact_start,contact_end,templates,updated_at FROM sales_profiles WHERE organization_id=%s",
                (organization_uuid,),
            )).fetchone()
        if row is None:
            return {"business_name": "", "sender_name": "", "offer": "", "tone": "consultivo, acolhedor e objetivo", "follow_up_hours": 48, "contact_start": "09:00", "contact_end": "18:00", "templates": DEFAULT_TEMPLATES, "updated_at": None}
        result = dict(row)
        result["contact_start"], result["contact_end"] = str(result["contact_start"])[:5], str(result["contact_end"])[:5]
        result["templates"] = {**DEFAULT_TEMPLATES, **(result.get("templates") or {})}
        result["updated_at"] = _iso(result["updated_at"])
        return result

    async def save_profile(self, organization_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        templates = profile["templates"]
        if len(templates) > 30 or any(not isinstance(key, str) or not isinstance(value, str) or len(key) > 80 or len(value) > 20000 for key, value in templates.items()):
            raise ApiError(422, "invalid_templates", "Revise os modelos de mensagem.")
        organization_uuid = _uuid("organization", organization_id)
        async with self._postgres._transaction(organization_id) as connection:
            await connection.execute(
                """INSERT INTO sales_profiles (organization_id,business_name,sender_name,offer,tone,follow_up_hours,contact_start,contact_end,templates)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (organization_id) DO UPDATE SET business_name=excluded.business_name,sender_name=excluded.sender_name,
                   offer=excluded.offer,tone=excluded.tone,follow_up_hours=excluded.follow_up_hours,contact_start=excluded.contact_start,
                   contact_end=excluded.contact_end,templates=excluded.templates,updated_at=now()""",
                (organization_uuid, profile["business_name"].strip(), profile["sender_name"].strip(), profile["offer"].strip(), profile["tone"].strip(), profile["follow_up_hours"], profile["contact_start"], profile["contact_end"], templates),
            )
        return await self.get_profile(organization_id)

    async def record(self, context: RequestContext, activity: OutreachCreate) -> dict[str, Any]:
        organization_uuid = _uuid("organization", context.organization_id)
        entry_uuid, user_uuid = _uuid("pipeline", activity.pipeline_entry_id), _uuid("user", context.user_id)
        follow_up_at = datetime.now(UTC) + timedelta(hours=activity.follow_up_hours) if activity.status == "sent" and activity.follow_up_hours else None
        async with self._postgres._transaction(context.organization_id) as connection:
            exists = await (await connection.execute("SELECT stage FROM pipeline_entries WHERE organization_id=%s AND id=%s FOR UPDATE", (organization_uuid, entry_uuid))).fetchone()
            if exists is None:
                raise ApiError(404, "pipeline_entry_not_found", "Lead não encontrado no Pipeline.")
            await connection.execute("INSERT INTO users (id,identity_provider,external_subject) VALUES (%s,'clerk',%s) ON CONFLICT (id) DO NOTHING", (user_uuid, context.user_id))
            row = await (await connection.execute(
                """INSERT INTO outreach_activities (organization_id,id,pipeline_entry_id,actor_user_id,channel,status,body,next_follow_up_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,pipeline_entry_id,channel,status,body,next_follow_up_at,created_at""",
                (organization_uuid, uuid4(), entry_uuid, user_uuid, activity.channel, activity.status, activity.body.strip(), follow_up_at),
            )).fetchone()
            if activity.status == "sent":
                next_action = f"Fazer follow-up por {activity.channel}" if follow_up_at else "Aguardar resposta"
                await connection.execute("UPDATE pipeline_entries SET stage='contacted',next_action=%s,next_action_at=%s,version=version+1,updated_at=now() WHERE organization_id=%s AND id=%s", (next_action, follow_up_at, organization_uuid, entry_uuid))
        return {key: (_iso(value) if hasattr(value, "isoformat") else str(value) if key in {"id", "pipeline_entry_id"} else value) for key, value in row.items()}


def create_sales_router(repository: SalesRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/sales", tags=["sales"])

    @router.get("/profile")
    async def get_profile(context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        return await repository.get_profile(context.organization_id)

    @router.put("/profile")
    async def save_profile(update: SalesProfileUpdate, context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Acesso restrito a operadores.")
        return await repository.save_profile(context.organization_id, update.model_dump())

    @router.post("/activities", status_code=201)
    async def record_activity(activity: OutreachCreate, context: Annotated[RequestContext, Depends(authenticated_context)]) -> dict[str, Any]:
        if context.role not in {"owner", "admin", "operator"}:
            raise ApiError(403, "insufficient_role", "Acesso restrito a operadores.")
        return await repository.record(context, activity)

    return router
