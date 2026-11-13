from __future__ import annotations

import json
from typing import Any, ClassVar

from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool
from app.video_studio.engine import VideoError
from app.video_studio.jobs import VideoJobs

AGENT_OWNER = "agent:local"


class CreatePresentationVideoTool(Tool):
    name = "create_presentation_video"
    description = (
        "Produz um vídeo de apresentação (MP4 1920x1080) narrado pela própria Kiara, com telas reais do "
        "sistema e cards sincronizados com a fala. brief = para quem, o que mostrar e o tom; audience = "
        "até 3 nomes para a saudação. Devolve job_id; acompanhe com presentation_video_status. "
        "Guia completo: operational_skill name=kiara-video-studio."
    )
    # The script text is sent to the Edge voice service; always ask first.
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "brief": {"type": "string", "maxLength": 4000},
            "audience": {"type": "array", "items": {"type": "string", "maxLength": 30}, "maxItems": 3},
            "quality": {"type": "string", "enum": ["1080p", "720p"]},
        },
        "required": ["brief"],
        "additionalProperties": False,
    }

    def __init__(self, jobs: VideoJobs) -> None:
        self.jobs = jobs

    def validate(self, parameters: dict[str, Any]) -> None:
        if parameters.keys() - {"brief", "audience", "quality"}:
            raise ValueError("Parâmetro de vídeo desconhecido.")
        brief = parameters.get("brief")
        if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
            raise ValueError("Descreva o vídeo em brief (até 4000 caracteres).")
        audience = parameters.get("audience", [])
        if not isinstance(audience, list) or len(audience) > 3 or not all(isinstance(n, str) and 0 < len(n.strip()) <= 30 for n in audience):
            raise ValueError("audience aceita até 3 nomes de até 30 caracteres.")
        if parameters.get("quality", "1080p") not in {"1080p", "720p"}:
            raise ValueError("quality deve ser 1080p ou 720p.")

    async def execute(self, brief: str, audience: list[str] | None = None, quality: str = "1080p") -> ToolResult:
        try:
            job = self.jobs.start(AGENT_OWNER, brief.strip(), [n.strip() for n in audience or []], quality)
        except VideoError as error:
            return ToolResult(False, error=str(error))
        return ToolResult(True, output=f"Produção iniciada. job_id={job['id']}", metadata={"video": job})


class PresentationVideoStatusTool(Tool):
    name = "presentation_video_status"
    description = "Mostra o andamento de um vídeo de apresentação (job_id) e o caminho do MP4 quando pronto."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"job_id": {"type": "string", "maxLength": 32}},
        "required": ["job_id"],
        "additionalProperties": False,
    }

    def __init__(self, jobs: VideoJobs) -> None:
        self.jobs = jobs

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"job_id"} or not isinstance(parameters["job_id"], str):
            raise ValueError("Informe somente job_id.")

    async def execute(self, job_id: str) -> ToolResult:
        try:
            job = self.jobs.status(AGENT_OWNER, job_id)
            path = str(self.jobs.video(AGENT_OWNER, job_id)) if job["status"] == "done" else None
        except VideoError as error:
            return ToolResult(False, error=str(error))
        return ToolResult(job["status"] != "failed", output=json.dumps({**job, "path": path}, ensure_ascii=False),
                          error=job["error"], metadata={"video": job, "path": path})
