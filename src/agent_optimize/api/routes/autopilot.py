"""V4 Autopilot API — policies, routing, verification, recovery, and decisions.

Automated changes operate inside customer-defined quality/SLA/risk constraints.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from agent_optimize.api.state import get_state
from agent_optimize.autopilot.policy import AutopilotMode, ExecutionPolicy, PolicyConstraints, PolicyDecision
from agent_optimize.autopilot.recovery import FailureType, RecoveryRule
from agent_optimize.autopilot.router import RoutingDecision

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SetModeRequest(BaseModel):
    mode: AutopilotMode


class SetConstraintsRequest(BaseModel):
    constraints: PolicyConstraints


class RouteRequest(BaseModel):
    original_model: str = ""
    input_tokens: int = 0
    output_tokens_estimate: int = 0
    task_class: str | None = None
    has_side_effects: bool = False
    customer_facing: bool = False


class VerifyRequest(BaseModel):
    risk_score: float = 0.0
    model_confidence: float = 1.0
    task_class: str | None = None
    has_side_effects: bool = False
    customer_facing: bool = False


class RecoverRequest(BaseModel):
    failure_type: FailureType = FailureType.UNKNOWN
    failed_tool: str = ""
    failed_model: str = ""
    error_message: str = ""
    retry_count: int = 0


class SetThresholdsRequest(BaseModel):
    risk_threshold: float | None = None
    confidence_threshold: float | None = None


class SetRoutingTableRequest(BaseModel):
    routing_table: dict[str, str]  # complexity_tier -> model


class ApproveDecisionRequest(BaseModel):
    actor: str = "user"


# ---------------------------------------------------------------------------
# Autopilot status and mode
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_autopilot_status() -> dict:
    """Get current autopilot status, mode, and stats."""
    state = get_state()
    status = state.policy_engine.status
    return {
        "mode": status.mode.value,
        "enabled_at": status.enabled_at.isoformat() if status.enabled_at else None,
        "decisions_made": status.decisions_made,
        "decisions_applied": status.decisions_applied,
        "decisions_rejected": status.decisions_rejected,
        "estimated_monthly_savings": status.estimated_monthly_savings,
        "healthy": status.healthy,
        "constraints": status.constraints.model_dump(),
        "stats": {
            "router": state.model_router.get_routing_stats(),
            "verifier": state.adaptive_verifier.get_stats(),
            "recovery": state.recovery_selector.get_stats(),
            "engine": state.policy_engine.get_stats(),
        },
    }


@router.post("/mode")
async def set_mode(body: SetModeRequest) -> dict:
    """Set autopilot operating mode: off, suggest, supervised, or autonomous."""
    state = get_state()
    status = state.policy_engine.set_mode(body.mode)
    return {"mode": status.mode.value, "enabled_at": status.enabled_at.isoformat() if status.enabled_at else None}


@router.post("/constraints")
async def set_constraints(body: SetConstraintsRequest) -> dict:
    """Set customer-defined quality/latency/cost/reliability/risk constraints."""
    state = get_state()
    status = state.policy_engine.set_constraints(body.constraints)
    return {"constraints": status.constraints.model_dump()}


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


@router.post("/policies")
async def create_policy(policy: ExecutionPolicy) -> dict:
    """Create a new execution policy."""
    state = get_state()
    created = state.policy_engine.create_policy(policy)
    return _serialize_policy(created)


@router.get("/policies")
async def list_policies(active_only: bool = False) -> dict:
    """List execution policies."""
    state = get_state()
    policies = state.policy_engine.list_policies(active_only=active_only)
    return {"count": len(policies), "policies": [_serialize_policy(p) for p in policies]}


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str) -> dict:
    """Get a specific execution policy."""
    state = get_state()
    policy = state.policy_engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _serialize_policy(policy)


@router.post("/policies/{policy_id}/activate")
async def activate_policy(policy_id: str) -> dict:
    """Activate an execution policy."""
    state = get_state()
    try:
        policy = state.policy_engine.activate_policy(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _serialize_policy(policy)


@router.post("/policies/{policy_id}/deactivate")
async def deactivate_policy(policy_id: str) -> dict:
    """Deactivate an execution policy."""
    state = get_state()
    try:
        policy = state.policy_engine.deactivate_policy(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _serialize_policy(policy)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


@router.post("/route")
async def route_request(body: RouteRequest) -> dict:
    """Get a model routing decision for a request."""
    state = get_state()
    if not state.policy_engine.status.constraints.allow_model_routing:
        raise HTTPException(status_code=403, detail="Model routing not allowed by constraints")

    decision = state.model_router.route(
        original_model=body.original_model,
        input_tokens=body.input_tokens,
        output_tokens_estimate=body.output_tokens_estimate,
        task_class=body.task_class,
        has_side_effects=body.has_side_effects,
        customer_facing=body.customer_facing,
    )

    # Record as policy decision
    pd = PolicyDecision(
        action_type="model_route",
        action_description=f"Route from {decision.original_model} to {decision.selected_model}",
        action_params={"selected_model": decision.selected_model, "complexity": decision.complexity.value},
        reason=decision.reason,
        expected_savings=decision.estimated_cost_savings,
        expected_quality_impact=decision.estimated_quality_delta,
    )
    state.policy_engine.make_decision(pd)

    return _serialize_routing(decision)


@router.post("/route/config")
async def set_routing_config(body: SetRoutingTableRequest) -> dict:
    """Update the model routing table."""
    state = get_state()
    state.model_router.set_routing_table(body.routing_table)
    return {"routing_table": state.model_router.routing_table}


@router.get("/route/stats")
async def get_routing_stats() -> dict:
    """Get routing statistics."""
    state = get_state()
    return state.model_router.get_routing_stats()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


@router.post("/verify")
async def verify_request(body: VerifyRequest) -> dict:
    """Get an adaptive verification decision for a request."""
    state = get_state()
    if not state.policy_engine.status.constraints.allow_adaptive_verification:
        raise HTTPException(status_code=403, detail="Adaptive verification not allowed by constraints")

    decision = state.adaptive_verifier.decide(
        risk_score=body.risk_score,
        model_confidence=body.model_confidence,
        task_class=body.task_class,
        has_side_effects=body.has_side_effects,
        customer_facing=body.customer_facing,
    )
    return {
        "should_verify": decision.should_verify,
        "reason": decision.reason,
        "risk_score": decision.risk_score,
        "model_confidence": decision.model_confidence,
        "estimated_savings_if_skipped": decision.estimated_savings_if_skipped,
    }


@router.post("/verify/thresholds")
async def set_verification_thresholds(body: SetThresholdsRequest) -> dict:
    """Update verification thresholds."""
    state = get_state()
    state.adaptive_verifier.set_thresholds(risk=body.risk_threshold, confidence=body.confidence_threshold)
    return state.adaptive_verifier.get_stats()


@router.get("/verify/stats")
async def get_verification_stats() -> dict:
    """Get adaptive verification statistics."""
    state = get_state()
    return state.adaptive_verifier.get_stats()


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


@router.post("/recover")
async def recover_from_failure(body: RecoverRequest) -> dict:
    """Get a recovery decision for a failure."""
    state = get_state()
    if not state.policy_engine.status.constraints.allow_recovery_selection:
        raise HTTPException(status_code=403, detail="Recovery selection not allowed by constraints")

    decision = state.recovery_selector.select_recovery(
        failure_type=body.failure_type,
        failed_tool=body.failed_tool,
        failed_model=body.failed_model,
        error_message=body.error_message,
        retry_count=body.retry_count,
    )
    return {
        "strategy": decision.strategy.value,
        "target_tool": decision.target_tool,
        "target_model": decision.target_model,
        "reason": decision.reason,
        "historical_success_rate": decision.historical_success_rate,
        "expected_cost_to_success": decision.expected_cost_to_success,
        "alternative_cost_to_success": decision.alternative_cost_to_success,
    }


@router.post("/recover/rules")
async def add_recovery_rule(rule: RecoveryRule) -> dict:
    """Add a custom recovery rule."""
    state = get_state()
    created = state.recovery_selector.add_rule(rule)
    return created.model_dump()


@router.get("/recover/rules")
async def list_recovery_rules() -> dict:
    """List recovery rules."""
    state = get_state()
    rules = state.recovery_selector.list_rules()
    return {"count": len(rules), "rules": [r.model_dump() for r in rules]}


@router.get("/recover/stats")
async def get_recovery_stats() -> dict:
    """Get recovery statistics."""
    state = get_state()
    return state.recovery_selector.get_stats()


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


@router.get("/decisions")
async def list_decisions(limit: int = Query(default=50, le=500)) -> dict:
    """List recent autopilot decisions."""
    state = get_state()
    decisions = state.policy_engine.get_decisions(limit=limit)
    return {
        "count": len(decisions),
        "decisions": [_serialize_decision(d) for d in decisions],
    }


@router.post("/decisions/{decision_id}/approve")
async def approve_decision(decision_id: str, body: ApproveDecisionRequest) -> dict:
    """Approve a pending decision (supervised mode)."""
    state = get_state()
    try:
        decision = state.policy_engine.approve_decision(decision_id, actor=body.actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _serialize_decision(decision)


@router.post("/decisions/{decision_id}/reject")
async def reject_decision(decision_id: str, body: ApproveDecisionRequest) -> dict:
    """Reject a pending decision."""
    state = get_state()
    try:
        decision = state.policy_engine.reject_decision(decision_id, actor=body.actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _serialize_decision(decision)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_policy(p: ExecutionPolicy) -> dict:
    return {
        "policy_id": p.policy_id,
        "name": p.name,
        "description": p.description,
        "active": p.active,
        "task_class": p.task_class,
        "model_routing": p.model_routing,
        "default_model": p.default_model,
        "verification_threshold": p.verification_threshold,
        "skip_verification_confidence": p.skip_verification_confidence,
        "max_retries": p.max_retries,
        "fallback_tools": p.fallback_tools,
        "context_strategy": p.context_strategy,
        "parallelize_independent": p.parallelize_independent,
        "traces_routed": p.traces_routed,
        "total_savings": p.total_savings,
        "created_at": p.created_at.isoformat(),
    }


def _serialize_routing(d: RoutingDecision) -> dict:
    return {
        "decision_id": d.decision_id,
        "complexity": d.complexity.value,
        "risk": d.risk.value,
        "selected_model": d.selected_model,
        "original_model": d.original_model,
        "requires_verification": d.requires_verification,
        "reason": d.reason,
        "estimated_cost_savings": d.estimated_cost_savings,
    }


def _serialize_decision(d: PolicyDecision) -> dict:
    return {
        "decision_id": d.decision_id,
        "created_at": d.created_at.isoformat(),
        "action_type": d.action_type,
        "action_description": d.action_description,
        "reason": d.reason,
        "expected_savings": d.expected_savings,
        "constraints_satisfied": d.constraints_satisfied,
        "constraint_violations": d.constraint_violations,
        "outcome": d.outcome,
        "applied": d.applied,
        "approved_by": d.approved_by,
    }
