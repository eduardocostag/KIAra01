"""Static product descriptors, independent of external integrations and executors."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ModuleKey = Literal["leads", "whatsapp", "atendimento", "ti"]
MembershipRole = Literal["owner", "admin", "operator", "viewer"]
PlatformRole = Literal["client", "reseller", "platform_admin"]


class ModuleDescriptor(BaseModel):
    key: ModuleKey
    name: str
    description: str
    href: str
    status: Literal["operational", "preparation"]
    status_label: str
    enabled: Literal[True] = True
    areas: list[str]
    integration_status: Literal["existing", "pending"]


_MODULES = (
    {
        "key": "leads",
        "name": "KIARA Leads",
        "description": "Pesquisa e operação comercial existente.",
        "href": "/app",
        "status": "operational",
        "status_label": "Operação existente",
        "areas": ["Pesquisa", "Pipeline", "Qualificação"],
        "integration_status": "existing",
    },
    {
        "key": "whatsapp",
        "name": "KIARA WhatsApp",
        "description": "Estrutura para um futuro módulo de comunicação.",
        "href": "/app/platform/whatsapp",
        "status": "preparation",
        "status_label": "Em preparação",
        "areas": ["Conversas", "Organização", "Acompanhamento"],
        "integration_status": "pending",
    },
    {
        "key": "atendimento",
        "name": "KIARA Atendimento",
        "description": "Estrutura para um futuro módulo de atendimento.",
        "href": "/app/platform/atendimento",
        "status": "preparation",
        "status_label": "Em preparação",
        "areas": ["Caixa de entrada", "Equipe", "Histórico"],
        "integration_status": "pending",
    },
    {
        "key": "ti",
        "name": "KIARA TI",
        "description": "Estrutura para um futuro módulo de suporte técnico.",
        "href": "/app/platform/ti",
        "status": "preparation",
        "status_label": "Em preparação",
        "areas": ["Diagnóstico", "Solicitações", "Conhecimento"],
        "integration_status": "pending",
    },
)


def module_descriptors() -> list[ModuleDescriptor]:
    return [ModuleDescriptor.model_validate(item) for item in _MODULES]


def module_exists(key: str) -> bool:
    return any(item["key"] == key for item in _MODULES)


def skill_modules(name: str) -> list[ModuleKey]:
    if name == "google-maps-scraper" or name.startswith("ig-"):
        return ["leads"]
    if name == "kiara-chatwoot":
        return ["atendimento"]
    if name == "kiara-freellmapi":
        return ["leads", "whatsapp", "atendimento", "ti"]
    return []
