"""Event bus and webhook dispatcher with HMAC signing and async retry."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from urllib.parse import urlparse

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger()


class EventType(str, Enum):
    CANARY_REGRESSED = "canary.regressed"
    CANARY_COMPLETED = "canary.completed"
    CANARY_ROLLED_BACK = "canary.rolled_back"
    AUTOPILOT_DECISION_APPLIED = "autopilot.decision.applied"
    AUTOPILOT_DECISION_BLOCKED = "autopilot.decision.blocked"
    AUTOPILOT_DECISION_PENDING = "autopilot.decision.pending"
    RECOMMENDATION_ACCEPTED = "recommendation.accepted"
    RECOMMENDATION_DEPLOYED = "recommendation.deployed"
    RECOMMENDATION_VERIFIED = "recommendation.verified"
    RECOMMENDATION_ROLLED_BACK = "recommendation.rolled_back"
    PROOF_VALIDATED = "proof.validated"
    PROOF_REJECTED = "proof.rejected"


class WebhookConfig(BaseModel):
    webhook_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    secret: str = ""
    events: list[str] = Field(default_factory=list)
    active: bool = True
    tenant_id: str | None = None
    name: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @field_validator("url")
    @classmethod
    def validate_webhook_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Webhook URLs must use HTTPS and cannot include credentials")
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
            raise ValueError("Local webhook destinations are not allowed")
        return value


class WebhookEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    tenant_id: str | None = None


class WebhookDelivery(BaseModel):
    delivery_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str
    event_id: str
    url: str
    status_code: int = 0
    success: bool = False
    attempts: int = 0
    last_error: str = ""
    delivered_at: datetime | None = None


def _sign_payload(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


class WebhookDispatcher:
    """Tenant-aware async webhook dispatcher with retry and HMAC signing."""

    def __init__(self, max_retries: int = 3) -> None:
        self._webhooks: dict[str, WebhookConfig] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._max_retries = max_retries

    def register(self, config: WebhookConfig) -> WebhookConfig:
        self._webhooks[config.webhook_id] = config
        logger.info("webhook.registered", id=config.webhook_id, events=config.events)
        return config

    def unregister(self, webhook_id: str) -> bool:
        return self._webhooks.pop(webhook_id, None) is not None

    def get(self, webhook_id: str) -> WebhookConfig | None:
        return self._webhooks.get(webhook_id)

    def list_webhooks(self, tenant_id: str | None = None) -> list[WebhookConfig]:
        hooks = list(self._webhooks.values())
        return [h for h in hooks if h.tenant_id == tenant_id] if tenant_id is not None else hooks

    def list_deliveries(self, webhook_id: str | None = None, limit: int = 50) -> list[WebhookDelivery]:
        deliveries = self._deliveries
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        return list(reversed(deliveries[-limit:]))

    async def dispatch(self, event: WebhookEvent, webhook_id: str | None = None) -> list[WebhookDelivery]:
        """Deliver only to the event tenant's hooks; optionally target one hook."""
        matching = [
            w for w in self._webhooks.values()
            if w.active and (event.tenant_id is None or w.tenant_id == event.tenant_id)
            and (webhook_id is None or w.webhook_id == webhook_id)
            and self._matches(w, event)
        ]
        deliveries = []
        for webhook in matching:
            delivery = await self._send(webhook, event)
            self._deliveries.append(delivery)
            deliveries.append(delivery)
        return deliveries

    async def _send(self, webhook: WebhookConfig, event: WebhookEvent) -> WebhookDelivery:
        payload_str = json.dumps({"event_id": event.event_id, "event_type": event.event_type,
                                  "timestamp": event.timestamp.isoformat(), "payload": event.payload}, default=str)
        headers = {"Content-Type": "application/json"}
        if webhook.secret:
            headers["X-AgentOptimize-Signature"] = _sign_payload(payload_str, webhook.secret)
        delivery = WebhookDelivery(webhook_id=webhook.webhook_id, event_id=event.event_id, url=webhook.url)
        for attempt in range(1, self._max_retries + 1):
            delivery.attempts = attempt
            try:
                # Prevent redirects to private targets. The URL validator requires HTTPS;
                # redirect following is disabled so an allowed URL cannot bounce to localhost.
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                    resp = await client.post(webhook.url, content=payload_str, headers=headers)
                delivery.status_code = resp.status_code
                delivery.success = 200 <= resp.status_code < 300
                if delivery.success:
                    delivery.delivered_at = datetime.now(tz=UTC)
                    return delivery
                delivery.last_error = f"HTTP {resp.status_code}"
            except Exception as exc:
                delivery.last_error = str(exc)
            if attempt < self._max_retries:
                await asyncio.sleep(2 ** attempt)
        logger.warning("webhook.failed", id=webhook.webhook_id, event=event.event_type,
                       attempts=delivery.attempts, error=delivery.last_error)
        return delivery

    @staticmethod
    def _matches(webhook: WebhookConfig, event: WebhookEvent) -> bool:
        return not webhook.events or event.event_type in webhook.events


class EventBus:
    """Central event bus that routes events to webhook dispatcher."""

    def __init__(self, dispatcher: WebhookDispatcher) -> None:
        self._dispatcher = dispatcher
        self._event_log: list[WebhookEvent] = []

    async def emit(self, event_type: str | EventType, payload: dict, tenant_id: str | None = None) -> None:
        event = WebhookEvent(event_type=event_type.value if isinstance(event_type, EventType) else event_type,
                             payload=payload, tenant_id=tenant_id)
        self._event_log.append(event)
        await self._dispatcher.dispatch(event)

    def get_events(self, limit: int = 100) -> list[WebhookEvent]:
        return list(reversed(self._event_log[-limit:]))

    @property
    def dispatcher(self) -> WebhookDispatcher:
        return self._dispatcher
