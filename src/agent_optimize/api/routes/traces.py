"""Trace query and drill-down endpoints with tenant-owned lookups."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request

from agent_optimize.api.state import get_state

router = APIRouter(prefix="/api/traces", tags=["traces"])


def _tenant(request: Request, supplied: str | None = None) -> str | None:
    authenticated = getattr(request.state, "authenticated", False)
    return request.state.tenant_id if authenticated else (supplied or getattr(request.state, "tenant_id", None))


def _get_trace(trace_id: str, tenant_id: str | None):
    trace = get_state().warehouse.get_trace(trace_id)
    if not trace or (tenant_id is not None and trace.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.get("")
async def list_traces(
    request: Request,
    tenant_id: str | None = None,
    task_class: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    min_cost: float | None = None,
    success_only: bool | None = None,
    limit: int = Query(default=100, le=1000),
) -> dict:
    traces = get_state().warehouse.query_traces(
        tenant_id=_tenant(request, tenant_id), task_class=task_class, start_time=start_time,
        end_time=end_time, min_cost=min_cost, success_only=success_only, limit=limit,
    )
    return {"count": len(traces), "traces": [
        {"trace_id": t.trace_id, "task_class": t.task_class, "start_time": t.start_time.isoformat(),
         "duration_ms": t.duration_ms, "total_cost": t.total_cost,
         "model_call_count": t.model_call_count, "tool_call_count": t.tool_call_count,
         "retry_count": t.retry_count, "success": t.success, "unique_models": t.unique_models,
         "unique_tools": t.unique_tools, "source_framework": t.source_framework} for t in traces
    ]}


@router.get("/{trace_id}")
async def get_trace(trace_id: str, request: Request) -> dict:
    trace = _get_trace(trace_id, _tenant(request))
    return {
        "trace_id": trace.trace_id, "tenant_id": trace.tenant_id, "task_class": trace.task_class,
        "start_time": trace.start_time.isoformat(), "end_time": trace.end_time.isoformat(),
        "duration_ms": trace.duration_ms, "total_cost": trace.total_cost,
        "total_input_tokens": trace.total_input_tokens, "total_output_tokens": trace.total_output_tokens,
        "model_call_count": trace.model_call_count, "tool_call_count": trace.tool_call_count,
        "retry_count": trace.retry_count, "success": trace.success, "error_message": trace.error_message,
        "unique_models": trace.unique_models, "unique_tools": trace.unique_tools,
        "source_framework": trace.source_framework,
        "spans": [
            {"span_id": s.span_id, "parent_span_id": s.parent_span_id,
             "span_kind": s.span_kind.value, "name": s.name, "status": s.status.value,
             "start_time": s.start_time.isoformat(), "end_time": s.end_time.isoformat(),
             "duration_ms": s.duration_ms,
             "cost": {"input_cost": s.cost.input_cost, "output_cost": s.cost.output_cost,
                      "tool_cost": s.cost.tool_cost, "total_cost": s.cost.total_cost},
             "model_call": {"provider": s.model_call.provider, "model": s.model_call.model,
                            "input_tokens": s.model_call.tokens.input_tokens,
                            "output_tokens": s.model_call.tokens.output_tokens} if s.model_call else None,
             "tool_call": {"tool_name": s.tool_call.tool_name, "tool_success": s.tool_call.tool_success,
                           "tool_error": s.tool_call.tool_error} if s.tool_call else None,
             "is_retry": s.is_retry, "retry_number": s.retry_number, "agent_name": s.agent_name}
            for s in trace.spans
        ],
    }


@router.get("/{trace_id}/cost")
async def get_trace_cost_breakdown(trace_id: str, request: Request) -> dict:
    state = get_state(); trace = _get_trace(trace_id, _tenant(request))
    return {"trace_id": trace_id, "total_cost": trace.total_cost,
            "by_model": state.cost_analyzer.get_cost_by_model(trace),
            "by_component": state.cost_analyzer.get_cost_by_component(trace),
            "by_agent": state.cost_analyzer.get_cost_by_agent(trace)}


@router.get("/{trace_id}/waste")
async def get_trace_waste_report(trace_id: str, request: Request) -> dict:
    trace = _get_trace(trace_id, _tenant(request))
    report = get_state().detector_registry.analyze_trace(trace)
    return {"trace_id": trace_id, "total_cost": report.total_cost,
            "total_waste": report.total_waste, "useful_work_cost": report.useful_work_cost,
            "efficiency_score": report.efficiency_score,
            "waste_by_category": {k.value: v for k, v in report.waste_by_category.items()},
            "detections": [{"detection_id": d.detection_id, "category": d.category.value,
                            "confidence": d.confidence.value, "estimated_waste_cost": d.estimated_waste_cost,
                            "savings_pct": d.savings_pct, "title": d.title, "description": d.description,
                            "evidence": d.evidence, "recommendation": d.recommendation,
                            "quality_risk": d.quality_risk.value} for d in report.detections]}
