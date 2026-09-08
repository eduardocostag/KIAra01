from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IdentityPrincipal:
    user_id: str
    organization_id: str
    membership_id: str
    role: str


class IdentityVerifier(Protocol):
    async def verify(self, bearer_token: str) -> IdentityPrincipal:
        """Validate a provider token and return trusted, canonical identity claims."""
        ...
