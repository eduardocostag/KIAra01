"""Consumer (B2C) qualification domain."""

from app.consumers.hunter import HunterDecision, HunterIntent, HunterPromptContract, HunterRequest
from app.consumers.hunter_service import GovernedHunterDecision, GovernedHunterService
from app.consumers.ingestion import (
    ConsumerIngestionError,
    ConsumerLeadPayload,
    GenericFormAdapter,
    LinkedInLeadAdapter,
    MetaLeadAdapter,
    SocialPlatform,
    TikTokLeadAdapter,
    normalize_consumer_payload,
)
from app.consumers.instagram_flow import (
    InstagramB2CFlow,
    InstagramDraft,
    InstagramFlowResult,
)
from app.consumers.instagram_pilot import InstagramPilotItem, InstagramPilotService
from app.consumers.intelligence import (
    ConsentGate,
    ConsumerClaim,
    ConsumerIntelligenceService,
    ConsumerQualification,
    ConsumerStatus,
    CustomerRoom,
    HandoffBrief,
    QualificationDimension,
)
from app.consumers.models import B2CStage, ConsentRecord, PersonLead, SocialIdentity, Touchpoint
from app.consumers.organic import OrganicIntentClassifier, OrganicOpportunity
from app.consumers.store import ConsumerStore, normalize_contact

__all__ = [
    "B2CStage",
    "ConsentGate",
    "ConsentRecord",
    "ConsumerClaim",
    "ConsumerIngestionError",
    "ConsumerIntelligenceService",
    "ConsumerLeadPayload",
    "ConsumerQualification",
    "ConsumerStatus",
    "ConsumerStore",
    "CustomerRoom",
    "GenericFormAdapter",
    "GovernedHunterDecision",
    "GovernedHunterService",
    "HandoffBrief",
    "HunterDecision",
    "HunterIntent",
    "HunterPromptContract",
    "HunterRequest",
    "InstagramB2CFlow",
    "InstagramDraft",
    "InstagramFlowResult",
    "InstagramPilotItem",
    "InstagramPilotService",
    "LinkedInLeadAdapter",
    "MetaLeadAdapter",
    "OrganicIntentClassifier",
    "OrganicOpportunity",
    "PersonLead",
    "QualificationDimension",
    "SocialIdentity",
    "SocialPlatform",
    "TikTokLeadAdapter",
    "Touchpoint",
    "normalize_consumer_payload",
    "normalize_contact",
]
