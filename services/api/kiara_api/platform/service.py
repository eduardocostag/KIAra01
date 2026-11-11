"""Read-only product composition; no integration clients or executors are started."""

from __future__ import annotations

from ..http.context import RequestContext
from ..http.errors import ApiError
from .access import PlatformAccessRepository
from .policy import PlatformPolicy, load_policy
from .registry import module_descriptors, module_exists, skill_modules
from .skills_catalog import SKILLS_CATALOG

PLATFORM_ADMIN_EMAILS = frozenset({"admin@kiara.local"})


class PlatformService:
    def __init__(self, access: PlatformAccessRepository):
        self.access = access

    async def context(self, context: RequestContext) -> dict:
        if not context.email or context.email.strip().casefold() not in PLATFORM_ADMIN_EMAILS:
            raise ApiError(
                403,
                "platform_admin_only",
                "A nova plataforma está disponível somente para o administrador autorizado.",
            )
        policy = load_policy()
        access = await self.access.resolve(context)
        organization_policy = policy.organizations.get(access.organization_id)
        modules = []
        for module in module_descriptors():
            # Leads remains compatible; these gates apply only to the new scaffold.
            if module.key != "leads" and organization_policy is not None:
                if module.key in organization_policy.disabled_modules:
                    continue
                roles = organization_policy.module_roles.get(module.key)
                if roles is not None and access.role not in roles:
                    continue
            modules.append(module.model_dump())
        return {
            "brand": "KIARA",
            "organization": {"id": access.organization_id, "name": access.organization_name},
            "membership": {"id": access.membership_id, "role": access.role},
            "platform_role": self.platform_role(context.user_id, policy, context.email),
            "modules": modules,
            "phase": "structure_only",
            "external_execution_enabled": False,
            "access_source": access.source,
        }

    @staticmethod
    def platform_role(user_id: str, policy: PlatformPolicy, email: str | None = None) -> str:
        if email and email.strip().casefold() in PLATFORM_ADMIN_EMAILS:
            return "platform_admin"
        if user_id in policy.platform_admin_user_ids:
            return "platform_admin"
        if policy.reseller_assignments.get(user_id):
            return "reseller"
        return "client"

    async def module(self, context: RequestContext, key: str) -> dict:
        if not module_exists(key):
            raise ApiError(404, "platform_module_not_found", "Módulo desconhecido.")
        resolved = await self.context(context)
        module = next((item for item in resolved["modules"] if item["key"] == key), None)
        if module is None:
            raise ApiError(
                403,
                "platform_module_disabled",
                "Este módulo não está disponível para sua participação nesta empresa.",
            )
        return {**resolved, "module": module, "execution_status": "inactive"}

    async def skills(self, context: RequestContext) -> dict:
        resolved = await self.context(context)
        enabled = {module["key"] for module in resolved["modules"]}
        items = []
        for entry in SKILLS_CATALOG:
            modules = [key for key in skill_modules(entry["name"]) if key in enabled]
            if modules:
                items.append(
                    {
                        **entry,
                        "modules": modules,
                        "trust": "untrusted_reference",
                        "executor_status": "inactive",
                    }
                )
        return {"items": items, "phase": "structure_only", "external_execution_enabled": False}

    async def portfolio(self, context: RequestContext) -> dict:
        resolved = await self.context(context)
        policy = load_policy()
        assigned = policy.reseller_assignments.get(context.user_id, [])
        if not assigned and resolved["platform_role"] != "platform_admin":
            raise ApiError(
                403,
                "platform_portfolio_forbidden",
                "Uma atribuição explícita de carteira é obrigatória.",
            )
        # Even platform admins receive only explicit assignments, never SELECT * over tenants.
        return {
            "items": [{"organization_id": value} for value in dict.fromkeys(assigned)],
            "platform_role": resolved["platform_role"],
            "scope": "assigned_metadata_only",
            "external_execution_enabled": False,
        }
