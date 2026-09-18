"""OAuth2/OIDC authentication — JWT validation with external identity providers.

Supports Google, GitHub, Okta, Auth0, or any OIDC-compliant provider.
Coexists with API key auth: try JWT first, fall back to API key.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import Enum

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class Role(str, Enum):
    VIEWER = "viewer"  # Read-only access
    OPERATOR = "operator"  # Can accept/deploy recommendations
    ADMIN = "admin"  # Full access including config changes


class OIDCConfig(BaseModel):
    """OIDC provider configuration."""
    issuer_url: str = ""  # e.g. https://accounts.google.com
    client_id: str = ""
    audience: str = ""
    jwks_uri: str = ""  # Auto-discovered from issuer if empty
    tenant_claim: str = "sub"  # Which JWT claim maps to tenant_id
    role_claim: str = "role"  # Which JWT claim maps to role
    default_role: Role = Role.VIEWER


class UserContext(BaseModel):
    """Authenticated user context extracted from JWT or API key."""
    tenant_id: str = ""
    user_id: str = ""
    email: str = ""
    role: Role = Role.VIEWER
    auth_method: str = ""  # "jwt", "api_key"
    provider: str = ""  # "google", "github", etc.


# ---------------------------------------------------------------------------
# JWKS cache and token validation
# ---------------------------------------------------------------------------


class JWKSCache:
    """Caches JWKS (JSON Web Key Sets) from OIDC providers."""

    def __init__(self) -> None:
        self._keys: dict[str, dict] = {}
        self._last_fetch: datetime | None = None

    async def get_keys(self, jwks_uri: str) -> dict:
        """Fetch and cache JWKS from the provider."""
        if self._keys and self._last_fetch:
            age = (datetime.now(tz=UTC) - self._last_fetch).total_seconds()
            if age < 3600:  # Cache for 1 hour
                return self._keys

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(jwks_uri)
                resp.raise_for_status()
                data = resp.json()
                self._keys = {k["kid"]: k for k in data.get("keys", [])}
                self._last_fetch = datetime.now(tz=UTC)
                logger.info("jwks.refreshed", uri=jwks_uri, keys=len(self._keys))
        except Exception:
            logger.exception("jwks.fetch_failed", uri=jwks_uri)

        return self._keys


class OIDCProvider:
    """Validates JWT tokens from an OIDC provider.

    Note: Full JWT cryptographic validation requires PyJWT + cryptography.
    This implementation provides the framework and config; add `pyjwt[crypto]`
    to dependencies for production use.
    """

    def __init__(self, config: OIDCConfig) -> None:
        self._config = config
        self._jwks = JWKSCache()

    @property
    def configured(self) -> bool:
        return bool(self._config.issuer_url and self._config.client_id)

    async def validate_token(self, token: str) -> UserContext | None:
        """Validate a JWT token and return user context.

        Production: use PyJWT to verify signature against JWKS.
        Current: decode claims without signature verification (dev mode).
        """
        if not self.configured:
            return None

        try:
            # Decode JWT payload (base64 middle segment)
            import base64
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Pad base64
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            import json
            claims = json.loads(base64.urlsafe_b64decode(payload_b64))

            # Extract user context from claims
            tenant_id = str(claims.get(self._config.tenant_claim, ""))
            role_str = claims.get(self._config.role_claim, self._config.default_role.value)

            try:
                role = Role(role_str)
            except ValueError:
                role = self._config.default_role

            return UserContext(
                tenant_id=tenant_id,
                user_id=claims.get("sub", ""),
                email=claims.get("email", ""),
                role=role,
                auth_method="jwt",
                provider=claims.get("iss", ""),
            )
        except Exception:
            logger.warning("oidc.token_validation_failed")
            return None

    async def discover_jwks_uri(self) -> str:
        """Auto-discover JWKS URI from OIDC well-known endpoint."""
        if self._config.jwks_uri:
            return self._config.jwks_uri

        well_known = f"{self._config.issuer_url.rstrip('/')}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(well_known)
                data = resp.json()
                uri = data.get("jwks_uri", "")
                self._config.jwks_uri = uri
                return uri
        except Exception:
            logger.exception("oidc.discovery_failed")
            return ""


def load_oidc_config() -> OIDCConfig:
    """Load OIDC configuration from environment variables."""
    return OIDCConfig(
        issuer_url=os.environ.get("AGENTOPTIMIZE_OIDC_ISSUER", ""),
        client_id=os.environ.get("AGENTOPTIMIZE_OIDC_CLIENT_ID", ""),
        audience=os.environ.get("AGENTOPTIMIZE_OIDC_AUDIENCE", ""),
        jwks_uri=os.environ.get("AGENTOPTIMIZE_OIDC_JWKS_URI", ""),
        tenant_claim=os.environ.get("AGENTOPTIMIZE_OIDC_TENANT_CLAIM", "sub"),
        role_claim=os.environ.get("AGENTOPTIMIZE_OIDC_ROLE_CLAIM", "role"),
    )
