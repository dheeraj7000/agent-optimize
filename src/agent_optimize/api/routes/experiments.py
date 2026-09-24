"""Replay experiment APIs; tenant ownership is checked before any trace access."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent_optimize.api.state import get_state
from agent_optimize.models.recommendations import RecommendationStatus
from agent_optimize.optimization.replay import CandidateConfig

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class CreateExperimentRequest(BaseModel):
    recommendation_id: str | None = None
    candidate_configs: list[CandidateConfig] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    use_recent_traces: int | None = None


def _tenant(request: Request) -> str | None:
    return request.state.tenant_id if getattr(request.state, "authenticated", False) else None


def _owned_recommendation(recommendation_id: str, tenant_id: str | None):
    rec = get_state().recommendation_store.get(recommendation_id)
    if not rec or (tenant_id is not None and rec.tenant_id != tenant_id):
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


def _owned_experiment(experiment_id: str, tenant_id: str | None):
    state = get_state()
    experiment = state.replay_engine.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    traces = [state.warehouse.get_trace(trace_id) for trace_id in experiment.trace_ids]
    if tenant_id is not None and (not traces or any(trace is None or trace.tenant_id != tenant_id for trace in traces)):
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment


@router.post("")
async def create_experiment(body: CreateExperimentRequest, request: Request) -> dict:
    state = get_state()
    tenant_id = _tenant(request)
    trace_ids = list(body.trace_ids)
    if body.use_recent_traces and not trace_ids:
        traces = state.warehouse.query_traces(tenant_id=tenant_id, limit=body.use_recent_traces)
        trace_ids = [trace.trace_id for trace in traces]
    if not trace_ids:
        raise HTTPException(status_code=400, detail="No traces specified and no recent traces found")

    selected_traces = [state.warehouse.get_trace(trace_id) for trace_id in trace_ids]
    if any(trace is None for trace in selected_traces):
        raise HTTPException(status_code=404, detail="One or more traces were not found")
    if tenant_id is not None and any(trace.tenant_id != tenant_id for trace in selected_traces):
        raise HTTPException(status_code=404, detail="One or more traces were not found")

    candidates = list(body.candidate_configs)
    recommendation = None
    if body.recommendation_id:
        recommendation = _owned_recommendation(body.recommendation_id, tenant_id)
    if recommendation and not candidates and recommendation.config_comparison:
        candidates.append(CandidateConfig(
            name=recommendation.config_comparison.proposed_config.name,
            description=f"Auto-generated from recommendation: {recommendation.title}",
            expected_cost_reduction_pct=recommendation.impact.cost_reduction_pct,
            expected_quality_impact=recommendation.impact.quality_delta,
            expected_latency_impact_pct=-recommendation.impact.latency_reduction_pct,
        ))
    if not candidates:
        raise HTTPException(status_code=400, detail="No candidate configurations provided")
    experiment = state.replay_engine.create_experiment(candidate_configs=candidates, trace_ids=trace_ids)
    if recommendation:
        try:
            state.recommendation_store.link_replay(recommendation.recommendation_id, experiment.experiment_id)
            state.recommendation_store.transition(recommendation.recommendation_id,
                RecommendationStatus.REPLAYING, actor="system",
                notes=f"Replay experiment {experiment.experiment_id} created")
        except ValueError:
            pass
    return _serialize_experiment(experiment)


@router.post("/{experiment_id}/run")
async def run_experiment(experiment_id: str, request: Request) -> dict:
    state = get_state()
    experiment = _owned_experiment(experiment_id, _tenant(request))
    traces = [state.warehouse.get_trace(trace_id) for trace_id in experiment.trace_ids]
    traces = [trace for trace in traces if trace is not None]
    if not traces:
        raise HTTPException(status_code=400, detail="No traces found for this experiment")
    experiment = state.replay_engine.run_projection_replay(experiment, traces)
    for recommendation in state.recommendation_store.query(tenant_id=_tenant(request), limit=10000):
        if recommendation.replay_experiment_id == experiment_id and experiment.recommended_config_id:
            try:
                state.recommendation_store.transition(
                    recommendation.recommendation_id, RecommendationStatus.VALIDATED, actor="system",
                    notes=(f"Replay validated. Recommended config: {experiment.recommended_config_id}. "
                           f"Confidence: {experiment.confidence_pct}%.")
                )
                recommendation.confidence.replay_confidence = experiment.confidence_pct / 100
                recommendation.confidence.overall_pct = min(100, recommendation.confidence.overall_pct + 10)
                recommendation.evidence.counterfactual_evaluations = len(traces)
            except ValueError:
                pass
    return _serialize_experiment(experiment)


@router.get("")
async def list_experiments(request: Request) -> dict:
    state = get_state()
    tenant_id = _tenant(request)
    experiments = state.replay_engine.list_experiments()
    if tenant_id is not None:
        experiments = [exp for exp in experiments if _experiment_owned_by(state, exp, tenant_id)]
    return {"count": len(experiments), "experiments": [_serialize_experiment_summary(exp) for exp in experiments]}


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str, request: Request) -> dict:
    return _serialize_experiment(_owned_experiment(experiment_id, _tenant(request)))


def _experiment_owned_by(state, experiment, tenant_id: str) -> bool:
    traces = [state.warehouse.get_trace(trace_id) for trace_id in experiment.trace_ids]
    return bool(traces) and all(trace is not None and trace.tenant_id == tenant_id for trace in traces)


def _serialize_experiment(experiment) -> dict:
    return {"experiment_id": experiment.experiment_id, "status": experiment.status.value,
            "created_at": experiment.created_at.isoformat(), "trace_count": len(experiment.trace_ids),
            "candidate_count": len(experiment.candidate_configs),
            "recommended_config_id": experiment.recommended_config_id,
            "confidence_pct": experiment.confidence_pct,
            "quality_regression_risk": experiment.quality_regression_risk,
            "baseline": _serialize_result(experiment.baseline_result) if experiment.baseline_result else None,
            "candidates": [{"config": {"config_id": candidate.config_id, "name": candidate.name,
                "description": candidate.description,
                "expected_cost_reduction_pct": candidate.expected_cost_reduction_pct,
                "expected_quality_impact": candidate.expected_quality_impact},
                "result": _serialize_result(next((result for result in experiment.candidate_results
                    if result.config_id == candidate.config_id), None))}
                for candidate in experiment.candidate_configs]}


def _serialize_experiment_summary(experiment) -> dict:
    return {"experiment_id": experiment.experiment_id, "status": experiment.status.value,
            "created_at": experiment.created_at.isoformat(), "trace_count": len(experiment.trace_ids),
            "candidate_count": len(experiment.candidate_configs),
            "recommended_config_id": experiment.recommended_config_id,
            "confidence_pct": experiment.confidence_pct}


def _serialize_result(result) -> dict | None:
    if result is None:
        return None
    return {"config_id": result.config_id, "config_name": result.config_name,
            "quality_score": result.quality_score, "cost": result.cost,
            "reliability": result.reliability, "traces_replayed": result.traces_replayed,
            "quality_delta": result.quality_delta, "cost_delta": result.cost_delta,
            "cost_reduction_pct": result.cost_reduction_pct, "latency_delta_pct": result.latency_delta_pct}
