"""Event bus and webhook dispatcher with HMAC signing and async retry."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from enum import Enum

import httpx
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    # Canary
    CANARY_REGRESSED = "canary.regressed"
    CANARY_COMPLETED = "canary.completed"
    CANARY_ROLLED_BACK = "canary.rolled_back"
    # Autopilot
    AUTOPILOT_DECISION_APPLIED = "autopilot.decision.applied"
    AUTOPILOT_DECISION_BLOCKED = "autopilot.decision.blocked"
    AUTOPILOT_DECISION_PENDING = "autopilot.decision.pending"
    # Recommendations
    RECOMMENDATION_ACCEPTED = "recommendation.accepted"
    RECOMMENDATION_DEPLOYED = "recommendation.deployed"
    RECOMMENDATION_VERIFIED = "recommendation.verified"
    RECOMMENDATION_ROLLED_BACK = "recommendation.rolled_back"
    # Proofs
    PROOF_VALIDATED = "proof.validated"
    PROOF_REJECTED = "proof.rejected"


class WebhookConfig(BaseModel):
    webhook_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    secret: str = ""  # HMAC-SHA256 signing key
    events: list[str] = Field(default_factory=list)  # Empty = all events
    active: bool = True
    tenant_id: str | None = None
    name: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


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


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def _sign_payload(payload: str, secret: str) -> str:
    """HMAC-SHA256 signature for webhook payload verification."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


class WebhookDispatcher:
    """Async webhook dispatcher with retry and HMAC signing."""

    def __init__(self, max_retries: int = 3) -> None:
        self._webhooks: dict[str, WebhookConfig] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._max_retries = max_retries

    # -- Config CRUD --

    def register(self, config: WebhookConfig) -> WebhookConfig:
        self._webhooks[config.webhook_id] = config
        logger.info("webhook.registered", id=config.webhook_id, url=config.url, events=config.events)
        return config

    def unregister(self, webhook_id: str) -> bool:
        return self._webhooks.pop(webhook_id, None) is not None

    def get(self, webhook_id: str) -> WebhookConfig | None:
        return self._webhooks.get(webhook_id)

    def list_webhooks(self, tenant_id: str | None = None) -> list[WebhookConfig]:
        hooks = list(self._webhooks.values())
        if tenant_id:
            hooks = [h for h in hooks if h.tenant_id == tenant_id]
        return hooks

    def list_deliveries(self, webhook_id: str | None = None, limit: int = 50) -> list[WebhookDelivery]:
        deliveries = self._deliveries
        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]
        return list(reversed(deliveries[-limit:]))

    # -- Dispatch --

    async def dispatch(self, event: WebhookEvent) -> list[WebhookDelivery]:
        """Send event to all matching webhooks."""
        matching = [
            w for w in self._webhooks.values()
            if w.active and self._matches(w, event)
        ]

        deliveries = []
        for webhook in matching:
            delivery = await self._send(webhook, event)
            self._deliveries.append(delivery)
            deliveries.append(delivery)

        return deliveries

    async def _send(self, webhook: WebhookConfig, event: WebhookEvent) -> WebhookDelivery:
        """Send with retry and HMAC signing."""
        payload_str = json.dumps({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }, default=str)

        headers = {"Content-Type": "application/json"}
        if webhook.secret:
            headers["X-AgentOptimize-Signature"] = _sign_payload(payload_str, webhook.secret)

        delivery = WebhookDelivery(
            webhook_id=webhook.webhook_id,
            event_id=event.event_id,
            url=webhook.url,
        )

        for attempt in range(1, self._max_retries + 1):
            delivery.attempts = attempt
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(webhook.url, content=payload_str, headers=headers)
                delivery.status_code = resp.status_code
                delivery.success = 200 <= resp.status_code < 300
                if delivery.success:
                    delivery.delivered_at = datetime.now(tz=UTC)
                    logger.info("webhook.delivered", id=webhook.webhook_id, event=event.event_type)
                    return delivery
                delivery.last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                delivery.last_error = str(e)

            if attempt < self._max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        logger.warning("webhook.failed", id=webhook.webhook_id, event=event.event_type,
                        attempts=delivery.attempts, error=delivery.last_error)
        return delivery

    @staticmethod
    def _matches(webhook: WebhookConfig, event: WebhookEvent) -> bool:
        if not webhook.events:
            return True  # Empty filter = all events
        return event.event_type in webhook.events


# ---------------------------------------------------------------------------
# Global event bus
# ---------------------------------------------------------------------------


class EventBus:
    """Central event bus that routes events to webhook dispatcher and audit log."""

    def __init__(self, dispatcher: WebhookDispatcher) -> None:
        self._dispatcher = dispatcher
        self._event_log: list[WebhookEvent] = []

    async def emit(self, event_type: str | EventType, payload: dict, tenant_id: str | None = None) -> None:
        event = WebhookEvent(
            event_type=event_type.value if isinstance(event_type, EventType) else event_type,
            payload=payload,
            tenant_id=tenant_id,
        )
        self._event_log.append(event)
        await self._dispatcher.dispatch(event)

    def get_events(self, limit: int = 100) -> list[WebhookEvent]:
        return list(reversed(self._event_log[-limit:]))

    @property
    def dispatcher(self) -> WebhookDispatcher:
        return self._dispatcher
