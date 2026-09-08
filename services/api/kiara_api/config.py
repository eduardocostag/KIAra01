from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiSettings:
    environment: str = "development"
    demo_auth_enabled: bool = False
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_jwks_cache_ttl_seconds: int = 300
    database_url: str | None = None

    @classmethod
    def from_env(cls) -> ApiSettings:
        environment = os.getenv("KIARA_ENV", "development").strip().lower()
        demo = os.getenv("KIARA_WEB_DEMO_AUTH", "false").strip().lower() == "true"
        origins = tuple(
            origin.strip()
            for origin in os.getenv("KIARA_CORS_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        )
        return cls(
            environment=environment,
            demo_auth_enabled=demo,
            cors_origins=origins,
            oidc_issuer=os.getenv("KIARA_OIDC_ISSUER") or None,
            oidc_audience=os.getenv("KIARA_OIDC_AUDIENCE") or None,
            oidc_jwks_url=os.getenv("KIARA_OIDC_JWKS_URL") or None,
            oidc_jwks_cache_ttl_seconds=int(
                os.getenv("KIARA_OIDC_JWKS_CACHE_TTL_SECONDS", "300")
            ),
            database_url=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL") or None,
        )

    @property
    def oidc_configured(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_jwks_url)

    def validate(self) -> None:
        if self.demo_auth_enabled and self.environment not in {"development", "test"}:
            raise RuntimeError("Demo authentication is forbidden outside development/test")
        if "*" in self.cors_origins:
            raise RuntimeError("Wildcard CORS origins are forbidden")
        if bool(self.oidc_issuer) != bool(self.oidc_jwks_url):
            raise RuntimeError("OIDC issuer and JWKS URL must be configured together")
        if self.oidc_jwks_url and not self.oidc_jwks_url.startswith("https://"):
            raise RuntimeError("OIDC JWKS URL must use HTTPS")
        if not 30 <= self.oidc_jwks_cache_ttl_seconds <= 3600:
            raise RuntimeError("OIDC JWKS cache TTL must be between 30 and 3600 seconds")
        if self.environment == "production" and not self.database_url:
            raise RuntimeError("POSTGRES_URL is required in production")
