from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

from app.models import PermissionLevel, ToolResult
from app.perception import ScreenPerception
from app.tools.base import Tool
from app.web_studio import BusinessSiteGenerator, SitePreviewValidator


class LandingPageTemplatesTool(Tool):
    name = "landing_page_templates"
    description = "Lista os templates do Landing Page System ou cria uma prévia local isolada e demonstrativa, sem publicação."
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"action": {"type": "string", "enum": ["list", "preview"]},
                       "template": {"type": "string", "maxLength": 100}},
        "required": ["action"], "additionalProperties": False,
    }

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root

    def validate(self, parameters: dict[str, Any]) -> None:
        if parameters.keys() - {"action", "template"} or parameters.get("action") not in {"list", "preview"}:
            raise ValueError("Use action=list ou preview.")
        if parameters["action"] == "preview" and (
            not isinstance(parameters.get("template"), str) or not 1 <= len(parameters["template"]) <= 100
        ):
            raise ValueError("Informe um template do catálogo.")

    async def execute(self, action: str, template: str = "", **_: Any) -> ToolResult:
        from app.web_studio.landing_system import build_template_preview, template_catalog

        self.validate({"action": action, "template": template})
        if action == "list":
            items = template_catalog()
            return ToolResult(True, output=json.dumps(items, ensure_ascii=False), metadata={"templates": items})
        destination = await asyncio.to_thread(build_template_preview, template, self.output_root)
        return ToolResult(True, output=f"Prévia demonstrativa criada em {destination}. Personalize e valide antes de publicar.",
                          metadata={"project_path": str(destination), "published": False,
                                    "personalized": False, "quality_verified": False})


class GenerateBusinessSiteTool(Tool):
    name = "generate_business_site"
    description = "Gera um site estático isolado usando imagem local e dados do estabelecimento."
    # A imagem pode atravessar uma fronteira de modelo; sempre requer consentimento.
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "site_name": {"type": "string", "maxLength": 100},
            "business_info": {"type": "string", "maxLength": 8000},
            "reference_image": {"type": "string", "maxLength": 500},
        },
        "required": ["site_name", "business_info", "reference_image"],
    }

    def __init__(self, generator: BusinessSiteGenerator, validator: SitePreviewValidator) -> None:
        self.generator = generator
        self.validator = validator

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != set(self.schema["required"]):
            raise ValueError("Informe site_name, business_info e reference_image.")
        for key, limit in (("site_name", 100), ("business_info", 8000), ("reference_image", 500)):
            value = parameters[key]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Campo inválido: {key}.")

    async def execute(self, **parameters: Any) -> ToolResult:
        destination = await self.generator.generate(**parameters)
        report = await self.validator.validate(destination)
        if not report.passed:
            return ToolResult(
                False,
                error=(
                    f"O rascunho foi salvo em {destination}, mas não passou no preview "
                    "mobile/tablet/desktop."
                ),
                metadata={
                    "project_path": str(destination),
                    "published": False,
                    "preview": report.as_metadata(),
                },
            )
        return ToolResult(
            True,
            output=f"Site criado e validado em três resoluções em {destination}.",
            metadata={
                "project_path": str(destination),
                "files": 3,
                "published": False,
                "preview": report.as_metadata(),
            },
        )


class ValidateBusinessSiteTool(Tool):
    name = "validate_business_site"
    description = "Valida um site gerado em navegador isolado e três resoluções."
    permission_level = PermissionLevel.READ_ONLY
    schema: ClassVar[dict[str, Any]] = {
        "properties": {"project": {"type": "string", "maxLength": 200}},
        "required": ["project"],
    }

    def __init__(self, validator: SitePreviewValidator) -> None:
        self.validator = validator

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"project"}:
            raise ValueError("Informe somente o projeto.")
        project = parameters["project"]
        if not isinstance(project, str) or not project.strip() or len(project) > 200:
            raise ValueError("Projeto inválido.")

    async def execute(self, *, project: str, **_: Any) -> ToolResult:
        report = await self.validator.validate(project)
        return ToolResult(
            report.passed,
            output="Preview aprovado em mobile, tablet e desktop." if report.passed else "",
            error=None if report.passed else "O preview encontrou problemas.",
            metadata={"preview": report.as_metadata(), "published": False},
        )


class GenerateBusinessSiteFromScreenTool(Tool):
    name = "generate_business_site_from_screen"
    description = "Captura a janela atual de forma efêmera e gera um site isolado."
    permission_level = PermissionLevel.SENSITIVE_ACTION
    schema: ClassVar[dict[str, Any]] = {
        "properties": {
            "site_name": {"type": "string", "maxLength": 100},
            "business_info": {"type": "string", "maxLength": 8000},
        },
        "required": ["site_name", "business_info"],
    }

    def __init__(
        self,
        generator: BusinessSiteGenerator,
        validator: SitePreviewValidator,
        perception: ScreenPerception,
    ) -> None:
        self.generator = generator
        self.validator = validator
        self.perception = perception

    def validate(self, parameters: dict[str, Any]) -> None:
        if set(parameters) != {"site_name", "business_info"}:
            raise ValueError("Informe somente site_name e business_info.")
        for key, limit in (("site_name", 100), ("business_info", 8000)):
            value = parameters[key]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Campo inválido: {key}.")

    async def execute(self, *, site_name: str, business_info: str, **_: Any) -> ToolResult:
        capture = await self.perception.capture_active_window(include_text=False)
        if capture is None or not capture.png:
            return ToolResult(False, error="Não consegui capturar a janela ativa.")
        destination = await self.generator.generate_from_bytes(
            site_name=site_name,
            business_info=business_info,
            image=capture.png,
        )
        report = await self.validator.validate(destination)
        return ToolResult(
            report.passed,
            output=(
                f"Site criado e validado em três resoluções em {destination}."
                if report.passed
                else ""
            ),
            error=(
                None
                if report.passed
                else f"O rascunho em {destination} não passou no preview automático."
            ),
            metadata={
                "project_path": str(destination),
                "published": False,
                "source_pixels_persisted": False,
                "preview": report.as_metadata(),
            },
        )
