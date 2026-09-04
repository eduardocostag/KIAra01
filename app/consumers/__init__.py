"""Consumer (B2C) qualification domain."""

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
    "HandoffBrief",
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
