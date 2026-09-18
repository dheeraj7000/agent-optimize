"""Webhook management API — CRUD, deliveries, and test."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from agent_optimize.api.state import get_state
from agent_optimize.webhooks.events import EventType, WebhookConfig, WebhookEvent

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("")
async def create_webhook(config: WebhookConfig) -> dict:
    state = get_state()
    created = state.event_bus.dispatcher.register(config)
    return created.model_dump()


@router.get("")
async def list_webhooks(tenant_id: str | None = None) -> dict:
    state = get_state()
    hooks = state.event_bus.dispatcher.list_webhooks(tenant_id)
    return {"count": len(hooks), "webhooks": [h.model_dump() for h in hooks]}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str) -> dict:
    state = get_state()
    removed = state.event_bus.dispatcher.unregister(webhook_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": True}


@router.get("/{webhook_id}/deliveries")
async def list_deliveries(webhook_id: str, limit: int = Query(default=50, le=200)) -> dict:
    state = get_state()
    deliveries = state.event_bus.dispatcher.list_deliveries(webhook_id, limit)
    return {"count": len(deliveries), "deliveries": [d.model_dump() for d in deliveries]}


@router.post("/test")
async def test_webhook(webhook_id: str) -> dict:
    """Send a test event to a specific webhook."""
    state = get_state()
    hook = state.event_bus.dispatcher.get(webhook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    event = WebhookEvent(event_type="test.ping", payload={"message": "Test from AgentOptimize"})
    deliveries = await state.event_bus.dispatcher.dispatch(event)
    return {"deliveries": [d.model_dump() for d in deliveries]}


@router.get("/events")
async def list_events(limit: int = Query(default=50, le=200)) -> dict:
    """List recent events from the event bus."""
    state = get_state()
    events = state.event_bus.get_events(limit)
    return {"count": len(events), "events": [e.model_dump() for e in events]}


@router.get("/event-types")
async def list_event_types() -> dict:
    return {"event_types": [e.value for e in EventType]}
