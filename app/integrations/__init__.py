"""External communication ports and adapters."""

from app.integrations.email import DraftEmail, EmailService, MicrosoftGraphEmailProvider

__all__ = ["DraftEmail", "EmailService", "MicrosoftGraphEmailProvider"]
