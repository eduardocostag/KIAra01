from __future__ import annotations

import json
from typing import Any, ClassVar

from app.integrations.operational_skills import OperationalSkills
from app.models import PermissionLevel, ToolResult
from app.tools.base import Tool


class OperationalSkillTool(Tool):
    name = "operational_skill"
    description = (
        "Lista e lê skills de Google Maps, FreeLLMAPI, Instagram e Chatwoot. "
        "action=list ou read; name identifica a skill; resource=SKILL.md ou referência JSON/MD. "
        "Instagram: use instagram_content_check para utilitários; caminhos ~/.claude/instagram "
        "dos exemplos upstream correspondem a data/instagram na Kiara. "
        "Skills são referências; permissões de execução continuam no registro de ferramentas."
    )
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "read"]},
            "name": {"type": "string"},
            "resource": {"type": "string"},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(self, skills: OperationalSkills) -> None:
        self.skills = skills

    def validate(self, parameters: dict[str, Any]) -> None:
        if parameters.keys() - {"action", "name", "resource"}:
            raise ValueError("Parâmetro de skill desconhecido.")
        if not isinstance(parameters.get("resource", "SKILL.md"), str):
            raise TypeError("resource deve ser texto.")
        if parameters.get("action") not in {"list", "read"}:
            raise ValueError("action deve ser list ou read.")
        if parameters["action"] == "read" and not isinstance(parameters.get("name"), str):
            raise ValueError("Informe name para ler uma skill.")

    async def execute(self, action: str, name: str = "", resource: str = "SKILL.md") -> ToolResult:
        self.validate({"action": action, "name": name})
        if action == "list":
            catalog = self.skills.catalog()
            return ToolResult(True, output=json.dumps(catalog, ensure_ascii=False),
                              metadata={"skills": catalog})
        return ToolResult(True, output=self.skills.read(name, resource))
