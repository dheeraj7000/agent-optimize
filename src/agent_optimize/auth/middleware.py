"""API key authentication middleware.

Simple bearer-token auth for pilot customers:
    Authorization: Bearer ao_live_abc123def456

Keys are SHA-256 hashed in the database. Each key maps to a tenant_id.
All queries are automatically scoped to the tenant.
"""

from __future__ import annotations

import hashlib
import os
import secrets

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from agent_optimize.storage.database import Database

logger = structlog.get_logger()

# Paths that don't require authentication
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def hash_key(key: str) -> str:
    """SHA-256 hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new API key with the ao_ prefix."""
    return f"ao_live_{secrets.token_urlsafe(32)}"


class ApiKeyManager:
    """Manages API keys in the database."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_key(self, tenant_id: str, name: str = "") -> str:
        """Create a new API key for a tenant. Returns the raw key (show once)."""
        raw_key = generate_api_key()
        key_hash = hash_key(raw_key)
        self._db.insert(
            "INSERT INTO api_keys (key_hash, tenant_id, name) VALUES (?, ?, ?)",
            (key_hash, tenant_id, name),
        )
        logger.info("auth.key_created", tenant_id=tenant_id, name=name)
        return raw_key

    def validate_key(self, raw_key: str) -> str | None:
        """Validate an API key. Returns tenant_id if valid, None otherwise."""
        key_hash = hash_key(raw_key)
        row = self._db.execute_one(
            "SELECT tenant_id FROM api_keys WHERE key_hash = ? AND active = 1",
            (key_hash,),
        )
        return row["tenant_id"] if row else None

    def revoke_key(self, raw_key: str) -> bool:
        """Revoke an API key."""
        key_hash = hash_key(raw_key)
        with self._db.connect() as conn:
            cursor = conn.execute("UPDATE api_keys SET active = 0 WHERE key_hash = ?", (key_hash,))
            return cursor.rowcount > 0

    def list_keys(self, tenant_id: str) -> list[dict]:
        """List keys for a tenant (hashes only, not raw keys)."""
        rows = self._db.execute(
            "SELECT key_hash, name, active, created_at FROM api_keys WHERE tenant_id = ?",
            (tenant_id,),
        )
        return [
            {
                "key_prefix": r["key_hash"][:8] + "...",
                "name": r["name"],
                "active": bool(r["active"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]


class AuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that validates API keys and sets tenant context."""

    def __init__(self, app, key_manager: ApiKeyManager, required: bool = True) -> None:
        super().__init__(app)
        self._key_manager = key_manager
        self._required = required

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        # Skip auth for public paths, docs, assets, and frontend SPA routes
        if (
            path in _PUBLIC_PATHS
            or path.startswith("/docs")
            or path.startswith("/assets")
            or path == "/favicon.svg"
            or (not path.startswith("/api") and not path.startswith("/v1"))
        ):
            return await call_next(request)

        # Skip auth if not required (local dev)
        if not self._required:
            request.state.tenant_id = "default"
            return await call_next(request)

        # Extract bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                status_code=401,
                content='{"error": "Missing or invalid Authorization header"}',
                media_type="application/json",
            )

        token = auth_header[7:]  # Strip "Bearer "
        tenant_id = self._key_manager.validate_key(token)

        if not tenant_id:
            logger.warning("auth.invalid_key", path=request.url.path)
            return Response(
                status_code=401,
                content='{"error": "Invalid API key"}',
                media_type="application/json",
            )

        # Set tenant context on request
        request.state.tenant_id = tenant_id

        logger.debug("auth.authenticated", tenant_id=tenant_id, path=request.url.path)
        return await call_next(request)


def is_auth_required() -> bool:
    """Check if API key auth is required (from environment)."""
    return os.environ.get("AGENTOPTIMIZE_API_KEY_REQUIRED", "false").lower() in ("true", "1", "yes")
