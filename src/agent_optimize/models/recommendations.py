"""V2 Recommendation models — lifecycle, confidence scoring, evidence chains, and config comparison.

Recommendations are the actionable output of the optimization engine. Each one moves
through a lifecycle: pending → accepted → deployed → verified (or rejected/rolled_back).
Teams prioritize fixes by business value — expected savings, quality risk, and effort.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from agent_optimize.models.waste import ConfidenceLevel, WasteCategory

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class RecommendationStatus(str, enum.Enum):
    """Tracks where a recommendation is in its lifecycle."""

    PENDING = "pending"  # Generated, awaiting review
    ACCEPTED = "accepted"  # Team agrees, ready for replay/canary
    REJECTED = "rejected"  # Team decided not to pursue
    REPLAYING = "replaying"  # Counterfactual replay in progress
    VALIDATED = "validated"  # Replay confirms savings + quality preserved
    DEPLOYED = "deployed"  # Change applied in production
    VERIFIED = "verified"  # Post-deploy monitoring confirms the savings
    ROLLED_BACK = "rolled_back"  # Deployed but reverted due to regression


class RecommendationPriority(str, enum.Enum):
    """Business-value priority for ordering work."""

    CRITICAL = "critical"  # >$10k/month, high confidence, low risk
    HIGH = "high"  # >$5k/month or high confidence
    MEDIUM = "medium"  # Moderate savings or moderate confidence
    LOW = "low"  # Small savings or low confidence


# ---------------------------------------------------------------------------
# Evidence chain
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A single piece of evidence backing a recommendation."""

    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = ""  # "trace_sample", "statistical", "replay_result", "ablation"
    description: str = ""
    data: dict = Field(default_factory=dict)  # Structured evidence payload
    source_trace_ids: list[str] = Field(default_factory=list)
    source_span_ids: list[str] = Field(default_factory=list)


class EvidenceChain(BaseModel):
    """Ordered collection of evidence supporting a recommendation.

    Every recommendation needs evidence — sample size, workload representativeness,
    evaluator stability, variance, and similarity between replay and production.
    """

    items: list[EvidenceItem] = Field(default_factory=list)
    traces_analyzed: int = 0
    counterfactual_evaluations: int = 0
    observation_window_days: int = 0
    summary: str = ""


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------


class ConfidenceScore(BaseModel):
    """Structured confidence assessment for a recommendation.

    Confidence depends on sample size, workload representativeness, evaluator stability,
    variance, model/provider changes, and similarity between replay and production.
    """

    overall: ConfidenceLevel = ConfidenceLevel.LOW
    overall_pct: float = 0.0  # 0-100

    # Contributing factors
    sample_size_score: float = 0.0  # 0-1, based on trace count
    workload_coverage: float = 0.0  # 0-1, how representative the sample is
    variance_score: float = 0.0  # 0-1, low variance = high score
    evaluator_agreement: float = 0.0  # 0-1, multiple detectors agree
    replay_confidence: float = 0.0  # 0-1, replay validates the projection

    # Risk factors
    model_drift_risk: float = 0.0  # 0-1, risk that model/pricing changes invalidate
    workload_drift_risk: float = 0.0  # 0-1, risk that traffic patterns change


# ---------------------------------------------------------------------------
# Impact projections
# ---------------------------------------------------------------------------


class ImpactProjection(BaseModel):
    """Projected impact of applying a recommendation across all five dimensions."""

    # Cost
    current_monthly_cost: float = 0.0
    projected_monthly_cost: float = 0.0
    monthly_savings: float = 0.0
    annual_savings: float = 0.0
    cost_reduction_pct: float = 0.0

    # Quality
    current_quality: float = 0.0
    projected_quality: float = 0.0
    quality_delta: float = 0.0  # Negative = regression
    quality_risk: ConfidenceLevel = ConfidenceLevel.LOW

    # Latency
    current_p50_ms: float = 0.0
    current_p95_ms: float = 0.0
    projected_p50_ms: float = 0.0
    projected_p95_ms: float = 0.0
    latency_reduction_pct: float = 0.0

    # Reliability
    current_reliability: float = 0.0
    projected_reliability: float = 0.0
    reliability_delta: float = 0.0

    # Risk
    risk_level: ConfidenceLevel = ConfidenceLevel.LOW
    risk_description: str = ""


# ---------------------------------------------------------------------------
# Configuration comparison
# ---------------------------------------------------------------------------


class ConfigSnapshot(BaseModel):
    """A snapshot of an agent configuration — what models, tools, and settings are used."""

    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""

    # Configuration details
    model_assignments: dict[str, str] = Field(default_factory=dict)  # step -> model
    tool_config: dict[str, dict] = Field(default_factory=dict)  # tool -> settings
    verification_enabled: bool = True
    retry_policy: dict = Field(default_factory=dict)
    parallelization_enabled: bool = False
    context_strategy: str = "full_history"  # full_history, summarized, windowed
    cache_strategy: str = "none"  # none, input_hash, semantic


class ConfigComparison(BaseModel):
    """Side-by-side comparison of two configurations with projected metrics."""

    comparison_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    current_config: ConfigSnapshot = Field(default_factory=ConfigSnapshot)
    proposed_config: ConfigSnapshot = Field(default_factory=ConfigSnapshot)

    # Comparison results
    impact: ImpactProjection = Field(default_factory=ImpactProjection)
    evidence: EvidenceChain = Field(default_factory=EvidenceChain)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)

    # What changed
    changes: list[str] = Field(default_factory=list)  # Human-readable change descriptions


# ---------------------------------------------------------------------------
# The Recommendation itself
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    """A concrete, actionable optimization recommendation.

    This is the V2 core: it connects a detected waste opportunity to a proposed change
    with full impact projections, evidence, confidence scoring, and lifecycle tracking.
    Teams prioritize these by business value.
    """

    recommendation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # Lifecycle
    status: RecommendationStatus = RecommendationStatus.PENDING
    status_history: list[dict] = Field(default_factory=list)  # [{status, timestamp, actor}]

    # What waste this addresses
    category: WasteCategory = WasteCategory.MODEL_OVERPROVISIONING
    opportunity_id: str = ""  # Links back to the V1 Opportunity

    # Priority
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    business_value_score: float = 0.0  # Composite score for ranking (0-100)
    engineering_effort: str = "medium"  # low, medium, high

    # The recommendation
    title: str = ""
    description: str = ""
    action_items: list[str] = Field(default_factory=list)

    # Impact assessment
    impact: ImpactProjection = Field(default_factory=ImpactProjection)

    # Evidence and confidence
    evidence: EvidenceChain = Field(default_factory=EvidenceChain)
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)

    # Configuration change
    config_comparison: ConfigComparison | None = None

    # Replay experiment (if one has been run)
    replay_experiment_id: str | None = None

    # Tenant
    tenant_id: str | None = None

    # Affected scope
    affected_task_classes: list[str] = Field(default_factory=list)
    affected_models: list[str] = Field(default_factory=list)
    affected_tools: list[str] = Field(default_factory=list)

    # Underlying detections
    source_detection_ids: list[str] = Field(default_factory=list)
    traces_analyzed: int = 0


class RecommendationSummary(BaseModel):
    """Lightweight view of a recommendation for list endpoints."""

    recommendation_id: str
    status: RecommendationStatus
    priority: RecommendationPriority
    category: WasteCategory
    title: str
    monthly_savings: float = 0.0
    annual_savings: float = 0.0
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    quality_risk: ConfidenceLevel = ConfidenceLevel.LOW
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
