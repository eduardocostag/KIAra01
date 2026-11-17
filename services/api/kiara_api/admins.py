"""Who is a Kiara system administrator (full access: early-access modules, unlimited plan, global settings).

One list for the whole API. KIARA_SYSTEM_ADMIN_EMAILS (comma separated) replaces the default when set.
"""
from __future__ import annotations

import os

DEFAULT_ADMIN_EMAILS = ("admin@kiara.local", "eduardocgonsalves@hotmail.com")


def system_admin_emails() -> frozenset[str]:
    configured = os.getenv("KIARA_SYSTEM_ADMIN_EMAILS", "")
    emails = configured.split(",") if configured.strip() else DEFAULT_ADMIN_EMAILS
    return frozenset(email.strip().lower() for email in emails if email.strip())


def is_system_admin(email: str | None) -> bool:
    return bool(email) and email.strip().lower() in system_admin_emails()
