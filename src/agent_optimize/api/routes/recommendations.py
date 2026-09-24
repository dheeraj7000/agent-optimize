"""V2 Recommendation API with request-derived tenant scoping."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from agent_optimize.api.state import get_state
from agent_optimize.models.recommendations import RecommendationPriority, RecommendationStatus
from agent_optimize.models.waste import WasteCategory

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class GenerateRequest(BaseModel):
    tenant_id: str | None = None
    window_days: int = 7


class TransitionRequest(BaseModel):
    actor: str = "user"
    notes: str = ""


def _tenant(request: Request, supplied: str | None = None) -> str | None:
    authenticated_tenant = getattr(request.state, "tenant_id", None)
    if getattr(request.state, "authenticated", False):
        return authenticated_tenant
    return supplied if supplied is not None else authenticated_tenant


def _owned_rec(recommendation_id: str, tenant_id: str | None):
    rec = get_state().recommendation_store.get(recommendation_id)
    if not rec or (tenant_id is not None and rec.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/generate")
async def generate_recommendations(body: GenerateRequest, request: Request) -> dict:
    state = get_state()
    tenant_id = _tenant(request, body.tenant_id)
    traces = state.warehouse.query_traces(tenant_id=tenant_id, limit=10000)
    if not traces:
        return {"count": 0, "recommendations": []}
    report = state.detector_registry.analyze_batch(traces)
    dashboard = state.optimization_engine.generate_opportunities(
        reports=[report], traces=traces, window_days=body.window_days,
    )
    from collections import defaultdict
    detections_by_cat: dict[WasteCategory, list] = defaultdict(list)
    for detection in report.detections:
        detections_by_cat[detection.category].append(detection)
    from agent_optimize.optimization.recommender import generate_recommendations as gen_recs
    recs = gen_recs(
        opportunities=dashboard.opportunities, detections_by_category=detections_by_cat,
        traces=traces, observation_days=body.window_days, tenant_id=tenant_id,
    )
    state.recommendation_store.store_batch(recs)
    return {"count": len(recs), "recommendations": [_serialize_summary(r) for r in recs]}


@router.get("")
async def list_recommendations(
    request: Request,
    tenant_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    min_savings: float | None = None,
    limit: int = Query(default=100, le=500),
) -> dict:
    state = get_state()
    status_enum = RecommendationStatus(status) if status else None
    category_enum = WasteCategory(category) if category else None
    priority_enum = RecommendationPriority(priority) if priority else None
    recs = state.recommendation_store.query(
        tenant_id=_tenant(request, tenant_id), status=status_enum, category=category_enum,
        priority=priority_enum, min_savings=min_savings, limit=limit,
    )
    return {"count": len(recs), "recommendations": [_serialize_summary(r) for r in recs]}


@router.get("/stats")
async def get_recommendation_stats(request: Request, tenant_id: str | None = None) -> dict:
    return get_state().recommendation_store.get_stats(tenant_id=_tenant(request, tenant_id))


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str, request: Request) -> dict:
    return _serialize_full(_owned_rec(recommendation_id, _tenant(request)))


@router.post("/{recommendation_id}/accept")
async def accept_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned_rec(recommendation_id, _tenant(request))
    return _do_transition(recommendation_id, RecommendationStatus.ACCEPTED, body)


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned_rec(recommendation_id, _tenant(request))
    return _do_transition(recommendation_id, RecommendationStatus.REJECTED, body)


@router.post("/{recommendation_id}/deploy")
async def deploy_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned_rec(recommendation_id, _tenant(request))
    return _do_transition(recommendation_id, RecommendationStatus.DEPLOYED, body)


@router.post("/{recommendation_id}/verify")
async def verify_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned_rec(recommendation_id, _tenant(request))
    return _do_transition(recommendation_id, RecommendationStatus.VERIFIED, body)


@router.post("/{recommendation_id}/rollback")
async def rollback_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned_rec(recommendation_id, _tenant(request))
    return _do_transition(recommendation_id, RecommendationStatus.ROLLED_BACK, body)


def _do_transition(rec_id: str, new_status: RecommendationStatus, body: TransitionRequest) -> dict:
    try:
        rec = get_state().recommendation_store.transition(rec_id, new_status, actor=body.actor, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _serialize_full(rec)


def _serialize_summary(rec) -> dict:
    return {
        "recommendation_id": rec.recommendation_id, "status": rec.status.value,
        "priority": rec.priority.value, "category": rec.category.value, "title": rec.title,
        "business_value_score": rec.business_value_score, "monthly_savings": rec.impact.monthly_savings,
        "annual_savings": rec.impact.annual_savings, "confidence": rec.confidence.overall.value,
        "confidence_pct": rec.confidence.overall_pct, "quality_risk": rec.impact.quality_risk.value,
        "engineering_effort": rec.engineering_effort, "created_at": rec.created_at.isoformat(),
    }


def _serialize_full(rec) -> dict:
    return {
        "recommendation_id": rec.recommendation_id, "created_at": rec.created_at.isoformat(),
        "updated_at": rec.updated_at.isoformat(), "status": rec.status.value,
        "status_history": rec.status_history, "category": rec.category.value,
        "opportunity_id": rec.opportunity_id, "priority": rec.priority.value,
        "business_value_score": rec.business_value_score, "engineering_effort": rec.engineering_effort,
        "title": rec.title, "description": rec.description, "action_items": rec.action_items,
        "impact": rec.impact.model_dump(mode="json"),
        "confidence": rec.confidence.model_dump(mode="json"),
        "evidence": rec.evidence.model_dump(mode="json"),
        "config_comparison": rec.config_comparison.model_dump(mode="json") if rec.config_comparison else None,
        "replay_experiment_id": rec.replay_experiment_id, "affected_models": rec.affected_models,
        "affected_tools": rec.affected_tools, "affected_task_classes": rec.affected_task_classes,
        "traces_analyzed": rec.traces_analyzed, "source_detection_ids": rec.source_detection_ids[:5],
    }
