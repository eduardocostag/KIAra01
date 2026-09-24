from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, Any
from typing import Literal
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from .http.context import RequestContext
from .http.dependencies import authenticated_context
from .http.errors import ApiError
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


def create_competition_router(repository: IntegrationRepository) -> APIRouter:
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
        account, analyses = await asyncio.gather(
            call(context, "mailerfind_user_get_info", {}),
            call(context, "mailerfind_analyses_list", {"limit": 20}),
        )
        return {"account": account, "analyses": analyses}

    @router.post("/analyses", status_code=201)
    async def create_analysis(payload: CompetitionAnalysisInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        return await call(context, "mailerfind_analysis_create", _analysis_arguments(payload))

    @router.post("/analyses/{analysis_id}/start")
    async def start_analysis(analysis_id: str, payload: CompetitionStartInput, context: Annotated[RequestContext, Depends(authenticated_context)]):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        return await call(context, "mailerfind_analysis_start", {"analysisId": analysis_id})

    @router.get("/analyses/{analysis_id}")
    async def get_analysis(analysis_id: str, context: Annotated[RequestContext, Depends(authenticated_context)]):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", analysis_id):
            raise ApiError(422, "analysis_id_invalid", "A análise selecionada não possui um identificador válido.")
        return await call(context, "mailerfind_analysis_get", {"analysisId": analysis_id})

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
        arguments: dict[str, Any] = {"analysisId": analysis_id, "limit": limit}
        if contactable_only:
            arguments["hasEmail"] = True
        return await call(context, "mailerfind_prospects_list", arguments)

    return router
