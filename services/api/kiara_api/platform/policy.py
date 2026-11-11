"""Trusted server configuration, read only when a platform endpoint is requested."""

from __future__ import annotations

import os
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from ..http.errors import ApiError
from .registry import MembershipRole, ModuleKey

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
PortfolioIds = Annotated[list[Identifier], Field(max_length=1000)]


class OrganizationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    disabled_modules: list[ModuleKey] = Field(default_factory=list, max_length=4)
    module_roles: dict[ModuleKey, list[MembershipRole]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def leads_is_legacy_compatible(self):
        if "leads" in self.disabled_modules or "leads" in self.module_roles:
            raise ValueError("Leads access cannot be configured by the structure-only platform")
        return self


class PlatformPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    organizations: dict[Identifier, OrganizationPolicy] = Field(default_factory=dict)
    platform_admin_user_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    reseller_assignments: dict[Identifier, PortfolioIds] = Field(default_factory=dict)

    @field_validator("organizations", "reseller_assignments")
    @classmethod
    def bounded_mapping(cls, value):
        if len(value) > 1000:
            raise ValueError("platform policy is too large")
        return value


def load_policy() -> PlatformPolicy:
    raw = os.getenv("KIARA_PLATFORM_POLICY_JSON", "").strip()
    if not raw:
        return PlatformPolicy()
    try:
        if len(raw) > 65_536:
            raise ValueError("policy exceeds size limit")
        return PlatformPolicy.model_validate_json(raw)
    except (ValidationError, ValueError):
        raise ApiError(
            503,
            "platform_policy_unavailable",
            "A política da plataforma é inválida. Leads permanece habilitado nesta fase; revise módulos, papéis e atribuições no servidor.",
        ) from None
