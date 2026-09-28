"""Health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from agent_optimize import __version__
from agent_optimize.api.state import get_state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "version": __version__}


@router.get("/status")
async def status() -> dict:
    from agent_optimize.auth.middleware import is_auth_required

    state = get_state()
    return {
        "status": "running",
        "version": __version__,
        "auth_required": is_auth_required(),
        "traces_stored": state.warehouse.trace_count,
        "detectors": state.detector_registry.list_detectors(),
        "providers": state.cost_catalog.list_providers(),
        "models": state.cost_catalog.list_models(),
    }
