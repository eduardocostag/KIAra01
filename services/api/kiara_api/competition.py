from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, Any
from typing import Literal
from uuid import uuid4
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
from .competition_store import CompetitionRepository
from .integrations import IntegrationRepository, SYSTEM_ADMIN_EMAIL


def _decode_mcp_body(raw: str) -> dict[str, Any]:
    if raw.startswith("event:") or "\ndata:" in raw:
        lines = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        raw = lines[-1] if lines else ""
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("invalid_mcp_response")
    return parsed


def _mcp_request(endpoint: str, token: str, payload: dict[str, Any], session_id: str | None = None) -> tuple[dict[str, Any], str | None]:
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = Request(endpoint, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=20) as response:
        raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("mcp_response_too_large")
        returned_session = response.headers.get("Mcp-Session-Id") or session_id
    return _decode_mcp_body(raw.decode("utf-8")), returned_session


def _mailerfind_tools(credentials: dict[str, str]) -> list[dict[str, Any]]:
    endpoint = credentials["endpoint_url"]
    if endpoint != "https://mcp.mailerfind.com/mcp":
        raise ValueError("invalid_mailerfind_endpoint")
    token = credentials["access_token"]
    _, session_id = _mcp_request(endpoint, token, {
        "jsonrpc": "2.0", "id": "kiara-initialize", "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "Kiara", "version": "1.0"},
        },
    })
    _mcp_request(endpoint, token, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, session_id)
    response, _ = _mcp_request(endpoint, token, {"jsonrpc": "2.0", "id": "kiara-tools", "method": "tools/list", "params": {}}, session_id)
    tools = response.get("result", {}).get("tools", [])
    if not isinstance(tools, list):
        raise ValueError("invalid_tools_list")
    return [item for item in tools if isinstance(item, dict)]


def _extract_tool_data(response: dict[str, Any]) -> Any:
    result = response.get("result")
    if not isinstance(result, dict):
        raise ValueError("invalid_tool_result")
    if result.get("isError"):
        content = result.get("content", [])
        message = next((item.get("text") for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)), None)
        raise RuntimeError(message or "mailerfind_tool_failed")
    if "structuredContent" in result:
        return result["structuredContent"]
    content = result.get("content", [])
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            try:
                return json.loads(item["text"])
            except json.JSONDecodeError:
                return {"message": item["text"]}
    return result


