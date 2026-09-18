"""Prometheus /metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from agent_optimize.metrics.prometheus import get_metrics_text

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """Prometheus-compatible metrics endpoint."""
    return get_metrics_text()
