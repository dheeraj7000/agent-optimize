"""V2 recommendation API scoped to authenticated workspaces."""

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
    if getattr(request.state, "authenticated", False):
        return request.state.tenant_id
    return supplied if supplied is not None else getattr(request.state, "tenant_id", None)


def _owned(recommendation_id: str, tenant_id: str | None):
    recommendation = get_state().recommendation_store.get(recommendation_id)
    if not recommendation or (tenant_id is not None and recommendation.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


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
    detections_by_category: dict[WasteCategory, list] = defaultdict(list)
    for detection in report.detections:
        detections_by_category[detection.category].append(detection)
    from agent_optimize.optimization.recommender import generate_recommendations
    recommendations = generate_recommendations(
        opportunities=dashboard.opportunities, detections_by_category=detections_by_category,
        traces=traces, observation_days=body.window_days, tenant_id=tenant_id,
    )
    state.recommendation_store.store_batch(recommendations)
    return {"count": len(recommendations), "recommendations": [_serialize_summary(item) for item in recommendations]}


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
    status_filter = RecommendationStatus(status) if status else None
    category_filter = WasteCategory(category) if category else None
    priority_filter = RecommendationPriority(priority) if priority else None
    recommendations = get_state().recommendation_store.query(
        tenant_id=_tenant(request, tenant_id), status=status_filter, category=category_filter,
        priority=priority_filter, min_savings=min_savings, limit=limit,
    )
    return {"count": len(recommendations), "recommendations": [_serialize_summary(item) for item in recommendations]}


@router.get("/stats")
async def get_recommendation_stats(request: Request, tenant_id: str | None = None) -> dict:
    return get_state().recommendation_store.get_stats(tenant_id=_tenant(request, tenant_id))


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str, request: Request) -> dict:
    return _serialize_full(_owned(recommendation_id, _tenant(request)))


@router.post("/{recommendation_id}/accept")
async def accept_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned(recommendation_id, _tenant(request))
    return _transition(recommendation_id, RecommendationStatus.ACCEPTED, body)


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned(recommendation_id, _tenant(request))
    return _transition(recommendation_id, RecommendationStatus.REJECTED, body)


@router.post("/{recommendation_id}/deploy")
async def deploy_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned(recommendation_id, _tenant(request))
    return _transition(recommendation_id, RecommendationStatus.DEPLOYED, body)


@router.post("/{recommendation_id}/verify")
async def verify_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned(recommendation_id, _tenant(request))
    return _transition(recommendation_id, RecommendationStatus.VERIFIED, body)


@router.post("/{recommendation_id}/rollback")
async def rollback_recommendation(recommendation_id: str, body: TransitionRequest, request: Request) -> dict:
    _owned(recommendation_id, _tenant(request))
    return _transition(recommendation_id, RecommendationStatus.ROLLED_BACK, body)


def _transition(recommendation_id: str, status: RecommendationStatus, body: TransitionRequest) -> dict:
    try:
        result = get_state().recommendation_store.transition(
            recommendation_id, status, actor=body.actor, notes=body.notes,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _serialize_full(result)


def _serialize_summary(item) -> dict:
    return {"recommendation_id": item.recommendation_id, "status": item.status.value,
            "priority": item.priority.value, "category": item.category.value, "title": item.title,
            "business_value_score": item.business_value_score, "monthly_savings": item.impact.monthly_savings,
            "annual_savings": item.impact.annual_savings, "confidence": item.confidence.overall.value,
            "confidence_pct": item.confidence.overall_pct, "quality_risk": item.impact.quality_risk.value,
            "engineering_effort": item.engineering_effort, "created_at": item.created_at.isoformat()}


def _serialize_full(item) -> dict:
    return {"recommendation_id": item.recommendation_id, "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(), "status": item.status.value,
            "status_history": item.status_history, "category": item.category.value,
            "opportunity_id": item.opportunity_id, "priority": item.priority.value,
            "business_value_score": item.business_value_score, "engineering_effort": item.engineering_effort,
            "title": item.title, "description": item.description, "action_items": item.action_items,
            "impact": item.impact.model_dump(mode="json"), "confidence": item.confidence.model_dump(mode="json"),
            "evidence": item.evidence.model_dump(mode="json"),
            "config_comparison": item.config_comparison.model_dump(mode="json") if item.config_comparison else None,
            "replay_experiment_id": item.replay_experiment_id, "affected_models": item.affected_models,
            "affected_tools": item.affected_tools, "affected_task_classes": item.affected_task_classes,
            "traces_analyzed": item.traces_analyzed, "source_detection_ids": item.source_detection_ids[:5]}
