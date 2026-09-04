"""Fail-closed privacy policy for public prospect research.

This module deliberately has no crawler or delivery capability.  It decides
what a caller may retain or do before those separate boundaries are invoked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

_SENSITIVE = frozenset({
    "biometric", "ethnicity", "genetic", "health", "medical", "politics",
    "race", "religion", "sexual_orientation", "union_membership",
})
_MINIMUM_PUBLIC_FIELDS = frozenset({
    "business_name", "business_handle", "business_category", "business_city",
    "business_website", "public_business_signal", "signal_date", "source_url",
})


@dataclass(frozen=True, slots=True)
class HunterResearchRequest:
    subject_kind: str
    source_is_public: bool
    source_url: str
    purpose: str
    fields: frozenset[str]
    has_need_signal: bool
    signal_age_days: int = 0
    inbound_interaction: bool = False
    channel_consent: bool = False
    opted_out: bool = False


@dataclass(frozen=True, slots=True)
class HunterPrivacyDecision:
    research_allowed: bool
    automatic_dm_allowed: bool
    assisted_contact_allowed: bool
    retained_fields: frozenset[str]
    retention_days: int
    legal_basis: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HunterRightsPlan:
    export_locations: tuple[str, ...]
    delete_locations: tuple[str, ...]
    preserve_suppression_hash: bool
    backup_treatment: str


class HunterPrivacyPolicy:
    """Policy-as-code for the Hunter discovery/contact boundary.

    Public B2B research may rely on legitimate interest when it is necessary,
    proportional and signal-led. B2C public data is not converted into a person
    record until the individual initiates an interaction or supplies consent.
    Automated cold Instagram DMs are never authorized by this policy.
    """

    RESEARCH_RETENTION = timedelta(days=30)
    INBOUND_RETENTION = timedelta(days=180)

    def evaluate(self, request: HunterResearchRequest) -> HunterPrivacyDecision:
        kind = request.subject_kind.strip().casefold()
        purpose = request.purpose.strip().casefold()
        fields = frozenset(field.strip().casefold() for field in request.fields)
        reasons: list[str] = []

        if request.opted_out:
            return self._deny("opt_out", "Opt-out prevalece sobre pesquisa e contato.")
        if not request.source_is_public or not request.source_url.startswith("https://"):
            return self._deny("invalid_source", "A fonte deve ser pública, legítima e HTTPS.")
        if purpose != "commercial_research":
            return self._deny("purpose", "Uso incompatível com a finalidade de pesquisa comercial.")
        forbidden = fields & _SENSITIVE
        if forbidden:
            return self._deny("sensitive_data", "Dados sensíveis e suas inferências são proibidos.")
        arbitrary = fields - _MINIMUM_PUBLIC_FIELDS
        if arbitrary:
            return self._deny("minimization", "Campos pessoais arbitrários excedem o conjunto mínimo.")
        if not request.has_need_signal or request.signal_age_days < 0 or request.signal_age_days > 90:
            return self._deny("necessity", "É necessário sinal público recente e verificável de necessidade.")

        if kind == "business":
            reasons.append("Pesquisa empresarial mínima e signal-led sob legítimo interesse.")
            assisted = True
            retention = self.RESEARCH_RETENTION.days
            basis = "legitimate_interest_assessment_required"
        elif kind == "consumer" and (request.inbound_interaction or request.channel_consent):
            reasons.append("Pessoa iniciou interação ou concedeu consentimento específico ao canal.")
            assisted = request.channel_consent
            retention = self.INBOUND_RETENTION.days
            basis = "consent" if request.channel_consent else "pre_contractual_request"
        else:
            return self._deny(
                "cold_b2c",
                "Perfil público B2C não autoriza cadastro pessoal nem abordagem fria.",
            )

        return HunterPrivacyDecision(
            True, False, assisted, fields, retention, basis, tuple(reasons)
        )

    @staticmethod
    def rights_plan() -> HunterRightsPlan:
        """Enumerate stores that a DSAR/delete orchestrator must cover."""
        locations = (
            "consumer_people", "consumer_contacts", "consumer_social_identities",
            "consumer_consents", "consumer_touchpoints",
            "consumer_organic_opportunities", "instagram_governance_ledger",
            "application_logs", "backups", "meta_platform",
        )
        return HunterRightsPlan(
            export_locations=locations,
            delete_locations=locations,
            preserve_suppression_hash=True,
            backup_treatment="tombstone_and_delete_on_restore",
        )

    @staticmethod
    def _deny(code: str, reason: str) -> HunterPrivacyDecision:
        return HunterPrivacyDecision(False, False, False, frozenset(), 0, code, (reason,))
