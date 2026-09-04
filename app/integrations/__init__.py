"""External communication ports and adapters."""

from app.integrations.email import DraftEmail, EmailService, MicrosoftGraphEmailProvider
from app.integrations.instagram import (
    InstagramApiError,
    InstagramContractError,
    InstagramMessage,
    InstagramMessagingClient,
    parse_message_events,
    verify_webhook_challenge,
    verify_webhook_signature,
)

__all__ = [
    "DraftEmail",
    "EmailService",
    "InstagramApiError",
    "InstagramContractError",
    "InstagramMessage",
    "InstagramMessagingClient",
    "MicrosoftGraphEmailProvider",
    "parse_message_events",
    "verify_webhook_challenge",
    "verify_webhook_signature",
]
