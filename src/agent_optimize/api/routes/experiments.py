"""V2 Replay experiment API — create, run, and compare configurations.

Experiments validate optimization recommendations against historical workloads
before they are deployed to production. The safe workflow:
detect → recommend → replay → evaluate → compare → canary → monitor → rollout.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent_optimize.api.state import get_state
from agent_optimize.models.recommendations import RecommendationStatus
from agent_optimize.optimization.replay import CandidateConfig

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateExperimentRequest(BaseModel):
    recommendation_id: str | None = None  # Optionally link to a recommendation
    candidate_configs: list[CandidateConfig] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    use_recent_traces: int | None = None  # If set, use N most recent traces


class RunExperimentRequest(BaseModel):
    experiment_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("")
async def create_experiment(body: CreateExperimentRequest) -> dict:
    """Create a new replay experiment.

    Optionally links to a recommendation and auto-generates candidate configs
    from its config comparison.
    """
    state = get_state()

    # Resolve trace IDs
    trace_ids = body.trace_ids
    if body.use_recent_traces and not trace_ids:
        traces = state.warehouse.query_traces(limit=body.use_recent_traces)
        trace_ids = [t.trace_id for t in traces]

    if not trace_ids:
        raise HTTPException(status_code=400, detail="No traces specified and no recent traces found")

    # If linked to a recommendation, auto-generate candidates from its config
    candidates = list(body.candidate_configs)
    if body.recommendation_id and not candidates:
        rec = state.recommendation_store.get(body.recommendation_id)
        if rec and rec.config_comparison:
            candidates.append(CandidateConfig(
                name=rec.config_comparison.proposed_config.name,
                description=f"Auto-generated from recommendation: {rec.title}",
                expected_cost_reduction_pct=rec.impact.cost_reduction_pct,
                expected_quality_impact=rec.impact.quality_delta,
                expected_latency_impact_pct=-rec.impact.latency_reduction_pct,
            ))

    if not candidates:
        raise HTTPException(status_code=400, detail="No candidate configurations provided")

    experiment = state.replay_engine.create_experiment(
        candidate_configs=candidates,
        trace_ids=trace_ids,
    )

    # Link to recommendation if specified
    if body.recommendation_id:
        try:
            state.recommendation_store.link_replay(body.recommendation_id, experiment.experiment_id)
            state.recommendation_store.transition(
                body.recommendation_id,
                RecommendationStatus.REPLAYING,
                actor="system",
                notes=f"Replay experiment {experiment.experiment_id} created",
            )
        except ValueError:
            pass  # Recommendation not found or invalid transition — still create experiment

    return _serialize_experiment(experiment)


@router.post("/{experiment_id}/run")
async def run_experiment(experiment_id: str) -> dict:
    """Run a projection-based replay for an experiment.

    V2 uses cost projection (no actual API calls). V3 will add live replay.
    """
    state = get_state()
    experiment = state.replay_engine.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Fetch the traces
    traces = [
        state.warehouse.get_trace(tid)
        for tid in experiment.trace_ids
    ]
    traces = [t for t in traces if t is not None]

    if not traces:
        raise HTTPException(status_code=400, detail="No traces found for this experiment")

    # Run projection replay
    experiment = state.replay_engine.run_projection_replay(experiment, traces)

    # If linked to a recommendation, update its status
    for rec in state.recommendation_store.query(limit=10000):
        if rec.replay_experiment_id == experiment_id and experiment.recommended_config_id:
            try:
                state.recommendation_store.transition(
                    rec.recommendation_id,
                    RecommendationStatus.VALIDATED,
                    actor="system",
                    notes=(
                        f"Replay validated. Recommended config: {experiment.recommended_config_id}. "
                        f"Confidence: {experiment.confidence_pct}%."
                    ),
                )
                # Update recommendation confidence with replay data
                rec.confidence.replay_confidence = experiment.confidence_pct / 100
                rec.confidence.overall_pct = min(100, rec.confidence.overall_pct + 10)
                rec.evidence.counterfactual_evaluations = len(traces)
            except ValueError:
                pass

    return _serialize_experiment(experiment)


@router.get("")
async def list_experiments() -> dict:
    """List all replay experiments."""
    state = get_state()
    experiments = state.replay_engine.list_experiments()
    return {
        "count": len(experiments),
        "experiments": [_serialize_experiment_summary(e) for e in experiments],
    }


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str) -> dict:
    """Get full experiment detail with results."""
    state = get_state()
    experiment = state.replay_engine.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return _serialize_experiment(experiment)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_experiment(exp) -> dict:
    return {
        "experiment_id": exp.experiment_id,
        "status": exp.status.value,
        "created_at": exp.created_at.isoformat(),
        "trace_count": len(exp.trace_ids),
        "candidate_count": len(exp.candidate_configs),
        "recommended_config_id": exp.recommended_config_id,
        "confidence_pct": exp.confidence_pct,
        "quality_regression_risk": exp.quality_regression_risk,
        "baseline": _serialize_result(exp.baseline_result) if exp.baseline_result else None,
        "candidates": [
            {
                "config": {
                    "config_id": c.config_id,
                    "name": c.name,
                    "description": c.description,
                    "expected_cost_reduction_pct": c.expected_cost_reduction_pct,
                    "expected_quality_impact": c.expected_quality_impact,
                },
                "result": _serialize_result(
                    next((r for r in exp.candidate_results if r.config_id == c.config_id), None)
                ),
            }
            for c in exp.candidate_configs
        ],
    }


def _serialize_experiment_summary(exp) -> dict:
    return {
        "experiment_id": exp.experiment_id,
        "status": exp.status.value,
        "created_at": exp.created_at.isoformat(),
        "trace_count": len(exp.trace_ids),
        "candidate_count": len(exp.candidate_configs),
        "recommended_config_id": exp.recommended_config_id,
        "confidence_pct": exp.confidence_pct,
    }


def _serialize_result(result) -> dict | None:
    if result is None:
        return None
    return {
        "config_id": result.config_id,
        "config_name": result.config_name,
        "quality_score": result.quality_score,
        "cost": result.cost,
        "reliability": result.reliability,
        "traces_replayed": result.traces_replayed,
        "quality_delta": result.quality_delta,
        "cost_delta": result.cost_delta,
        "cost_reduction_pct": result.cost_reduction_pct,
        "latency_delta_pct": result.latency_delta_pct,
    }
