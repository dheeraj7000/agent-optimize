"""Onboarding API — progress tracking and demo seed."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from agent_optimize.api.state import get_state

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class SeedRequest(BaseModel):
    count: int = 20


class CompleteStepRequest(BaseModel):
    step_key: str


@router.get("/status")
async def get_onboarding_status(tenant_id: str = "default") -> dict:
    """Get onboarding progress for a tenant."""
    state = get_state()
    status = state.onboarding.get_status(tenant_id)
    return status.model_dump()


@router.post("/complete-step")
async def complete_step(body: CompleteStepRequest, tenant_id: str = "default") -> dict:
    """Mark an onboarding step as completed."""
    state = get_state()
    status = state.onboarding.complete_step(tenant_id, body.step_key)
    return status.model_dump()


@router.post("/seed-demo")
async def seed_demo_data(body: SeedRequest) -> dict:
    """Seed synthetic traces for demo/onboarding.

    Generates realistic OTel traces and ingests them through the normal pipeline.
    """
    from agent_optimize.ingestion.otlp_receiver import _extract_spans_from_otlp, _normalizer, _on_trace_callback
    from agent_optimize.onboarding.service import generate_demo_traces

    payloads = generate_demo_traces(body.count)
    ingested = 0

    for payload in payloads:
        raw_spans = _extract_spans_from_otlp(payload)
        traces_map: dict[str, list] = {}
        for span in raw_spans:
            tid = span.get("traceId", "unknown")
            traces_map.setdefault(tid, []).append(span)

        for spans in traces_map.values():
            trace = _normalizer.normalize_trace(spans)
            if trace and _on_trace_callback:
                await _on_trace_callback(trace)
                ingested += 1

    # Mark onboarding step
    state = get_state()
    state.onboarding.complete_step("default", "connect_traces")

    return {"ingested": ingested, "message": f"Seeded {ingested} demo traces"}
