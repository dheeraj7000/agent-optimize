"""Policy engine — customer-defined constraints and learned execution policies.

The long-term optimization policy selects the execution configuration that maximizes
business utility:

    policy* = argmax(Value - Cost - LatencyPenalty - ReliabilityPenalty - RiskPenalty)

Actions include: model choice, tool choice, reasoning budget, whether to verify,
whether to delegate, retry/fallback strategy, context strategy, cache strategy,
and parallelization.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

import structlog
from pydantic import BaseModel, Field

from agent_optimize.models.waste import ConfidenceLevel

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Constraints — the customer-defined guardrails
# ---------------------------------------------------------------------------


class PolicyConstraints(BaseModel):
    """Customer-defined quality, latency, cost, reliability, and risk guardrails.

    Every autopilot decision must satisfy these constraints. If a proposed action
    would violate a constraint, it is rejected regardless of cost savings.
    """

    # Quality
    min_quality_score: float = 0.95  # Minimum acceptable success/quality rate
    max_quality_regression: float = 0.02  # Max quality drop from baseline (epsilon)

    # Latency
    max_p50_latency_ms: float = 10000.0
    max_p95_latency_ms: float = 30000.0

    # Reliability
    min_reliability: float = 0.98  # Minimum completion/success rate

    # Cost
    max_cost_per_trace: float | None = None  # Hard cap on per-trace cost
    max_monthly_budget: float | None = None  # Monthly budget ceiling

    # Risk
    max_risk_level: ConfidenceLevel = ConfidenceLevel.MEDIUM  # Max acceptable risk
    require_canary: bool = True  # Require canary before full rollout
    require_replay_validation: bool = True  # Require replay proof before deploy

    # Autopilot permissions — what the system is allowed to change automatically
    allow_model_routing: bool = True
    allow_adaptive_verification: bool = True
    allow_recovery_selection: bool = True
    allow_context_optimization: bool = False  # Higher risk, opt-in
    allow_parallelization: bool = True


class AutopilotMode(str, enum.Enum):
    """Autopilot operating mode."""

    OFF = "off"  # All manual
    SUGGEST = "suggest"  # Generate decisions but don't apply
    SUPERVISED = "supervised"  # Apply with human approval per decision
    AUTONOMOUS = "autonomous"  # Apply automatically within constraints


class AutopilotStatus(BaseModel):
    """Current autopilot system status."""

    mode: AutopilotMode = AutopilotMode.OFF
    enabled_at: datetime | None = None
    constraints: PolicyConstraints = Field(default_factory=PolicyConstraints)

    # Stats
    decisions_made: int = 0
    decisions_applied: int = 0
    decisions_rejected: int = 0
    estimated_monthly_savings: float = 0.0
    quality_score: float = 0.0
    last_decision_at: datetime | None = None

    # Health
    healthy: bool = True
    issues: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


class PolicyDecision(BaseModel):
    """A single decision made by the autopilot policy engine.

    Every decision records what action was taken, why, and whether it
    satisfied the constraints.
    """

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # What
    action_type: str = ""  # "model_route", "verify_skip", "recovery_fallback", "parallelize"
    action_description: str = ""
    action_params: dict = Field(default_factory=dict)

    # Why
    reason: str = ""
    expected_savings: float = 0.0
    expected_quality_impact: float = 0.0
    expected_latency_impact_ms: float = 0.0

    # Constraint check
    constraints_satisfied: bool = True
    constraint_violations: list[str] = Field(default_factory=list)

    # Outcome
    applied: bool = False
    approved_by: str | None = None  # "autopilot", "user:<name>", None
    outcome: str = ""  # "applied", "pending_approval", "rejected", "constraint_violation"


# ---------------------------------------------------------------------------
# Execution policy
# ---------------------------------------------------------------------------


class ExecutionPolicy(BaseModel):
    """A learned execution policy for a specific task class or workload.

    Encodes the cheapest reliable execution configuration discovered through
    historical analysis and validated through replay.
    """

    policy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    tenant_id: str | None = None
    task_class: str | None = None  # Which workload this policy applies to

    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    active: bool = False

    # Constraints this policy operates within
    constraints: PolicyConstraints = Field(default_factory=PolicyConstraints)

    # Routing rules
    model_routing: dict[str, str] = Field(default_factory=dict)  # complexity_tier -> model
    default_model: str = ""

    # Verification rules
    verification_threshold: float = 0.7  # risk_score above this triggers verification
    skip_verification_confidence: float = 0.9  # confidence above this skips verification

    # Recovery rules
    max_retries: int = 2
    fallback_tools: dict[str, str] = Field(default_factory=dict)  # tool -> fallback
    fallback_models: dict[str, str] = Field(default_factory=dict)  # model -> fallback

    # Context rules
    context_strategy: str = "full_history"
    max_context_tokens: int | None = None

    # Parallelization
    parallelize_independent: bool = False

    # Performance tracking
    traces_routed: int = 0
    avg_cost_per_trace: float = 0.0
    avg_quality: float = 0.0
    avg_latency_ms: float = 0.0
    total_savings: float = 0.0


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------


class PolicyEngine:
    """The autopilot brain — evaluates requests and makes constrained decisions."""

    def __init__(self) -> None:
        self._status = AutopilotStatus()
        self._policies: dict[str, ExecutionPolicy] = {}
        self._decisions: list[PolicyDecision] = []

    @property
    def status(self) -> AutopilotStatus:
        return self._status

    def set_mode(self, mode: AutopilotMode) -> AutopilotStatus:
        self._status.mode = mode
        if mode != AutopilotMode.OFF and not self._status.enabled_at:
            self._status.enabled_at = datetime.now(tz=UTC)
        logger.info("policy_engine.mode_changed", mode=mode.value)
        return self._status

    def set_constraints(self, constraints: PolicyConstraints) -> AutopilotStatus:
        self._status.constraints = constraints
        logger.info("policy_engine.constraints_updated")
        return self._status

    # -- Policy CRUD --

    def create_policy(self, policy: ExecutionPolicy) -> ExecutionPolicy:
        policy.constraints = self._status.constraints
        self._policies[policy.policy_id] = policy
        logger.info("policy_engine.policy_created", policy_id=policy.policy_id, name=policy.name)
        return policy

    def get_policy(self, policy_id: str) -> ExecutionPolicy | None:
        return self._policies.get(policy_id)

    def list_policies(self, active_only: bool = False) -> list[ExecutionPolicy]:
        policies = list(self._policies.values())
        if active_only:
            policies = [p for p in policies if p.active]
        return policies

    def activate_policy(self, policy_id: str) -> ExecutionPolicy:
        policy = self._policies.get(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        policy.active = True
        policy.updated_at = datetime.now(tz=UTC)
        logger.info("policy_engine.policy_activated", policy_id=policy_id)
        return policy

    def deactivate_policy(self, policy_id: str) -> ExecutionPolicy:
        policy = self._policies.get(policy_id)
        if not policy:
            raise ValueError(f"Policy {policy_id} not found")
        policy.active = False
        policy.updated_at = datetime.now(tz=UTC)
        logger.info("policy_engine.policy_deactivated", policy_id=policy_id)
        return policy

    # -- Decision making --

    def make_decision(self, decision: PolicyDecision) -> PolicyDecision:
        """Evaluate a decision against constraints and record it."""
        constraints = self._status.constraints

        # Check constraints
        violations: list[str] = []

        if decision.expected_quality_impact < -constraints.max_quality_regression:
            violations.append(
                f"Quality regression {decision.expected_quality_impact:.3%} exceeds "
                f"max allowed {constraints.max_quality_regression:.3%}"
            )

        decision.constraint_violations = violations
        decision.constraints_satisfied = len(violations) == 0

        # Determine outcome based on mode
        if not decision.constraints_satisfied:
            decision.outcome = "constraint_violation"
            decision.applied = False
            self._status.decisions_rejected += 1
        elif self._status.mode == AutopilotMode.AUTONOMOUS:
            decision.outcome = "applied"
            decision.applied = True
            decision.approved_by = "autopilot"
            self._status.decisions_applied += 1
            self._status.estimated_monthly_savings += decision.expected_savings
        elif self._status.mode == AutopilotMode.SUPERVISED:
            decision.outcome = "pending_approval"
            decision.applied = False
        elif self._status.mode == AutopilotMode.SUGGEST:
            decision.outcome = "suggested"
            decision.applied = False
        else:
            decision.outcome = "autopilot_off"
            decision.applied = False

        self._status.decisions_made += 1
        self._status.last_decision_at = decision.created_at
        self._decisions.append(decision)

        logger.info(
            "policy_engine.decision",
            action=decision.action_type,
            outcome=decision.outcome,
            savings=decision.expected_savings,
        )

        return decision

    def approve_decision(self, decision_id: str, actor: str = "user") -> PolicyDecision:
        """Approve a pending decision (supervised mode)."""
        decision = next((d for d in self._decisions if d.decision_id == decision_id), None)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.outcome != "pending_approval":
            raise ValueError(f"Decision is not pending approval (status: {decision.outcome})")

        decision.applied = True
        decision.approved_by = f"user:{actor}"
        decision.outcome = "applied"
        self._status.decisions_applied += 1
        self._status.estimated_monthly_savings += decision.expected_savings
        return decision

    def reject_decision(self, decision_id: str, actor: str = "user") -> PolicyDecision:
        """Reject a pending decision."""
        decision = next((d for d in self._decisions if d.decision_id == decision_id), None)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")

        decision.applied = False
        decision.approved_by = f"user:{actor}"
        decision.outcome = "rejected"
        self._status.decisions_rejected += 1
        return decision

    def get_decisions(self, limit: int = 100) -> list[PolicyDecision]:
        return list(reversed(self._decisions[-limit:]))

    def get_stats(self) -> dict:
        return {
            "mode": self._status.mode.value,
            "decisions_made": self._status.decisions_made,
            "decisions_applied": self._status.decisions_applied,
            "decisions_rejected": self._status.decisions_rejected,
            "estimated_monthly_savings": round(self._status.estimated_monthly_savings, 2),
            "policies_active": sum(1 for p in self._policies.values() if p.active),
            "policies_total": len(self._policies),
        }
