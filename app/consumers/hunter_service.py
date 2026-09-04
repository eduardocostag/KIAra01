"""Policy-enforced entry point for Kiara Hunter decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.privacy import HunterPrivacyDecision, HunterPrivacyPolicy, HunterResearchRequest

from .hunter_engine import HunterDecision, HunterEngine, ProspectEvidence


@dataclass(frozen=True, slots=True)
class GovernedHunterDecision:
    privacy: HunterPrivacyDecision
    commercial: HunterDecision | None
    allowed_action: str


class GovernedHunterService:
    """Ensure privacy policy runs before scoring or channel selection."""

    def __init__(
        self,
        *,
        policy: HunterPrivacyPolicy | None = None,
        engine: HunterEngine | None = None,
    ) -> None:
        self._policy = policy or HunterPrivacyPolicy()
        self._engine = engine or HunterEngine()

    def evaluate(
        self,
        request: HunterResearchRequest,
        evidence: ProspectEvidence,
        *,
        now: datetime | None = None,
    ) -> GovernedHunterDecision:
        privacy = self._policy.evaluate(request)
        if not privacy.research_allowed:
            return GovernedHunterDecision(privacy, None, "bloqueado_pela_privacidade")
        commercial = self._engine.evaluate(evidence, now=now)
        if commercial.route.execution_mode == "bloqueado":
            return GovernedHunterDecision(privacy, commercial, "suprimir_contato")
        if not privacy.assisted_contact_allowed:
            return GovernedHunterDecision(privacy, commercial, "somente_pesquisa_sem_contato")
        return GovernedHunterDecision(privacy, commercial, commercial.next_action)
