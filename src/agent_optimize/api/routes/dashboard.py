"""Opportunity dashboard API — scoped to the authenticated workspace."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from agent_optimize.api.state import get_state

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _tenant(request: Request, supplied: str | None = None) -> str | None:
    if getattr(request.state, "authenticated", False):
        return request.state.tenant_id
    return supplied


@router.get("/opportunities")
async def get_opportunities(
    request: Request,
    tenant_id: str | None = None,
    window_days: int = Query(default=7, ge=1, le=90),
) -> dict:
    state = get_state()
    tenant = _tenant(request, tenant_id)
    traces = state.warehouse.query_traces(tenant_id=tenant, limit=10000)
    if not traces:
        return {"total_ai_spend_monthly": 0.0, "identified_waste_monthly": 0.0,
                "optimization_potential_pct": 0.0, "potential_optimized_spend": 0.0,
                "estimated_annual_savings": 0.0, "opportunities": [], "traces_analyzed": 0,
                "time_window_days": window_days}
    report = state.detector_registry.analyze_batch(traces)
    dashboard = state.optimization_engine.generate_opportunities(
        reports=[report], traces=traces, window_days=window_days,
    )
    return {
        "computed_at": dashboard.computed_at.isoformat(),
        "total_ai_spend_monthly": dashboard.total_ai_spend_monthly,
        "identified_waste_monthly": dashboard.identified_waste_monthly,
        "optimization_potential_pct": dashboard.optimization_potential_pct,
        "potential_optimized_spend": dashboard.potential_optimized_spend,
        "estimated_annual_savings": dashboard.estimated_annual_savings,
        "traces_analyzed": dashboard.traces_analyzed,
        "time_window_days": dashboard.time_window_days,
        "opportunities": [{
            "opportunity_id": item.opportunity_id, "category": item.category.value,
            "confidence": item.confidence.value, "estimated_monthly_waste": item.estimated_monthly_waste,
            "estimated_annual_savings": item.estimated_annual_savings,
            "affected_traces_pct": item.affected_traces_pct,
            "estimated_quality_impact": item.estimated_quality_impact,
            "title": item.title, "description": item.description,
            "recommendation": item.recommendation, "evidence_summary": item.evidence_summary,
            "total_detections": item.total_detections,
        } for item in dashboard.opportunities],
    }


@router.get("/stats")
async def get_aggregate_stats(
    request: Request,
    tenant_id: str | None = None,
    window_hours: int = Query(default=168, ge=1, le=2160),
) -> dict:
    return get_state().warehouse.get_aggregate_stats(
        tenant_id=_tenant(request, tenant_id), window_hours=window_hours,
    )


@router.get("/runs")
async def get_run_summaries(
    request: Request,
    tenant_id: str | None = None,
    limit: int = Query(default=100, le=1000),
) -> dict:
    summaries = get_state().warehouse.get_run_summaries(
        tenant_id=_tenant(request, tenant_id), limit=limit,
    )
    return {"count": len(summaries), "runs": [summary.model_dump() for summary in summaries]}


@router.get("/models")
async def get_models(request: Request, tenant_id: str | None = None) -> dict:
    state = get_state()
    traces = state.warehouse.query_traces(tenant_id=_tenant(request, tenant_id), limit=10000)
    models = sorted({model for trace in traces for model in trace.unique_models})
    return {"models": models, "catalog_models": state.cost_catalog.list_models()}


@router.get("/tools")
async def get_tools(request: Request, tenant_id: str | None = None) -> dict:
    traces = get_state().warehouse.query_traces(tenant_id=_tenant(request, tenant_id), limit=10000)
    return {"tools": sorted({tool for trace in traces for tool in trace.unique_tools})}
