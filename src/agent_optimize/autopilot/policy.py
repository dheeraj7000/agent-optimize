"""Policy engine — customer constraints and execution-policy tracking."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

import structlog
from pydantic import BaseModel, Field

from agent_optimize.models.waste import ConfidenceLevel

logger = structlog.get_logger()


class PolicyConstraints(BaseModel):
    """Customer-defined quality, latency, cost, reliability, and risk guardrails."""

    min_quality_score: float = 0.95
    max_quality_regression: float = 0.02
    max_p50_latency_ms: float = 10000.0
    max_p95_latency_ms: float = 30000.0
    min_reliability: float = 0.98
    max_cost_per_trace: float | None = None
    max_monthly_budget: float | None = None
    max_risk_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    require_canary: bool = True
    require_replay_validation: bool = True
    allow_model_routing: bool = True
    allow_adaptive_verification: bool = True
    allow_recovery_selection: bool = True
    allow_context_optimization: bool = False
    allow_parallelization: bool = True


class AutopilotMode(str, enum.Enum):
    OFF = "off"
    SUGGEST = "suggest"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class AutopilotStatus(BaseModel):
    mode: AutopilotMode = AutopilotMode.OFF
    enabled_at: datetime | None = None
    constraints: PolicyConstraints = Field(default_factory=PolicyConstraints)
    decisions_made: int = 0
    decisions_applied: int = 0
    decisions_rejected: int = 0
    estimated_monthly_savings: float = 0.0
    quality_score: float = 0.0
    last_decision_at: datetime | None = None
    healthy: bool = True
    issues: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    """Proposal metadata and evidence used to evaluate every policy guardrail."""

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    action_type: str = ""
    action_description: str = ""
    action_params: dict = Field(default_factory=dict)
    reason: str = ""
    expected_savings: float = 0.0
    expected_quality_impact: float = 0.0
    expected_latency_impact_ms: float = 0.0
    projected_quality_score: float | None = None
    projected_p50_latency_ms: float | None = None
    projected_p95_latency_ms: float | None = None
    projected_reliability: float | None = None
    projected_cost_per_trace: float | None = None
    projected_monthly_cost: float | None = None
    risk_level: ConfidenceLevel | None = None
    replay_validation_passed: bool = False
    canary_passed: bool = False
    constraints_satisfied: bool = True
    constraint_violations: list[str] = Field(default_factory=list)
    applied: bool = False
    approved_by: str | None = None
    outcome: str = ""


class ExecutionPolicy(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    tenant_id: str | None = None
    task_class: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    active: bool = False
    constraints: PolicyConstraints = Field(default_factory=PolicyConstraints)
    model_routing: dict[str, str] = Field(default_factory=dict)
    default_model: str = ""
    verification_threshold: float = 0.7
    skip_verification_confidence: float = 0.9
    max_retries: int = 2
    fallback_tools: dict[str, str] = Field(default_factory=dict)
    fallback_models: dict[str, str] = Field(default_factory=dict)
    context_strategy: str = "full_history"
    max_context_tokens: int | None = None
    parallelize_independent: bool = False
    traces_routed: int = 0
    avg_cost_per_trace: float = 0.0
    avg_quality: float = 0.0
    avg_latency_ms: float = 0.0
    total_savings: float = 0.0


class PolicyEngine:
    """Evaluates proposals fail-closed and never claims an action was executed."""

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

    def create_policy(self, policy: ExecutionPolicy) -> ExecutionPolicy:
        policy.constraints = self._status.constraints
        self._policies[policy.policy_id] = policy
        logger.info("policy_engine.policy_created", policy_id=policy.policy_id, name=policy.name)
        return policy

    def get_policy(self, policy_id: str) -> ExecutionPolicy | None:
        return self._policies.get(policy_id)

    def list_policies(self, active_only: bool = False) -> list[ExecutionPolicy]:
        policies = list(self._policies.values())
        return [policy for policy in policies if policy.active] if active_only else policies

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

    def _violations(self, decision: PolicyDecision) -> list[str]:
        c = self._status.constraints
        issues: list[str] = []
        if decision.expected_quality_impact < -c.max_quality_regression:
            issues.append("Expected quality regression exceeds the configured maximum")
        if decision.projected_quality_score is None:
            issues.append("Projected quality score is required")
        elif decision.projected_quality_score < c.min_quality_score:
            issues.append("Projected quality score is below the configured minimum")
        for label, value, maximum in (
            ("p50 latency", decision.projected_p50_latency_ms, c.max_p50_latency_ms),
            ("p95 latency", decision.projected_p95_latency_ms, c.max_p95_latency_ms),
        ):
            if value is None:
                issues.append(f"Projected {label} is required")
            elif value > maximum:
                issues.append(f"Projected {label} exceeds the configured maximum")
        if decision.projected_reliability is None:
            issues.append("Projected reliability is required")
        elif decision.projected_reliability < c.min_reliability:
            issues.append("Projected reliability is below the configured minimum")
        if c.max_cost_per_trace is not None:
            if decision.projected_cost_per_trace is None:
                issues.append("Projected cost per trace is required")
            elif decision.projected_cost_per_trace > c.max_cost_per_trace:
                issues.append("Projected cost per trace exceeds the configured maximum")
        if c.max_monthly_budget is not None:
            if decision.projected_monthly_cost is None:
                issues.append("Projected monthly cost is required")
            elif decision.projected_monthly_cost > c.max_monthly_budget:
                issues.append("Projected monthly cost exceeds the configured budget")
        if decision.risk_level is None:
            issues.append("A risk level is required")
        elif decision.risk_level > c.max_risk_level:
            issues.append("Risk level exceeds the configured maximum")
        if c.require_replay_validation and not decision.replay_validation_passed:
            issues.append("Replay validation is required and has not passed")
        if c.require_canary and not decision.canary_passed:
            issues.append("Canary validation is required and has not passed")
        return issues

    def make_decision(self, decision: PolicyDecision) -> PolicyDecision:
        decision.constraint_violations = self._violations(decision)
        decision.constraints_satisfied = not decision.constraint_violations
        if not decision.constraints_satisfied:
            decision.outcome = "constraint_violation"
            self._status.decisions_rejected += 1
        elif self._status.mode == AutopilotMode.AUTONOMOUS:
            decision.outcome = "authorized_not_executed"
            decision.approved_by = "autopilot"
        elif self._status.mode == AutopilotMode.SUPERVISED:
            decision.outcome = "pending_approval"
        elif self._status.mode == AutopilotMode.SUGGEST:
            decision.outcome = "suggested"
        else:
            decision.outcome = "autopilot_off"
        self._status.decisions_made += 1
        self._status.last_decision_at = decision.created_at
        self._decisions.append(decision)
        logger.info("policy_engine.decision", action=decision.action_type,
                    outcome=decision.outcome, savings=decision.expected_savings)
        return decision

    def approve_decision(self, decision_id: str, actor: str = "user") -> PolicyDecision:
        decision = next((item for item in self._decisions if item.decision_id == decision_id), None)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.outcome != "pending_approval":
            raise ValueError(f"Decision is not pending approval (status: {decision.outcome})")
        decision.applied = False
        decision.approved_by = f"user:{actor}"
        decision.outcome = "approved_not_executed"
        return decision

    def reject_decision(self, decision_id: str, actor: str = "user") -> PolicyDecision:
        decision = next((item for item in self._decisions if item.decision_id == decision_id), None)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        if decision.outcome != "pending_approval":
            raise ValueError(f"Decision is not pending approval (status: {decision.outcome})")
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
            "policies_active": sum(1 for policy in self._policies.values() if policy.active),
            "policies_total": len(self._policies),
        }
