"""Prometheus metrics — business, autopilot, and system metrics.

Uses prometheus_client library. If not installed, metrics are no-ops.
Install: pip install prometheus-client
"""

from __future__ import annotations

import time
from typing import Any

import structlog

logger = structlog.get_logger()

try:
    from prometheus_client import (
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Metric definitions (no-ops if prometheus_client not installed)
# ---------------------------------------------------------------------------

if PROMETHEUS_AVAILABLE:
    # Business metrics
    TRACES_INGESTED = Counter(
        "agentoptimize_traces_ingested_total",
        "Total traces ingested",
    )
    TRACE_COST = Histogram(
        "agentoptimize_trace_cost_dollars",
        "Cost per trace in dollars",
        buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0),
    )
    WASTE_DETECTED = Histogram(
        "agentoptimize_waste_detected_dollars",
        "Waste detected per trace in dollars",
        buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0),
    )
    RECOMMENDATIONS_TOTAL = Gauge(
        "agentoptimize_recommendations_total",
        "Total recommendations by status",
        ["status"],
    )
    SAVINGS_IDENTIFIED = Gauge(
        "agentoptimize_savings_identified_dollars",
        "Total identified monthly savings",
    )
    SAVINGS_VERIFIED = Gauge(
        "agentoptimize_savings_verified_dollars",
        "Total verified monthly savings",
    )

    # Autopilot metrics
    AUTOPILOT_DECISIONS = Counter(
        "agentoptimize_autopilot_decisions_total",
        "Autopilot decisions by outcome",
        ["outcome"],
    )
    ROUTING_DECISIONS = Counter(
        "agentoptimize_routing_decisions_total",
        "Routing decisions by complexity tier",
        ["complexity"],
    )
    VERIFICATION_SKIP_RATE = Gauge(
        "agentoptimize_verification_skip_rate",
        "Fraction of verification decisions that were skipped",
    )

    # System metrics
    REQUEST_DURATION = Histogram(
        "agentoptimize_request_duration_seconds",
        "HTTP request duration",
        ["method", "endpoint", "status"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )
    REQUEST_TOTAL = Counter(
        "agentoptimize_request_total",
        "HTTP requests total",
        ["method", "status"],
    )
    TRACES_STORED = Gauge(
        "agentoptimize_traces_stored",
        "Number of traces in warehouse",
    )


# ---------------------------------------------------------------------------
# Helper functions (safe to call regardless of prometheus_client availability)
# ---------------------------------------------------------------------------


def record_trace_ingested(cost: float = 0.0, waste: float = 0.0) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    TRACES_INGESTED.inc()
    if cost > 0:
        TRACE_COST.observe(cost)
    if waste > 0:
        WASTE_DETECTED.observe(waste)


def record_autopilot_decision(outcome: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    AUTOPILOT_DECISIONS.labels(outcome=outcome).inc()


def record_routing_decision(complexity: str) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    ROUTING_DECISIONS.labels(complexity=complexity).inc()


def set_verification_skip_rate(rate: float) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    VERIFICATION_SKIP_RATE.set(rate)


def set_traces_stored(count: int) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    TRACES_STORED.set(count)


def set_recommendation_stats(by_status: dict[str, int], identified: float, verified: float) -> None:
    if not PROMETHEUS_AVAILABLE:
        return
    for status, count in by_status.items():
        RECOMMENDATIONS_TOTAL.labels(status=status).set(count)
    SAVINGS_IDENTIFIED.set(identified)
    SAVINGS_VERIFIED.set(verified)


def get_metrics_text() -> str:
    """Generate Prometheus text format for /metrics endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return "# prometheus_client not installed\n"
    return generate_latest(REGISTRY).decode("utf-8")


# ---------------------------------------------------------------------------
# FastAPI middleware for request metrics
# ---------------------------------------------------------------------------


class MetricsMiddleware:
    """ASGI middleware that records request duration and counts."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not PROMETHEUS_AVAILABLE:
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code = 200

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.monotonic() - start
            method = scope.get("method", "GET")
            path = scope.get("path", "/")
            # Normalize path (strip IDs for cardinality control)
            endpoint = _normalize_path(path)
            REQUEST_DURATION.labels(method=method, endpoint=endpoint, status=str(status_code)).observe(duration)
            REQUEST_TOTAL.labels(method=method, status=str(status_code)).inc()


def _normalize_path(path: str) -> str:
    """Replace UUIDs and IDs in paths to control metric cardinality."""
    parts = path.split("/")
    normalized = []
    for part in parts:
        if len(part) > 8 and ("-" in part or len(part) == 32):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/".join(normalized)
