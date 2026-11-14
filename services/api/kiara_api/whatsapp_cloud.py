"""Official WhatsApp (Meta Cloud API) for each client, connected through Meta's Embedded Signup.

Kiara is the Tech Provider: the client clicks one button, creates or picks their WhatsApp Business account and
number inside Meta's own window, and pays Meta directly (payment method added in their WhatsApp Manager).
Kiara only receives a business token for that client's account, kept encrypted per organization.

Platform settings (Kiara's Meta app), all server-side:
  META_APP_ID, META_APP_SECRET, META_WA_CONFIG_ID (Embedded Signup configuration), META_GRAPH_VERSION,
  KIARA_API_PUBLIC_URL (HTTPS base for the per-client webhook, e.g. https://kiara-api-rouge.vercel.app)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from .channel_webhooks import credentials_for_webhook
from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
from .integrations import IntegrationRepository
from .server_gateway import _opener
from .unified_inbox import ingest_message

PROVIDER = "whatsapp_cloud"
GRAPH_HOST = "https://graph.facebook.com"
MAX_GRAPH_BODY = 1_000_000
WHATSAPP_MANAGER_URL = "https://business.facebook.com/wa/manage/home/"
_MEDIA_LABELS = {"image": "[imagem]", "video": "[vídeo]", "audio": "[áudio]", "voice": "[áudio]", "document": "[documento]",
                 "sticker": "[figurinha]", "location": "[localização]", "contacts": "[contato]"}


class GraphError(RuntimeError):
    """Sanitized Graph API failure: carries Meta's numeric code and a safe message, never tokens or bodies."""

    def __init__(self, status: int, code: int | None, message: str):
        super().__init__(message)
        self.status, self.code = status, code


def platform_settings() -> dict[str, str]:
    version = os.getenv("META_GRAPH_VERSION", "").strip() or "v23.0"
    return {"app_id": os.getenv("META_APP_ID", "").strip(), "app_secret": os.getenv("META_APP_SECRET", "").strip(),
            "config_id": os.getenv("META_WA_CONFIG_ID", "").strip(),
            "graph_version": version if re.fullmatch(r"v\d{2}\.\d", version) else "v23.0",
            "public_url": os.getenv("KIARA_API_PUBLIC_URL", "").strip().rstrip("/")}


def missing_settings(settings: dict[str, str]) -> list[str]:
    missing = [name for name, key in (("META_APP_ID", "app_id"), ("META_APP_SECRET", "app_secret"),
                                      ("META_WA_CONFIG_ID", "config_id"), ("KIARA_API_PUBLIC_URL", "public_url")) if not settings[key]]
    if settings["app_id"] and not settings["app_id"].isdigit():
        missing.append("META_APP_ID (numérico)")
    if settings["config_id"] and not settings["config_id"].isdigit():
        missing.append("META_WA_CONFIG_ID (numérico)")
    if settings["public_url"] and (urlsplit(settings["public_url"]).scheme != "https" or not urlsplit(settings["public_url"]).hostname):
        missing.append("KIARA_API_PUBLIC_URL (HTTPS)")
    return missing


def graph(method: str, path: str, *, version: str, token: str | None = None, params: dict | None = None,
          body: dict | None = None, timeout: float = 20) -> dict[str, Any]:
    """One Graph API call: HTTPS only to graph.facebook.com, no redirects, bounded body, sanitized errors."""
    url = f"{GRAPH_HOST}/{version}/{path.lstrip('/')}" + (("?" + urlencode(params)) if params else "")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _opener.open(request, timeout=timeout) as response:
            raw, status = response.read(MAX_GRAPH_BODY + 1), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(MAX_GRAPH_BODY + 1), error.code
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise GraphError(0, None, "A Meta não respondeu.") from None
    try:
        payload = json.loads(raw[:MAX_GRAPH_BODY] or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    if not 200 <= status < 300 or (isinstance(payload, dict) and "error" in payload):
        error = payload.get("error") if isinstance(payload, dict) and isinstance(payload.get("error"), dict) else {}
        code = error.get("code") if isinstance(error.get("code"), int) else None
        message = error.get("error_user_msg") or error.get("message") or "Erro na Meta."
        raise GraphError(status, code, str(message)[:300])
    if not isinstance(payload, dict):
        raise GraphError(status, None, "Resposta inesperada da Meta.")
    return payload


def public_state(credentials: dict[str, str] | None) -> dict[str, Any]:
    if not credentials:
        return {"connected": False}
    return {"connected": True, "display_phone_number": credentials.get("display_phone_number", ""),
            "verified_name": credentials.get("verified_name", ""), "quality_rating": credentials.get("quality_rating", ""),
            "registered": credentials.get("registered") == "true", "connected_at": credentials.get("connected_at", ""),
            "manager_url": WHATSAPP_MANAGER_URL}


class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=10, max_length=2000, pattern=r"^[A-Za-z0-9_\-.#]+$")
    waba_id: str = Field(pattern=r"^[0-9]{5,30}$")
    phone_number_id: str = Field(pattern=r"^[0-9]{5,30}$")


