"""V2 Recommendation API — lifecycle management, prioritization, and drill-down.

Teams can prioritize fixes by business value: each recommendation includes
expected savings, quality impact, confidence, evidence, and a proposed configuration.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agent_optimize.api.state import get_state
from agent_optimize.models.recommendations import RecommendationPriority, RecommendationStatus
from agent_optimize.models.waste import WasteCategory

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class GenerateRequest(BaseModel):
    tenant_id: str | None = None
    window_days: int = 7


class TransitionRequest(BaseModel):
    actor: str = "user"
    notes: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate_recommendations(body: GenerateRequest) -> dict:
    """Generate recommendations from current trace data.

    Runs the full pipeline: query traces → detect waste → generate opportunities →
    produce recommendations with confidence, evidence, impact, and config comparisons.
    """
    state = get_state()

    traces = state.warehouse.query_traces(tenant_id=body.tenant_id, limit=10000)
    if not traces:
        return {"count": 0, "recommendations": []}

    # Run waste detection
    report = state.detector_registry.analyze_batch(traces)

    # Generate V1 opportunities
    dashboard = state.optimization_engine.generate_opportunities(
        reports=[report], traces=traces, window_days=body.window_days,
    )

    # Group detections by category for the recommender
    from collections import defaultdict

    detections_by_cat: dict[WasteCategory, list] = defaultdict(list)
    for d in report.detections:
        detections_by_cat[d.category].append(d)

    # Generate V2 recommendations
    from agent_optimize.optimization.recommender import generate_recommendations as gen_recs

    recs = gen_recs(
        opportunities=dashboard.opportunities,
        detections_by_category=detections_by_cat,
        traces=traces,
        observation_days=body.window_days,
        tenant_id=body.tenant_id,
    )

    # Store them
    state.recommendation_store.store_batch(recs)

    return {
        "count": len(recs),
        "recommendations": [_serialize_summary(r) for r in recs],
    }


@router.get("")
async def list_recommendations(
    tenant_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    min_savings: float | None = None,
    limit: int = Query(default=100, le=500),
) -> dict:
    """List recommendations with optional filters, sorted by business value."""
    state = get_state()

    status_enum = RecommendationStatus(status) if status else None
    category_enum = WasteCategory(category) if category else None
    priority_enum = RecommendationPriority(priority) if priority else None

    recs = state.recommendation_store.query(
        tenant_id=tenant_id,
        status=status_enum,
        category=category_enum,
        priority=priority_enum,
        min_savings=min_savings,
        limit=limit,
    )

    return {
        "count": len(recs),
        "recommendations": [_serialize_summary(r) for r in recs],
    }


@router.get("/stats")
async def get_recommendation_stats(tenant_id: str | None = None) -> dict:
    """Aggregate recommendation statistics — how many in each state, total savings."""
    state = get_state()
    return state.recommendation_store.get_stats(tenant_id=tenant_id)


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str) -> dict:
    """Get full recommendation detail with impact, evidence, confidence, and config."""
    state = get_state()
    rec = state.recommendation_store.get(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return _serialize_full(rec)


@router.post("/{recommendation_id}/accept")
async def accept_recommendation(recommendation_id: str, body: TransitionRequest) -> dict:
    """Accept a recommendation — team agrees to pursue this optimization."""
    return _do_transition(recommendation_id, RecommendationStatus.ACCEPTED, body)


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(recommendation_id: str, body: TransitionRequest) -> dict:
    """Reject a recommendation — team decided not to pursue."""
    return _do_transition(recommendation_id, RecommendationStatus.REJECTED, body)


@router.post("/{recommendation_id}/deploy")
async def deploy_recommendation(recommendation_id: str, body: TransitionRequest) -> dict:
    """Mark a recommendation as deployed to production."""
    return _do_transition(recommendation_id, RecommendationStatus.DEPLOYED, body)


@router.post("/{recommendation_id}/verify")
async def verify_recommendation(recommendation_id: str, body: TransitionRequest) -> dict:
    """Mark a recommendation as verified — post-deploy monitoring confirms savings."""
    return _do_transition(recommendation_id, RecommendationStatus.VERIFIED, body)


@router.post("/{recommendation_id}/rollback")
async def rollback_recommendation(recommendation_id: str, body: TransitionRequest) -> dict:
    """Roll back a deployed recommendation due to regression."""
    return _do_transition(recommendation_id, RecommendationStatus.ROLLED_BACK, body)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _do_transition(rec_id: str, new_status: RecommendationStatus, body: TransitionRequest) -> dict:
    state = get_state()
    try:
        rec = state.recommendation_store.transition(
            rec_id, new_status, actor=body.actor, notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _serialize_full(rec)


def _serialize_summary(rec) -> dict:
    return {
        "recommendation_id": rec.recommendation_id,
        "status": rec.status.value,
        "priority": rec.priority.value,
        "category": rec.category.value,
        "title": rec.title,
        "business_value_score": rec.business_value_score,
        "monthly_savings": rec.impact.monthly_savings,
        "annual_savings": rec.impact.annual_savings,
        "confidence": rec.confidence.overall.value,
        "confidence_pct": rec.confidence.overall_pct,
        "quality_risk": rec.impact.quality_risk.value,
        "engineering_effort": rec.engineering_effort,
        "created_at": rec.created_at.isoformat(),
    }


def _serialize_full(rec) -> dict:
    return {
        "recommendation_id": rec.recommendation_id,
        "created_at": rec.created_at.isoformat(),
        "updated_at": rec.updated_at.isoformat(),
        "status": rec.status.value,
        "status_history": rec.status_history,
        "category": rec.category.value,
        "opportunity_id": rec.opportunity_id,
        "priority": rec.priority.value,
        "business_value_score": rec.business_value_score,
        "engineering_effort": rec.engineering_effort,
        "title": rec.title,
        "description": rec.description,
        "action_items": rec.action_items,
        "impact": {
            "current_monthly_cost": rec.impact.current_monthly_cost,
            "projected_monthly_cost": rec.impact.projected_monthly_cost,
            "monthly_savings": rec.impact.monthly_savings,
            "annual_savings": rec.impact.annual_savings,
            "cost_reduction_pct": rec.impact.cost_reduction_pct,
            "current_quality": rec.impact.current_quality,
            "projected_quality": rec.impact.projected_quality,
            "quality_delta": rec.impact.quality_delta,
            "quality_risk": rec.impact.quality_risk.value,
            "current_p50_ms": rec.impact.current_p50_ms,
            "current_p95_ms": rec.impact.current_p95_ms,
            "projected_p50_ms": rec.impact.projected_p50_ms,
            "projected_p95_ms": rec.impact.projected_p95_ms,
            "latency_reduction_pct": rec.impact.latency_reduction_pct,
            "current_reliability": rec.impact.current_reliability,
            "projected_reliability": rec.impact.projected_reliability,
            "risk_level": rec.impact.risk_level.value,
            "risk_description": rec.impact.risk_description,
        },
        "confidence": {
            "overall": rec.confidence.overall.value,
            "overall_pct": rec.confidence.overall_pct,
            "sample_size_score": rec.confidence.sample_size_score,
            "workload_coverage": rec.confidence.workload_coverage,
            "variance_score": rec.confidence.variance_score,
            "evaluator_agreement": rec.confidence.evaluator_agreement,
            "replay_confidence": rec.confidence.replay_confidence,
            "model_drift_risk": rec.confidence.model_drift_risk,
            "workload_drift_risk": rec.confidence.workload_drift_risk,
        },
        "evidence": {
            "summary": rec.evidence.summary,
            "traces_analyzed": rec.evidence.traces_analyzed,
            "counterfactual_evaluations": rec.evidence.counterfactual_evaluations,
            "observation_window_days": rec.evidence.observation_window_days,
            "items": [
                {
                    "kind": item.kind,
                    "description": item.description,
                    "data": item.data,
                    "source_trace_ids": item.source_trace_ids,
                }
                for item in rec.evidence.items
            ],
        },
        "config_comparison": {
            "changes": rec.config_comparison.changes,
            "current": {
                "name": rec.config_comparison.current_config.name,
                "model_assignments": rec.config_comparison.current_config.model_assignments,
                "context_strategy": rec.config_comparison.current_config.context_strategy,
                "cache_strategy": rec.config_comparison.current_config.cache_strategy,
                "verification_enabled": rec.config_comparison.current_config.verification_enabled,
                "parallelization_enabled": rec.config_comparison.current_config.parallelization_enabled,
            },
            "proposed": {
                "name": rec.config_comparison.proposed_config.name,
                "model_assignments": rec.config_comparison.proposed_config.model_assignments,
                "context_strategy": rec.config_comparison.proposed_config.context_strategy,
                "cache_strategy": rec.config_comparison.proposed_config.cache_strategy,
                "verification_enabled": rec.config_comparison.proposed_config.verification_enabled,
                "parallelization_enabled": rec.config_comparison.proposed_config.parallelization_enabled,
            },
        }
        if rec.config_comparison
        else None,
        "replay_experiment_id": rec.replay_experiment_id,
        "affected_models": rec.affected_models,
        "affected_tools": rec.affected_tools,
        "affected_task_classes": rec.affected_task_classes,
        "traces_analyzed": rec.traces_analyzed,
        "source_detection_ids": rec.source_detection_ids[:5],
    }
