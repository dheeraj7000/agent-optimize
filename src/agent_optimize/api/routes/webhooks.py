"""Webhook management API with authenticated tenant ownership."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from agent_optimize.api.state import get_state
from agent_optimize.webhooks.events import EventType, WebhookConfig, WebhookEvent

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _tenant(request: Request) -> str | None:
    return getattr(request.state, "tenant_id", None)


def _get_owned(webhook_id: str, tenant_id: str | None):
    hook = get_state().event_bus.dispatcher.get(webhook_id)
    if not hook or (tenant_id is not None and hook.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Webhook not found")
    return hook


@router.post("")
async def create_webhook(config: WebhookConfig, request: Request) -> dict:
    tenant_id = _tenant(request)
    if tenant_id is not None:
        config.tenant_id = tenant_id
    created = get_state().event_bus.dispatcher.register(config)
    return created.model_dump(exclude={"secret"})


@router.get("")
async def list_webhooks(request: Request, tenant_id: str | None = None) -> dict:
    owner = _tenant(request) if _tenant(request) is not None else tenant_id
    hooks = get_state().event_bus.dispatcher.list_webhooks(owner)
    return {"count": len(hooks), "webhooks": [h.model_dump(exclude={"secret"}) for h in hooks]}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str, request: Request) -> dict:
    _get_owned(webhook_id, _tenant(request))
    get_state().event_bus.dispatcher.unregister(webhook_id)
    return {"deleted": True}


@router.get("/{webhook_id}/deliveries")
async def list_deliveries(webhook_id: str, request: Request, limit: int = Query(default=50, le=200)) -> dict:
    _get_owned(webhook_id, _tenant(request))
    deliveries = get_state().event_bus.dispatcher.list_deliveries(webhook_id, limit)
    return {"count": len(deliveries), "deliveries": [d.model_dump() for d in deliveries]}


@router.post("/test")
async def test_webhook(request: Request, webhook_id: str) -> dict:
    tenant_id = _tenant(request)
    hook = _get_owned(webhook_id, tenant_id)
    event = WebhookEvent(event_type="test.ping", payload={"message": "Test from AgentOptimize"}, tenant_id=hook.tenant_id)
    deliveries = await get_state().event_bus.dispatcher.dispatch(event)
    return {"deliveries": [d.model_dump() for d in deliveries if d.webhook_id == webhook_id]}


@router.get("/events")
async def list_events(request: Request, limit: int = Query(default=50, le=200)) -> dict:
    tenant_id = _tenant(request)
    events = get_state().event_bus.get_events(limit)
    if tenant_id is not None:
        events = [event for event in events if event.tenant_id == tenant_id]
    return {"count": len(events), "events": [e.model_dump() for e in events]}


@router.get("/event-types")
async def list_event_types() -> dict:
    return {"event_types": [e.value for e in EventType]}