def _owner_or_admin(context: RequestContext) -> None:
    if context.role not in {"owner", "admin"}:
        raise ApiError(403, "insufficient_permission", "Somente owner ou admin conectam o WhatsApp oficial.")


class WhatsAppCloudService:
    def __init__(self, integrations: IntegrationRepository | None, graph_call=graph):
        self.integrations = integrations
        self.graph = graph_call

    def _repository(self) -> IntegrationRepository:
        if self.integrations is None:
            raise ApiError(503, "integrations_not_configured", "O cofre de credenciais não está configurado no servidor.")
        return self.integrations

    async def status(self, context: RequestContext) -> dict[str, Any]:
        settings = platform_settings()
        missing = missing_settings(settings)
        credentials = await self._repository().credentials_for(context.organization_id, PROVIDER) if self.integrations else None
        result = {**public_state(credentials), "platform_ready": not missing,
                  # Public values the browser needs to open Meta's window; the app secret never leaves the server.
                  "app_id": settings["app_id"] if not missing else "", "config_id": settings["config_id"] if not missing else "",
                  "graph_version": settings["graph_version"]}
        if missing and (context.email or "").strip().lower() == "admin@kiara.local":
            result["missing_settings"] = missing
        return result

    async def connect(self, context: RequestContext, body: ConnectRequest) -> dict[str, Any]:
        _owner_or_admin(context)
        settings = platform_settings()
        if missing_settings(settings):
            raise ApiError(503, "whatsapp_official_unavailable", "A conexão oficial ainda não está disponível. Fale com o suporte da Kiara.")
        repository = self._repository()
        version = settings["graph_version"]
        try:
            # 1. The code from Meta's window lives ~30 s: exchange it first for this client's business token.
            exchanged = await asyncio.to_thread(self.graph, "GET", "oauth/access_token", version=version, params={
                "client_id": settings["app_id"], "client_secret": settings["app_secret"], "code": body.code})
            token = exchanged.get("access_token")
            if not isinstance(token, str) or len(token) < 20:
                raise GraphError(200, None, "A Meta não devolveu o acesso.")
            # 2. Messages from this client's account go to their own Kiara webhook (organization in the URL).
            verify_token = secrets.token_urlsafe(24)
            callback = f"{settings['public_url']}/v1/channels/whatsapp-cloud/{context.organization_id}/webhook"
            credentials = {"access_token": token, "waba_id": body.waba_id, "phone_number_id": body.phone_number_id,
                           "verify_token": verify_token, "pin": f"{secrets.randbelow(900000) + 100000}",
                           "connected_at": datetime.now(UTC).isoformat(), "registered": "false"}
            # Saved before subscribing: Meta verifies the callback URL immediately, and the webhook reads this token.
            await repository.save(context.organization_id, PROVIDER, credentials)
            await asyncio.to_thread(self.graph, "POST", f"{body.waba_id}/subscribed_apps", version=version, token=token,
                                    body={"override_callback_uri": callback, "verify_token": verify_token})
            # 3. Register the number on the Cloud API with a two-step verification PIN that Kiara keeps.
            try:
                await asyncio.to_thread(self.graph, "POST", f"{body.phone_number_id}/register", version=version, token=token,
                                        body={"messaging_product": "whatsapp", "pin": credentials["pin"]})
                credentials["registered"] = "true"
            except GraphError:
                credentials["registered"] = "false"  # e.g. already registered elsewhere; shown to the client
            info = await asyncio.to_thread(self.graph, "GET", body.phone_number_id, version=version, token=token,
                                           params={"fields": "display_phone_number,verified_name,quality_rating"})
            credentials.update({key: str(info.get(key) or "")[:120] for key in ("display_phone_number", "verified_name", "quality_rating")})
            await repository.save(context.organization_id, PROVIDER, credentials)
        except GraphError as error:
            await self._forget(context.organization_id)
            raise ApiError(502, "whatsapp_official_failed", f"A Meta recusou a conexão: {error}") from None
        return public_state(credentials)

    async def _forget(self, organization_id: str) -> None:
        try:
            await self._repository().disconnect(organization_id, PROVIDER)
        except Exception:  # noqa: BLE001 - best effort cleanup of a half-made connection
            pass

    async def disconnect(self, context: RequestContext) -> dict[str, Any]:
        _owner_or_admin(context)
        repository = self._repository()
        credentials = await repository.credentials_for(context.organization_id, PROVIDER)
        if credentials:
            try:  # stop Meta from sending this account's events to Kiara; the client's account itself is untouched
                await asyncio.to_thread(self.graph, "DELETE", f"{credentials['waba_id']}/subscribed_apps",
                                        version=platform_settings()["graph_version"], token=credentials["access_token"])
            except GraphError:
                pass
        await repository.disconnect(context.organization_id, PROVIDER)
        return {"connected": False}


