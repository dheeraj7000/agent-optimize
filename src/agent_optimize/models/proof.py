"""V3 Savings proof and canary monitoring models.

Every recommendation needs evidence. A savings proof validates that a proposed
optimization actually delivers the claimed savings while preserving quality.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from agent_optimize.evaluation.base import EvalSuite, EvalVerdict
from agent_optimize.models.waste import ConfidenceLevel

# ---------------------------------------------------------------------------
# Savings Proof
# ---------------------------------------------------------------------------


class ProofStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"  # Savings confirmed
    REJECTED = "rejected"  # Savings not confirmed or quality regressed
    EXPIRED = "expired"  # Too old, needs re-validation


class MetricSnapshot(BaseModel):
    """Point-in-time metrics for comparison."""

    total_cost: float = 0.0
    avg_cost_per_trace: float = 0.0
    success_rate: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0
    traces_count: int = 0
    window_hours: int = 168


class SavingsProof(BaseModel):
    """Validated proof that an optimization delivers its claimed savings.

    Every recommendation needs evidence: traces analyzed, counterfactual evaluations,
    observation window, quality regression risk, and confidence.
    """

    proof_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_id: str = ""
    experiment_id: str | None = None
    status: ProofStatus = ProofStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    validated_at: datetime | None = None

    # Before / after snapshots
    before: MetricSnapshot = Field(default_factory=MetricSnapshot)
    after: MetricSnapshot = Field(default_factory=MetricSnapshot)

    # Calculated savings
    actual_savings_pct: float = 0.0
    actual_monthly_savings: float = 0.0
    claimed_monthly_savings: float = 0.0
    savings_accuracy_pct: float = 0.0  # actual / claimed * 100

    # Quality preservation
    quality_preserved: bool = True
    quality_delta: float = 0.0
    latency_delta_pct: float = 0.0
    reliability_delta: float = 0.0

    # Evaluation results
    eval_suite: EvalSuite | None = None
    eval_verdict: EvalVerdict = EvalVerdict.SKIP

    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_pct: float = 0.0
    observation_window_days: int = 0
    traces_analyzed: int = 0

    # Evidence text
    summary: str = ""


# ---------------------------------------------------------------------------
# Canary
# ---------------------------------------------------------------------------


class CanaryStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Metrics dipped but within tolerance
    REGRESSED = "regressed"  # Quality breach — rollback recommended
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class CanaryThresholds(BaseModel):
    """Thresholds that trigger automatic rollback or alerting."""

    max_error_rate_increase: float = 0.02  # 2%
    max_latency_increase_pct: float = 25.0  # 25%
    min_success_rate: float = 0.93
    min_cost_savings_pct: float = 5.0  # Must still be saving at least this much
    evaluation_interval_minutes: int = 60
    min_canary_duration_hours: int = 24
    max_canary_duration_hours: int = 168  # 7 days


class CanaryCheckpoint(BaseModel):
    """A single checkpoint during canary monitoring."""

    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    checked_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    metrics: MetricSnapshot = Field(default_factory=MetricSnapshot)
    baseline_metrics: MetricSnapshot = Field(default_factory=MetricSnapshot)

    # Comparison
    cost_savings_pct: float = 0.0
    success_rate_delta: float = 0.0
    latency_delta_pct: float = 0.0
    error_rate_delta: float = 0.0

    # Assessment
    healthy: bool = True
    issues: list[str] = Field(default_factory=list)


class Canary(BaseModel):
    """A canary deployment being monitored for quality regression."""

    canary_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    recommendation_id: str = ""
    experiment_id: str | None = None
    status: CanaryStatus = CanaryStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Configuration
    thresholds: CanaryThresholds = Field(default_factory=CanaryThresholds)
    traffic_pct: float = 10.0  # % of traffic to route to candidate

    # Baseline metrics (captured at canary start)
    baseline_metrics: MetricSnapshot = Field(default_factory=MetricSnapshot)

    # Checkpoints
    checkpoints: list[CanaryCheckpoint] = Field(default_factory=list)

    # Outcome
    final_verdict: EvalVerdict = EvalVerdict.SKIP
    final_summary: str = ""
