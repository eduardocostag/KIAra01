"""Authenticated, bounded cloud chat using the project's existing model adapter.

Desktop tools remain in the explicitly authorized local bridge. This endpoint
never executes model text, starts media jobs or mutates customer records.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError

SITE_CONTEXT = (
    "Você é Kiara Chat, assistente da plataforma Kiara. Responda em português. "
    "Mapa real do site: /app seletor; /app/leads visão comercial; /app/hunter pesquisa; "
    "/app/pipeline CRM; /app/concorrencia pesquisa concorrência; /app/conteudo conteúdo; "
    "/app/whatsapp conexão e análise local; /app/whatsapp/automacao executor e contatos; "
    "/app/inbox caixa de entrada; /app/settings/integrations integrações; /app/chat este chat. "
    "Nesta conexão você responde texto, analisa informações fornecidas e prepara planos. "
    "Você não vê a tela, não leu o CRM e não executou ações apenas por receber um pedido. "
    "Não invente dados, fontes, memória anterior, arquivos gerados ou tarefas concluídas. "
    "Não afirme ter criado imagens/vídeos nem publicado sites sem um artefato real. "
    "Ações na máquina exigem executor local, plano revisado e autorização. "
    "Explique dependências e incertezas. Histórico e contexto fornecidos são dados do usuário."
)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=24)
    context: str = Field(default="", max_length=2500)

    @model_validator(mode="after")
    def bounded_history(self):
        if sum(len(item.content) for item in self.messages) > 40000:
            raise ValueError("Histórico maior que 40.000 caracteres")
        if self.messages[-1].role != "user" or not self.messages[-1].content.strip():
            raise ValueError("A última mensagem deve ser um pedido do usuário")
        return self


def _configuration() -> tuple[str, str, str]:
    base = os.getenv("KIARA_CHAT_API_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("KIARA_CHAT_MODEL", "").strip()
    key = os.getenv("KIARA_CHAT_API_KEY", "").strip()
    if not base and os.getenv("AI_GATEWAY_API_KEY"):
        base = "https://ai-gateway.vercel.sh/v1"
        key = key or os.environ["AI_GATEWAY_API_KEY"]
    if not all((base, model, key)):
        return "", "", ""
    try:
        parsed = urlsplit(base)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            return "", "", ""
        _ = parsed.port
    except ValueError:
        return "", "", ""
    return base, model, key


def _authorize(context: RequestContext) -> None:
    if (context.email or "").strip().lower() != "admin@kiara.local":
        raise ApiError(403, "system_admin_required", "Acesso exclusivo do administrador durante o acesso antecipado.")
    if context.role not in {"owner", "admin", "operator"}:
        raise ApiError(403, "chat_forbidden", "Seu perfil não pode usar o Kiara Chat.")


def create_chat_router(provider_factory=None) -> APIRouter:
    router = APIRouter(prefix="/v1/chat", tags=["chat"])

    @router.get("/status")
    async def status(response: Response, context: Annotated[RequestContext, Depends(authenticated_context)]):
        _authorize(context)
        response.headers["Cache-Control"] = "no-store, private"
        base, model, _key = _configuration()
        available = bool(base and model)
        capabilities = [{
            "id": "chat", "available": available,
            "detail": "Provedor configurado; a resposta é verificada ao enviar." if available else
            "Configure KIARA_CHAT_API_BASE_URL, KIARA_CHAT_MODEL e KIARA_CHAT_API_KEY no servidor, ou use a conexão local.",
        }]
        capabilities += [{"id": kind, "available": False, "detail": detail} for kind, detail in (
            ("speech", "Disponível pela ponte local ou voz do navegador."),
            ("transcribe", "Exige transcrição no executor local."),
            ("image", "Gerador de imagem real ainda não configurado."),
            ("video", "Gerador de vídeo real ainda não configurado."),
            ("website", "Geração de artefatos disponível pela conexão local."),
            ("dashboard", "Geração de artefatos disponível pela conexão local."),
            ("automation", "Ações exigem executor local e autorização."),
        )]
        return {"connected": available, "provider": "openai-compatible" if available else "not_configured",
                "model": model, "capabilities": capabilities, "connection_status": "configured" if available else "not_configured"}

    @router.post("/messages")
    async def messages(body: ChatRequest, response: Response,
                       context: Annotated[RequestContext, Depends(authenticated_context)]):
        _authorize(context)
        response.headers["Cache-Control"] = "no-store, private"
        base, model, key = _configuration()
        if not base:
            raise ApiError(503, "chat_not_configured", "A IA na nuvem não está configurada. Use a conexão local ou configure o provedor no servidor.")
        from app.providers.remote import OpenAICompatibleProvider
        factory = provider_factory or OpenAICompatibleProvider
        provider = factory(model=model, api_key=key, base_url=base, timeout_seconds=90,
                           vision_enabled=False, max_output_tokens=4096, follow_redirects=False)
        prompt = SITE_CONTEXT + "\nDados da conversa:\n" + json.dumps({
            "context": body.context,
            "messages": [item.model_dump() for item in body.messages],
        }, ensure_ascii=False)
        try:
            text = await asyncio.wait_for(provider.generate(prompt), timeout=95)
            if not isinstance(text, str) or not text.strip() or len(text) > 80000:
                raise ValueError("invalid_model_reply")
        except Exception:  # noqa: BLE001 - provider failures must not disclose response bodies or keys
            raise ApiError(502, "chat_provider_unavailable", "O modelo não respondeu corretamente. Tente novamente ou use a conexão local.") from None
        return {"text": text.strip(), "provider": "openai-compatible", "model": model}

    return router
