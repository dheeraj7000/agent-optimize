"""Shared test fixtures — trace factories, app clients, and database setup."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from agent_optimize.models.traces import (
    CostBreakdown,
    ModelCallSpan,
    NormalizedSpan,
    NormalizedTrace,
    SpanKind,
    SpanStatus,
    TokenUsage,
    ToolCallSpan,
)


# ---------------------------------------------------------------------------
# Trace factories
# ---------------------------------------------------------------------------


def make_span(
    *,
    span_kind: SpanKind = SpanKind.MODEL_CALL,
    model: str = "gpt-4o",
    provider: str = "openai",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    input_cost: float = 0.0025,
    output_cost: float = 0.002,
    duration_ms: float = 500.0,
    status: SpanStatus = SpanStatus.OK,
    is_retry: bool = False,
    retry_number: int = 0,
    tool_name: str = "",
    tool_success: bool = True,
    tool_input_hash: str | None = None,
    name: str = "",
    parent_span_id: str | None = None,
    trace_id: str = "trace-1",
) -> NormalizedSpan:
    """Factory for normalized spans with sensible defaults."""
    now = datetime.now(tz=UTC)
    span_id = str(uuid.uuid4())

    model_call = None
    tool_call = None

    if span_kind == SpanKind.MODEL_CALL:
        model_call = ModelCallSpan(
            provider=provider,
            model=model,
            tokens=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )
    elif span_kind == SpanKind.TOOL_CALL:
        tool_call = ToolCallSpan(
            tool_name=tool_name or "search",
            tool_success=tool_success,
            tool_input_hash=tool_input_hash,
        )

    return NormalizedSpan(
        span_id=span_id,
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        span_kind=span_kind,
        name=name or span_kind.value,
        status=status,
        start_time=now,
        end_time=now + timedelta(milliseconds=duration_ms),
        duration_ms=duration_ms,
        cost=CostBreakdown(input_cost=input_cost, output_cost=output_cost),
        model_call=model_call,
        tool_call=tool_call,
        is_retry=is_retry,
        retry_number=retry_number,
    )


def make_trace(
    *,
    trace_id: str | None = None,
    tenant_id: str = "test-tenant",
    spans: list[NormalizedSpan] | None = None,
    success: bool = True,
    total_cost: float | None = None,
    duration_ms: float = 5000.0,
    task_class: str | None = None,
) -> NormalizedTrace:
    """Factory for normalized traces with sensible defaults."""
    trace_id = trace_id or str(uuid.uuid4())
    now = datetime.now(tz=UTC)

    if spans is None:
        spans = [
            make_span(trace_id=trace_id, model="gpt-4o", input_tokens=2000, output_tokens=500),
            make_span(trace_id=trace_id, model="gpt-4o", input_tokens=3000, output_tokens=300),
        ]

    trace = NormalizedTrace(
        trace_id=trace_id,
        tenant_id=tenant_id,
        task_class=task_class,
        start_time=now,
        end_time=now + timedelta(milliseconds=duration_ms),
        duration_ms=duration_ms,
        spans=spans,
        success=success,
    )
    trace.recompute_aggregates()

    if total_cost is not None:
        trace.total_cost = total_cost

    return trace


# ---------------------------------------------------------------------------
# App fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client():
    """TestClient with in-memory storage (no SQLite, no auth)."""
    os.environ.pop("AGENTOPTIMIZE_DB_PATH", None)
    os.environ.pop("AGENTOPTIMIZE_API_KEY_REQUIRED", None)

    from agent_optimize.api.app import create_app

    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def sqlite_db():
    """Temporary SQLite database for storage tests."""
    from agent_optimize.storage.database import Database

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database(db_path)
    yield db

    os.unlink(db_path)