def send_text(credentials: dict[str, str], phone: str, text: str) -> str:
    """Reply through the client's official number (inside WhatsApp's 24 h service window). Returns Meta's id."""
    result = graph("POST", f"{credentials['phone_number_id']}/messages", version=platform_settings()["graph_version"],
                   token=credentials["access_token"], body={"messaging_product": "whatsapp", "recipient_type": "individual",
                                                            "to": phone, "type": "text", "text": {"body": text[:4096]}})
    messages = result.get("messages")
    identifier = messages[0].get("id") if isinstance(messages, list) and messages and isinstance(messages[0], dict) else None
    if not isinstance(identifier, str) or not identifier:
        raise RuntimeError("Recibo da Meta ausente.")
    return identifier


def cloud_messages(payload: dict[str, Any], phone_number_id: str) -> list[dict[str, Any]]:
    """Meta webhook payload -> inbox messages. Rejects events addressed to another number."""
    if payload.get("object") != "whatsapp_business_account" or not isinstance(payload.get("entry"), list):
        raise ValueError("Evento inválido.")
    messages = []
    for entry in payload["entry"][:50]:
        for change in (entry.get("changes") or [])[:50]:
            value = change.get("value") or {}
            if change.get("field") != "messages":
                continue
            if str((value.get("metadata") or {}).get("phone_number_id", "")) != phone_number_id:
                raise ValueError("Número divergente.")
            names = {str(c.get("wa_id")): str((c.get("profile") or {}).get("name") or "")[:160] for c in (value.get("contacts") or []) if isinstance(c, dict)}
            for message in (value.get("messages") or [])[:100]:
                sender, identifier, kind = str(message.get("from", "")), message.get("id"), str(message.get("type", ""))
                if not sender.isdigit() or not isinstance(identifier, str):
                    continue
                if kind == "text":
                    text = str((message.get("text") or {}).get("body") or "")
                else:
                    media = message.get(kind) if isinstance(message.get(kind), dict) else {}
                    text = str(media.get("caption") or "") or _MEDIA_LABELS.get(kind, "[mensagem]")
                messages.append({"channel": "whatsapp", "identity": sender, "external_id": identifier[:250],
                                 "text": text[:10000] or "[mensagem]", "direction": "inbound", "name": names.get(sender, ""),
                                 "occurred_at": datetime.fromtimestamp(int(message.get("timestamp", 0)) or datetime.now(UTC).timestamp(), UTC)})
    return messages


def create_whatsapp_cloud_router(service: WhatsAppCloudService) -> APIRouter:
    router = APIRouter(tags=["whatsapp-official"])

    @router.get("/v1/whatsapp-official/status")
    async def status(response: Response, context: Annotated[RequestContext, Depends(authenticated_context)]):
        response.headers["Cache-Control"] = "no-store, private"
        return await service.status(context)

    @router.post("/v1/whatsapp-official/connect")
    async def connect(body: ConnectRequest, response: Response, context: Annotated[RequestContext, Depends(authenticated_context)]):
        response.headers["Cache-Control"] = "no-store, private"
        return await service.connect(context, body)

    @router.delete("/v1/whatsapp-official")
    async def disconnect(response: Response, context: Annotated[RequestContext, Depends(authenticated_context)]):
        response.headers["Cache-Control"] = "no-store, private"
        return await service.disconnect(context)

    @router.get("/v1/channels/whatsapp-cloud/{organization_id}/webhook")
    async def challenge(organization_id: str, request: Request):
        credentials = await credentials_for_webhook(service._repository(), organization_id, PROVIDER)
        query = request.query_params
        if (query.get("hub.mode") != "subscribe" or not credentials.get("verify_token")
                or not hmac.compare_digest(query.get("hub.verify_token", ""), credentials["verify_token"])):
            raise ApiError(401, "webhook_invalid", "Verificação de canal inválida.")
        return PlainTextResponse(query.get("hub.challenge", ""))

    @router.post("/v1/channels/whatsapp-cloud/{organization_id}/webhook")
    async def webhook(organization_id: str, request: Request):
        repository = service._repository()
        credentials = await credentials_for_webhook(repository, organization_id, PROVIDER)
        raw = await request.body()
        if not raw or len(raw) > 262144:
            raise ApiError(413, "webhook_too_large", "Evento acima do limite.")
        secret = platform_settings()["app_secret"]
        expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not secret or not hmac.compare_digest(request.headers.get("x-hub-signature-256", ""), expected):
            raise ApiError(401, "webhook_invalid", "Evento não autenticado.")
        try:
            messages = cloud_messages(json.loads(raw), credentials["phone_number_id"])
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            raise ApiError(401, "webhook_invalid", "Evento inválido.") from None
        accepted = 0
        async with repository._postgres._transaction(organization_id) as connection:
            for message in messages:
                result = await ingest_message(connection, organization_id, **message)
                accepted += int(result["inserted"])
        return {"accepted": accepted}

    return router
