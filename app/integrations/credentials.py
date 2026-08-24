from __future__ import annotations

import os
from typing import Protocol


class CredentialProvider(Protocol):
    def get(self, name: str) -> str | None: ...


class EnvironmentCredentials:
    """Reads secrets at use time; values are never copied into application config."""

    def get(self, name: str) -> str | None:
        return os.environ.get(name)


class WindowsCredentialManager:
    def get(self, name: str) -> str | None:
        try:
            import win32cred

            credential = win32cred.CredRead(name, win32cred.CRED_TYPE_GENERIC)
            value = credential.get("CredentialBlob")
            return value.decode("utf-16-le") if isinstance(value, bytes) else str(value)
        except (ImportError, OSError):
            return None


class ChainedCredentials:
    def __init__(self, *providers: CredentialProvider) -> None:
        self.providers = providers

    def get(self, name: str) -> str | None:
        return next((value for provider in self.providers if (value := provider.get(name))), None)
