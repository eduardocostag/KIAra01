from __future__ import annotations

from dataclasses import dataclass

from ..ports.identity import IdentityPrincipal


@dataclass(frozen=True, slots=True)
class RequestContext:
    user_id: str
    organization_id: str
    membership_id: str
    role: str
    correlation_id: str

    @classmethod
    def from_principal(cls, principal: IdentityPrincipal, correlation_id: str) -> RequestContext:
        return cls(
            user_id=principal.user_id,
            organization_id=principal.organization_id,
            membership_id=principal.membership_id,
            role=principal.role,
            correlation_id=correlation_id,
        )