def _mailerfind_call(credentials: dict[str, str], tool_name: str, arguments: dict[str, Any]) -> Any:
    endpoint = credentials["endpoint_url"]
    if endpoint != "https://mcp.mailerfind.com/mcp":
        raise ValueError("invalid_mailerfind_endpoint")
    token = credentials["access_token"]
    _, session_id = _mcp_request(endpoint, token, {
        "jsonrpc": "2.0", "id": "kiara-initialize", "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "Kiara", "version": "1.0"},
        },
    })
    _mcp_request(endpoint, token, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, session_id)
    response, _ = _mcp_request(endpoint, token, {
        "jsonrpc": "2.0", "id": "kiara-tool-call", "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }, session_id)
    return _extract_tool_data(response)


CompetitionMode = Literal["followers", "account_audience", "account_commenters", "commenters"]


class CompetitionAnalysisInput(BaseModel):
    mode: CompetitionMode
    target: str = Field(min_length=1, max_length=500)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("target", "name")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class CompetitionStartInput(BaseModel):
    confirm: Literal[True]


class CompetitionImportInput(BaseModel):
    mode: CompetitionMode
    target: str = Field(min_length=1, max_length=500)
    profiles: list[str] = Field(min_length=1, max_length=500)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("target", "name")
    @classmethod
    def trim_import_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("profiles")
    @classmethod
    def validate_profiles(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if isinstance(value, str) and value.strip()]
        if not cleaned:
            raise ValueError("Informe ao menos um perfil público.")
        if any(len(value) > 500 for value in cleaned):
            raise ValueError("Cada perfil deve ter no máximo 500 caracteres.")
        return cleaned


_INSTAGRAM_RESERVED_PATHS = {
    "about", "accounts", "api", "challenge", "developer", "directory", "direct",
    "emails", "explore", "legal", "p", "privacy", "reel", "reels", "stories", "web",
}


def _imported_profile(value: str) -> dict[str, Any] | None:
    raw = value.strip()
    label = ""
    if "|" in raw:
        raw, label = (part.strip() for part in raw.split("|", 1))
    if raw.startswith(("http://", "https://")):
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme != "https" or host != "instagram.com":
            return None
        handle = parsed.path.strip("/").split("/", 1)[0]
    else:
        handle = raw.removeprefix("@").split()[0] if raw else ""
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", handle) or handle.lower() in _INSTAGRAM_RESERVED_PATHS:
        return None
    username = handle.lower()
    return {
        "id": f"instagram:{username}",
        "username": username,
        "full_name": label[:200] or None,
        "profile_url": f"https://www.instagram.com/{username}/",
        "source": "kiara_public",
    }


def _normalize_imported_profiles(values: list[str]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for value in values:
        profile = _imported_profile(value)
        if profile:
            unique.setdefault(str(profile["username"]), profile)
    return list(unique.values())


def _analysis_arguments(payload: CompetitionAnalysisInput) -> dict[str, Any]:
    arguments: dict[str, Any] = {"sourceType": "instagram", "mode": payload.mode}
    if payload.mode == "commenters":
        parsed = urlsplit(payload.target)
        if parsed.scheme != "https" or parsed.hostname not in {"instagram.com", "www.instagram.com"} or not re.match(r"^/(p|reel)/[^/]+/?", parsed.path):
            raise ApiError(422, "instagram_post_url_invalid", "Cole o link HTTPS de uma publicação ou Reel público do Instagram.")
        arguments["postUrl"] = payload.target
    else:
        username = payload.target.removeprefix("@").strip()
        if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
            raise ApiError(422, "instagram_username_invalid", "Informe somente o @usuário público do concorrente.")
        arguments["username"] = username
    if payload.name:
        arguments["name"] = payload.name
    return arguments


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: dict[str, Any], *keys: str) -> str:
    for key in keys:
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return ""


def _number(value: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        item = value.get(key)
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            return max(0, int(item))
    return None


def _analysis_record(value: Any) -> dict[str, Any]:
    current = _object(value)
    if not current:
        return {}
    if _text(current, "id", "analysisId", "analysis_id", "status", "state"):
        return current
    for key in ("analysis", "data", "result"):
        nested = _analysis_record(current.get(key))
        if nested:
            return nested
    return current


def _analysis_id(value: Any) -> str:
    return _text(_analysis_record(value), "id", "analysisId", "analysis_id")


def _items(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    current = _object(value)
    if not current:
        return []
    for key in keys:
        if isinstance(current.get(key), list):
            return _items(current[key], *keys)
    for key in ("data", "result"):
        nested = _items(current.get(key), *keys)
        if nested:
            return nested
    return []


async def _archive_analysis(
    archive: CompetitionRepository,
    organization_id: str,
    value: Any,
    *,
    mode: str | None = None,
    target: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    record = _analysis_record(value)
    identifier = _analysis_id(record)
    if not identifier:
        return None
    return await archive.upsert_analysis(
        organization_id,
        identifier,
        record,
        mode=mode or _text(record, "mode"),
        target=target or _text(record, "target", "username", "postUrl"),
        name=name or _text(record, "name"),
        status=_text(record, "status", "state") or "created",
        prospect_count=_number(record, "prospectCount", "prospectsCount", "prospect_count", "totalProspects"),
    )


def create_competition_router(repository: IntegrationRepository, archive: CompetitionRepository) -> APIRouter:
    router = APIRouter(prefix="/v1/competition", tags=["competition"])

    def ensure_system_admin(context: RequestContext) -> None:
        if context.email != SYSTEM_ADMIN_EMAIL:
            raise ApiError(403, "competition_preview_admin_only", "A prévia de Concorrência está disponível somente para o administrador geral.")

    async def credentials_for_admin(context: RequestContext) -> dict[str, str]:
        ensure_system_admin(context)
        credentials = await repository.credentials_for(context.organization_id, "mailerfind")
        if not credentials:
            raise ApiError(409, "mailerfind_not_connected", "Conecte o MailerFind global no painel administrativo antes de usar Concorrência.")
        return credentials

    async def call(context: RequestContext, tool_name: str, arguments: dict[str, Any]) -> Any:
        credentials = await credentials_for_admin(context)
        try:
            return await asyncio.to_thread(_mailerfind_call, credentials, tool_name, arguments)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise ApiError(409, "mailerfind_reauthorization_required", "O MailerFind recusou a autorização. Reconecte-o em Administração > APIs e conexões.") from None
            raise ApiError(502, "mailerfind_unavailable", f"O MailerFind respondeu com HTTP {error.code}. Tente novamente em alguns minutos.") from None
        except (URLError, TimeoutError):
            raise ApiError(502, "mailerfind_unavailable", "O MailerFind não respondeu. Tente novamente em alguns minutos.") from None
        except RuntimeError as error:
            message = str(error)
            raise ApiError(422, "mailerfind_operation_rejected", message[:500] if message else "O MailerFind recusou a operação. Revise os dados e os créditos da conta.") from None
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            raise ApiError(502, "mailerfind_invalid_response", "O MailerFind respondeu em formato incompatível. Contate o administrador.") from None

    @router.get("/tools")
    async def list_tools(context: Annotated[RequestContext, Depends(authenticated_context)]):
        credentials = await credentials_for_admin(context)
        try:
            tools = await asyncio.to_thread(_mailerfind_tools, credentials)
        except HTTPError as error:
            if error.code in {401, 403}:
                raise ApiError(409, "mailerfind_reauthorization_required", "O MailerFind recusou a autorização. Reconecte-o em Administração > APIs e conexões.") from None
            raise ApiError(502, "mailerfind_unavailable", f"O MailerFind respondeu com HTTP {error.code}. Tente novamente em alguns minutos.") from None
        except (URLError, TimeoutError):
            raise ApiError(502, "mailerfind_unavailable", "O MailerFind não respondeu. Tente novamente em alguns minutos.") from None
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            raise ApiError(502, "mailerfind_invalid_response", "O MailerFind respondeu em formato incompatível. Contate o administrador.") from None
        return {"items": [
            {
                "name": item.get("name"),
                "description": item.get("description"),
                "input_schema": item.get("inputSchema", {}),
            }
            for item in tools if isinstance(item.get("name"), str)
        ]}

    @router.get("/overview")
    async def overview(context: Annotated[RequestContext, Depends(authenticated_context)]):
        ensure_system_admin(context)
        try:
            account, analyses = await asyncio.gather(
                call(context, "mailerfind_user_get_info", {}),
                call(context, "mailerfind_analyses_list", {"limit": 20}),
            )
            for item in _items(analyses, "analyses", "items"):
                await _archive_analysis(archive, context.organization_id, item)
            local = await archive.list_analyses(context.organization_id)
            return {"account": account, "analyses": {"items": local}, "provider": {"available": True}}
        except ApiError as error:
            local = await archive.list_analyses(context.organization_id)
            return {
                "account": {}, "analyses": {"items": local},
                "provider": {"available": False, "code": error.code, "message": error.message},
            }

    @router.post("/analyses", status_code=201)
    async def create_analysis(payload: CompetitionAnalysisInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        result = await call(context, "mailerfind_analysis_create", _analysis_arguments(payload))
        await _archive_analysis(archive, context.organization_id, result, mode=payload.mode, target=payload.target, name=payload.name)
        return result

    @router.post("/imports", status_code=201)
    async def import_public_profiles(
        payload: CompetitionImportInput,
        context: Annotated[RequestContext, Depends(authenticated_context)],
    ):
        ensure_system_admin(context)
        prospects = _normalize_imported_profiles(payload.profiles)
        if not prospects:
            raise ApiError(
                422,
                "instagram_profiles_invalid",
                "Nenhum perfil público válido foi encontrado. Cole usuários como @perfil ou links HTTPS do Instagram.",
            )
        analysis_id = f"kiara_{uuid4().hex}"
        name = payload.name or f"Kiara · {payload.mode} · {payload.target}"
        analysis = await archive.upsert_analysis(
            context.organization_id,
            analysis_id,
            {"source": "kiara_public", "imported": len(prospects)},
            mode=payload.mode,
            target=payload.target,
            name=name,
            status="completed",
            prospect_count=len(prospects),
            provider="kiara_public",
        )
        saved = await archive.upsert_prospects(context.organization_id, analysis_id, prospects)
        return {"analysis": analysis, "saved": saved, "items": prospects}

    @router.post("/analyses/{analysis_id}/start")
    async def start_analysis(analysis_id: str, payload: CompetitionStartInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        result = await call(context, "mailerfind_analysis_start", {"analysisId": analysis_id})
        await _archive_analysis(archive, context.organization_id, result)
        return result

    @router.get("/analyses/{analysis_id}")
    async def get_analysis(analysis_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        ensure_system_admin(context)
        try:
            result = await call(context, "mailerfind_analysis_get", {"analysisId": analysis_id})
            await _archive_analysis(archive, context.organization_id, result)
            return result
        except ApiError:
            local = await archive.get_analysis(context.organization_id, analysis_id)
            if local:
                return local
            raise

    @router.get("/prospects")
    async def list_prospects(
        context: Annotated[RequestContext, Depends(authenticated_context)],
        analysis_id: str,
        contactable_only: bool = False,
        limit: int = 50,
    ):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        if not 1 <= limit <= 100:
            raise ApiError(422, "prospect_limit_invalid", "O limite deve ficar entre 1 e 100.")
        ensure_system_admin(context)
        local = await archive.list_prospects(context.organization_id, analysis_id, limit)
        if local:
            return {"items": local, "archived": True}
        arguments: dict[str, Any] = {"analysisId": analysis_id, "limit": limit}
        if contactable_only:
            arguments["hasEmail"] = True
        result = await call(context, "mailerfind_prospects_list", arguments)
        if not await archive.get_analysis(context.organization_id, analysis_id):
            await archive.upsert_analysis(context.organization_id, analysis_id, {}, status="completed")
        await archive.upsert_prospects(context.organization_id, analysis_id, _items(result, "prospects", "items"))
        local = await archive.list_prospects(context.organization_id, analysis_id, limit)
        return {"items": local, "archived": True}

    return router
