"""API key authentication middleware and tenant boundary enforcement."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from urllib.parse import parse_qsl, urlencode

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from agent_optimize.storage.database import Database

logger = structlog.get_logger()
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    return f"ao_live_{secrets.token_urlsafe(32)}"


class ApiKeyManager:
    """Manages API keys in the database."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create_key(self, tenant_id: str, name: str = "") -> str:
        raw_key = generate_api_key()
        self._db.insert(
            "INSERT INTO api_keys (key_hash, tenant_id, name) VALUES (?, ?, ?)",
            (hash_key(raw_key), tenant_id, name),
        )
        logger.info("auth.key_created", tenant_id=tenant_id, name=name)
        return raw_key

    def validate_key(self, raw_key: str) -> str | None:
        row = self._db.execute_one(
            "SELECT tenant_id FROM api_keys WHERE key_hash = ? AND active = 1",
            (hash_key(raw_key),),
        )
        return row["tenant_id"] if row else None

    def revoke_key(self, raw_key: str) -> bool:
        with self._db.connect() as conn:
            cursor = conn.execute("UPDATE api_keys SET active = 0 WHERE key_hash = ?", (hash_key(raw_key),))
            return cursor.rowcount > 0

    def list_keys(self, tenant_id: str) -> list[dict]:
        rows = self._db.execute(
            "SELECT key_hash, name, active, created_at FROM api_keys WHERE tenant_id = ?", (tenant_id,),
        )
        return [{"key_prefix": r["key_hash"][:8] + "...", "name": r["name"],
                 "active": bool(r["active"]), "created_at": r["created_at"]} for r in rows]


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate bearer keys and enforce tenant boundaries for API resources."""

    def __init__(self, app, key_manager: ApiKeyManager | None = None, required: bool = True) -> None:
        super().__init__(app)
        self._key_manager = key_manager
        self._required = required

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/docs"):
            return await call_next(request)

        tenant_id = None
        if self._required:
            auth_header = request.headers.get("authorization", "")
            token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
            tenant_id = self._key_manager.validate_key(token) if token and self._key_manager else None
            if not tenant_id:
                return Response(status_code=401, content='{"error":"Missing or invalid API key"}', media_type="application/json")
        request.state.tenant_id = tenant_id
        request.state.authenticated = self._required

        if self._required:
            # Never let a caller select another tenant through query parameters.
            pairs = [(k, v) for k, v in parse_qsl(request.scope.get("query_string", b"").decode(), keep_blank_values=True)
                     if k != "tenant_id"]
            if request.url.path.startswith(("/api/traces", "/api/dashboard", "/api/recommendations")):
                pairs.append(("tenant_id", tenant_id))
                request.scope["query_string"] = urlencode(pairs).encode()

            denied = self._resource_belongs_to_other_tenant(request, tenant_id)
            if denied:
                return Response(status_code=404, content='{"detail":"Not found"}', media_type="application/json")

            # Tenant is also accepted in the recommendation-generation JSON body.
            # Replace any caller-supplied value before the route parses the request.
            if request.url.path == "/api/recommendations/generate" and request.method == "POST":
                try:
                    body = await request.json()
                    if not isinstance(body, dict):
                        return Response(status_code=400, content='{"detail":"Invalid JSON body"}', media_type="application/json")
                    body["tenant_id"] = tenant_id
                    encoded = json.dumps(body).encode()
                    sent = False
                    async def receive():
                        nonlocal sent
                        if sent:
                            return {"type": "http.request", "body": b"", "more_body": False}
                        sent = True
                        return {"type": "http.request", "body": encoded, "more_body": False}
                    request._receive = receive
                except (ValueError, TypeError):
                    return Response(status_code=400, content='{"detail":"Invalid JSON body"}', media_type="application/json")

        return await call_next(request)

    @staticmethod
    def _resource_belongs_to_other_tenant(request: Request, tenant_id: str) -> bool:
        """Check ownership for path-based trace, recommendation, and experiment IDs."""
        match = re.match(r"^/api/(traces|recommendations|experiments)/([^/]+)", request.url.path)
        if not match:
            return False
        resource, resource_id = match.groups()
        try:
            from agent_optimize.api.state import get_state
            state = get_state()
            if resource == "traces":
                item = state.warehouse.get_trace(resource_id)
                return item is not None and item.tenant_id != tenant_id
            if resource == "recommendations":
                item = state.recommendation_store.get(resource_id)
                return item is not None and item.tenant_id != tenant_id
            experiment = state.replay_engine.get_experiment(resource_id)
            if experiment is None:
                return False
            traces = [state.warehouse.get_trace(tid) for tid in experiment.trace_ids]
            return not traces or any(t is None or t.tenant_id != tenant_id for t in traces)
        except (RuntimeError, AssertionError):
            return False


def is_auth_required() -> bool:
    """Require authentication by default in production; opt out only for local dev."""
    value = os.environ.get("AGENTOPTIMIZE_API_KEY_REQUIRED")
    if value is not None:
        return value.lower() in ("true", "1", "yes")
    return os.environ.get("AGENTOPTIMIZE_ENV", "development").lower() in {"prod", "production"}
