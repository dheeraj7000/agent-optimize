"""V3 Validation API — savings proofs, evaluators, and canary monitoring.

Savings claims are validated before production. The safe workflow:
detect → recommend → replay → evaluate → compare → canary → monitor → rollout.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agent_optimize.api.state import get_state
from agent_optimize.models.proof import CanaryThresholds

router = APIRouter(prefix="/api/validation", tags=["validation"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ValidateReplayRequest(BaseModel):
    recommendation_id: str
    experiment_id: str
    observation_days: int = 7
    claimed_monthly_savings: float = 0.0


class CreateCanaryRequest(BaseModel):
    recommendation_id: str
    experiment_id: str | None = None
    traffic_pct: float = 10.0
    thresholds: CanaryThresholds = Field(default_factory=CanaryThresholds)


class CanaryCheckpointRequest(BaseModel):
    use_recent_traces: int = 100  # How many recent traces to use for the checkpoint


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------


@router.get("/evaluators")
async def list_evaluators() -> dict:
    """List all registered quality evaluators."""
    state = get_state()
    return {"evaluators": state.evaluator_registry.list_evaluators()}


# ---------------------------------------------------------------------------
# Savings proofs
# ---------------------------------------------------------------------------


@router.post("/prove")
async def validate_savings(body: ValidateReplayRequest) -> dict:
    """Validate savings from a replay experiment.

    Runs all quality evaluators against baseline and candidate traces,
    computes actual savings vs. claimed, and produces a SavingsProof.
    """
    state = get_state()

    # Get the experiment
    experiment = state.replay_engine.get_experiment(body.experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get traces
    baseline_traces = [
        state.warehouse.get_trace(tid)
        for tid in experiment.trace_ids
    ]
    baseline_traces = [t for t in baseline_traces if t is not None]

    if not baseline_traces:
        raise HTTPException(status_code=400, detail="No baseline traces found")

    # Get costs from experiment results
    baseline_cost = experiment.baseline_result.cost if experiment.baseline_result else 0.0
    candidate_cost = 0.0
    if experiment.recommended_config_id and experiment.candidate_results:
        for r in experiment.candidate_results:
            if r.config_id == experiment.recommended_config_id:
                candidate_cost = r.cost
                break

    # Validate
    proof = state.savings_validator.validate_from_replay(
        recommendation_id=body.recommendation_id,
        experiment_id=body.experiment_id,
        baseline_traces=baseline_traces,
        baseline_cost=baseline_cost,
        candidate_cost=candidate_cost,
        claimed_monthly_savings=body.claimed_monthly_savings,
        observation_days=body.observation_days,
    )

    # Store proof
    state.proof_store[proof.proof_id] = proof

    return _serialize_proof(proof)


@router.get("/proofs")
async def list_proofs(
    recommendation_id: str | None = None,
    limit: int = Query(default=50, le=200),
) -> dict:
    """List savings proofs."""
    state = get_state()
    proofs = list(state.proof_store.values())

    if recommendation_id:
        proofs = [p for p in proofs if p.recommendation_id == recommendation_id]

    proofs.sort(key=lambda p: p.created_at, reverse=True)
    return {
        "count": len(proofs[:limit]),
        "proofs": [_serialize_proof_summary(p) for p in proofs[:limit]],
    }


@router.get("/proofs/{proof_id}")
async def get_proof(proof_id: str) -> dict:
    """Get full savings proof detail."""
    state = get_state()
    proof = state.proof_store.get(proof_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Proof not found")
    return _serialize_proof(proof)


# ---------------------------------------------------------------------------
# Canary monitoring
# ---------------------------------------------------------------------------


@router.post("/canaries")
async def create_canary(body: CreateCanaryRequest) -> dict:
    """Create a canary deployment for a recommendation."""
    state = get_state()

    canary = state.canary_manager.create_canary(
        recommendation_id=body.recommendation_id,
        experiment_id=body.experiment_id,
        thresholds=body.thresholds,
        traffic_pct=body.traffic_pct,
    )

    return _serialize_canary(canary)


@router.post("/canaries/{canary_id}/start")
async def start_canary(canary_id: str) -> dict:
    """Start canary monitoring, capturing baseline metrics."""
    state = get_state()

    # Use recent traces as baseline
    baseline_traces = state.warehouse.query_traces(limit=500)
    if not baseline_traces:
        raise HTTPException(status_code=400, detail="No baseline traces available")

    try:
        canary = state.canary_manager.start_canary(canary_id, baseline_traces)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return _serialize_canary(canary)


@router.post("/canaries/{canary_id}/checkpoint")
async def add_checkpoint(canary_id: str, body: CanaryCheckpointRequest) -> dict:
    """Add a monitoring checkpoint to a running canary.

    Compares current metrics against baseline and checks thresholds.
    """
    state = get_state()

    canary = state.canary_manager.get_canary(canary_id)
    if not canary:
        raise HTTPException(status_code=404, detail="Canary not found")

    # Get recent traces for the checkpoint
    canary_traces = state.warehouse.query_traces(limit=body.use_recent_traces)
    baseline_traces = state.warehouse.query_traces(limit=body.use_recent_traces)

    if not canary_traces:
        raise HTTPException(status_code=400, detail="No traces available for checkpoint")

    try:
        checkpoint = state.canary_manager.add_checkpoint(
            canary_id, canary_traces, baseline_traces,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return {
        "canary_id": canary_id,
        "canary_status": canary.status.value,
        "checkpoint": _serialize_checkpoint(checkpoint),
    }


@router.post("/canaries/{canary_id}/complete")
async def complete_canary(canary_id: str) -> dict:
    """Complete a canary — finalize verdict and summary."""
    state = get_state()
    try:
        canary = state.canary_manager.complete_canary(canary_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _serialize_canary(canary)


@router.get("/canaries")
async def list_canaries() -> dict:
    """List all canary deployments."""
    state = get_state()
    canaries = state.canary_manager.list_canaries()
    return {
        "count": len(canaries),
        "canaries": [_serialize_canary_summary(c) for c in canaries],
    }


@router.get("/canaries/{canary_id}")
async def get_canary(canary_id: str) -> dict:
    """Get full canary detail with all checkpoints."""
    state = get_state()
    canary = state.canary_manager.get_canary(canary_id)
    if not canary:
        raise HTTPException(status_code=404, detail="Canary not found")
    return _serialize_canary(canary)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_proof(proof) -> dict:
    return {
        "proof_id": proof.proof_id,
        "recommendation_id": proof.recommendation_id,
        "experiment_id": proof.experiment_id,
        "status": proof.status.value,
        "created_at": proof.created_at.isoformat(),
        "validated_at": proof.validated_at.isoformat() if proof.validated_at else None,
        "before": proof.before.model_dump(),
        "after": proof.after.model_dump(),
        "actual_savings_pct": proof.actual_savings_pct,
        "actual_monthly_savings": proof.actual_monthly_savings,
        "claimed_monthly_savings": proof.claimed_monthly_savings,
        "savings_accuracy_pct": proof.savings_accuracy_pct,
        "quality_preserved": proof.quality_preserved,
        "quality_delta": proof.quality_delta,
        "latency_delta_pct": proof.latency_delta_pct,
        "eval_verdict": proof.eval_verdict.value,
        "eval_results": [
            {
                "evaluator": r.evaluator_name,
                "verdict": r.verdict.value,
                "score": r.score,
                "message": r.message,
            }
            for r in (proof.eval_suite.results if proof.eval_suite else [])
        ],
        "confidence": proof.confidence.value,
        "confidence_pct": proof.confidence_pct,
        "observation_window_days": proof.observation_window_days,
        "traces_analyzed": proof.traces_analyzed,
        "summary": proof.summary,
    }


def _serialize_proof_summary(proof) -> dict:
    return {
        "proof_id": proof.proof_id,
        "recommendation_id": proof.recommendation_id,
        "status": proof.status.value,
        "actual_savings_pct": proof.actual_savings_pct,
        "quality_preserved": proof.quality_preserved,
        "eval_verdict": proof.eval_verdict.value,
        "confidence": proof.confidence.value,
        "summary": proof.summary,
    }


def _serialize_canary(canary) -> dict:
    return {
        "canary_id": canary.canary_id,
        "recommendation_id": canary.recommendation_id,
        "experiment_id": canary.experiment_id,
        "status": canary.status.value,
        "created_at": canary.created_at.isoformat(),
        "started_at": canary.started_at.isoformat() if canary.started_at else None,
        "completed_at": canary.completed_at.isoformat() if canary.completed_at else None,
        "traffic_pct": canary.traffic_pct,
        "thresholds": canary.thresholds.model_dump(),
        "baseline_metrics": canary.baseline_metrics.model_dump(),
        "checkpoints": [_serialize_checkpoint(c) for c in canary.checkpoints],
        "checkpoint_count": len(canary.checkpoints),
        "final_verdict": canary.final_verdict.value,
        "final_summary": canary.final_summary,
    }


def _serialize_canary_summary(canary) -> dict:
    return {
        "canary_id": canary.canary_id,
        "recommendation_id": canary.recommendation_id,
        "status": canary.status.value,
        "traffic_pct": canary.traffic_pct,
        "checkpoint_count": len(canary.checkpoints),
        "final_verdict": canary.final_verdict.value,
    }


def _serialize_checkpoint(cp) -> dict:
    return {
        "checkpoint_id": cp.checkpoint_id,
        "checked_at": cp.checked_at.isoformat(),
        "healthy": cp.healthy,
        "cost_savings_pct": cp.cost_savings_pct,
        "success_rate_delta": cp.success_rate_delta,
        "latency_delta_pct": cp.latency_delta_pct,
        "error_rate_delta": cp.error_rate_delta,
        "issues": cp.issues,
        "metrics": cp.metrics.model_dump(),
    }
