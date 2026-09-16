"""V2 Recommendation generator — converts Opportunities into actionable Recommendations.

Takes the V1 optimization engine output (Opportunities with waste detections) and produces
Recommendations with full confidence scoring, impact projections, evidence chains,
auto-generated candidate configurations, and business-value prioritization.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import structlog

from agent_optimize.models.recommendations import (
    ConfidenceScore,
    ConfigComparison,
    ConfigSnapshot,
    EvidenceChain,
    EvidenceItem,
    ImpactProjection,
    Recommendation,
    RecommendationPriority,
    RecommendationStatus,
)
from agent_optimize.models.traces import NormalizedTrace
from agent_optimize.models.waste import (
    ConfidenceLevel,
    Opportunity,
    WasteCategory,
    WasteDetection,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

_SAMPLE_SIZE_THRESHOLDS = {50: 0.3, 200: 0.5, 1000: 0.7, 5000: 0.9, 10000: 1.0}


def _score_sample_size(n: int) -> float:
    """Score confidence from sample size (0-1)."""
    for threshold, score in sorted(_SAMPLE_SIZE_THRESHOLDS.items()):
        if n <= threshold:
            return score
    return 1.0


def _score_variance(detections: list[WasteDetection]) -> float:
    """Score based on how consistent the waste estimates are (low variance = high score)."""
    if len(detections) < 2:
        return 0.5
    costs = [d.estimated_waste_cost for d in detections]
    mean = sum(costs) / len(costs)
    if mean == 0:
        return 0.5
    variance = sum((c - mean) ** 2 for c in costs) / len(costs)
    cv = math.sqrt(variance) / mean if mean > 0 else 0  # Coefficient of variation
    # CV < 0.3 = very consistent, CV > 2.0 = highly variable
    return max(0.0, min(1.0, 1.0 - (cv / 2.0)))


def _score_evaluator_agreement(detections: list[WasteDetection]) -> float:
    """Score based on how many detectors found the same category of waste."""
    if not detections:
        return 0.0
    unique_detectors = {d.detector_name for d in detections}
    # More detector agreement = higher confidence (diminishing returns)
    return min(1.0, len(unique_detectors) * 0.5)


def compute_confidence(
    detections: list[WasteDetection],
    traces_analyzed: int,
    observation_days: int,
) -> ConfidenceScore:
    """Compute a structured confidence score for a recommendation."""
    sample_score = _score_sample_size(traces_analyzed)
    variance_score = _score_variance(detections)
    agreement_score = _score_evaluator_agreement(detections)

    # Workload coverage: longer observation = more representative
    coverage = min(1.0, observation_days / 14.0)  # 14 days = full coverage

    # Overall: weighted combination
    overall_pct = (
        sample_score * 30
        + coverage * 25
        + variance_score * 25
        + agreement_score * 20
    )

    if overall_pct >= 80:
        overall = ConfidenceLevel.HIGH
    elif overall_pct >= 50:
        overall = ConfidenceLevel.MEDIUM
    else:
        overall = ConfidenceLevel.LOW

    return ConfidenceScore(
        overall=overall,
        overall_pct=round(overall_pct, 1),
        sample_size_score=round(sample_score, 3),
        workload_coverage=round(coverage, 3),
        variance_score=round(variance_score, 3),
        evaluator_agreement=round(agreement_score, 3),
        replay_confidence=0.0,  # Set after replay
        model_drift_risk=0.1,  # Baseline risk
        workload_drift_risk=0.1,
    )


# ---------------------------------------------------------------------------
# Evidence chain builder
# ---------------------------------------------------------------------------


def build_evidence_chain(
    detections: list[WasteDetection],
    traces_analyzed: int,
    observation_days: int,
) -> EvidenceChain:
    """Build a structured evidence chain from waste detections."""
    items: list[EvidenceItem] = []

    # Statistical summary evidence
    if detections:
        costs = [d.estimated_waste_cost for d in detections]
        items.append(EvidenceItem(
            kind="statistical",
            description=(
                f"Analyzed {traces_analyzed} traces over {observation_days} days. "
                f"Found {len(detections)} instances with waste estimates "
                f"ranging ${min(costs):.4f} to ${max(costs):.4f}."
            ),
            data={
                "detection_count": len(detections),
                "min_waste": round(min(costs), 4),
                "max_waste": round(max(costs), 4),
                "mean_waste": round(sum(costs) / len(costs), 4),
            },
        ))

    # Sample trace evidence (top 5 by waste)
    top_detections = sorted(detections, key=lambda d: d.estimated_waste_cost, reverse=True)[:5]
    for d in top_detections:
        items.append(EvidenceItem(
            kind="trace_sample",
            description=d.evidence,
            data={
                "detection_id": d.detection_id,
                "waste_cost": d.estimated_waste_cost,
                "savings_pct": d.savings_pct,
                "confidence": d.confidence.value,
            },
            source_trace_ids=[d.trace_id],
            source_span_ids=d.span_ids,
        ))

    return EvidenceChain(
        items=items,
        traces_analyzed=traces_analyzed,
        counterfactual_evaluations=0,  # Set after replay
        observation_window_days=observation_days,
        summary=(
            f"{len(detections)} detections across {traces_analyzed} traces "
            f"over {observation_days}-day observation window."
        ),
    )


# ---------------------------------------------------------------------------
# Impact projection
# ---------------------------------------------------------------------------


def project_impact(
    opportunity: Opportunity,
    detections: list[WasteDetection],
    traces: list[NormalizedTrace],
) -> ImpactProjection:
    """Project the full impact of applying an optimization."""
    # Cost
    monthly_waste = opportunity.estimated_monthly_waste
    monthly_spend = (
        monthly_waste / (opportunity.affected_traces_pct / 100)
        if opportunity.affected_traces_pct > 0
        else 0
    )

    # Quality
    quality_impacts = [d.estimated_quality_impact for d in detections if d.estimated_quality_impact != 0]
    avg_quality_delta = sum(quality_impacts) / len(quality_impacts) if quality_impacts else 0.0

    # Determine quality risk
    if avg_quality_delta >= -0.005:
        quality_risk = ConfidenceLevel.LOW
    elif avg_quality_delta >= -0.02:
        quality_risk = ConfidenceLevel.MEDIUM
    else:
        quality_risk = ConfidenceLevel.HIGH

    # Latency from traces
    durations = [t.duration_ms for t in traces if t.duration_ms > 0]
    if durations:
        durations_sorted = sorted(durations)
        p50 = durations_sorted[len(durations_sorted) // 2]
        p95 = durations_sorted[int(len(durations_sorted) * 0.95)]
    else:
        p50 = p95 = 0.0

    latency_pct = opportunity.estimated_latency_impact_pct

    # Reliability
    success_count = sum(1 for t in traces if t.success)
    reliability = success_count / len(traces) if traces else 0.0

    return ImpactProjection(
        current_monthly_cost=round(monthly_spend, 2),
        projected_monthly_cost=round(monthly_spend - monthly_waste, 2),
        monthly_savings=round(monthly_waste, 2),
        annual_savings=round(monthly_waste * 12, 2),
        cost_reduction_pct=round(
            (monthly_waste / monthly_spend * 100) if monthly_spend > 0 else 0, 1
        ),
        current_quality=round(reliability, 4),
        projected_quality=round(reliability + avg_quality_delta, 4),
        quality_delta=round(avg_quality_delta, 4),
        quality_risk=quality_risk,
        current_p50_ms=round(p50, 1),
        current_p95_ms=round(p95, 1),
        projected_p50_ms=round(p50 * (1 + latency_pct / 100), 1),
        projected_p95_ms=round(p95 * (1 + latency_pct / 100), 1),
        latency_reduction_pct=round(-latency_pct, 1),
        current_reliability=round(reliability, 4),
        projected_reliability=round(reliability, 4),
        reliability_delta=0.0,
        risk_level=quality_risk,
        risk_description=_risk_description(quality_risk, avg_quality_delta),
    )


def _risk_description(risk: ConfidenceLevel, quality_delta: float) -> str:
    if risk == ConfidenceLevel.LOW:
        return "Low risk. Expected quality impact is negligible."
    if risk == ConfidenceLevel.MEDIUM:
        return f"Medium risk. Expected quality delta: {quality_delta:.3%}. Recommend replay validation."
    return f"High risk. Expected quality delta: {quality_delta:.3%}. Require replay + canary before deployment."


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------

_SMALL_MODELS = {"gpt-4o-mini", "claude-haiku-3-20240307", "gemini-2.0-flash"}


def generate_config_comparison(
    category: WasteCategory,
    detections: list[WasteDetection],
    traces: list[NormalizedTrace],
) -> ConfigComparison:
    """Auto-generate a proposed config change based on the waste category."""
    current = ConfigSnapshot(name="current", description="Current production configuration")
    proposed = ConfigSnapshot(name="proposed", description="Optimized configuration")
    changes: list[str] = []

    # Extract current models/tools from traces
    models_used: set[str] = set()
    tools_used: set[str] = set()
    for t in traces:
        models_used.update(t.unique_models)
        tools_used.update(t.unique_tools)

    current.model_assignments = {f"step_{i}": m for i, m in enumerate(sorted(models_used))}
    proposed.model_assignments = dict(current.model_assignments)

    if category == WasteCategory.MODEL_OVERPROVISIONING:
        small = next(iter(_SMALL_MODELS), "gpt-4o-mini")
        proposed.model_assignments["low_complexity"] = small
        changes.append(f"Route low-complexity calls to {small}")

    elif category == WasteCategory.BAD_ROUTING:
        small = next(iter(_SMALL_MODELS), "gpt-4o-mini")
        proposed.model_assignments["low_complexity"] = small
        proposed.model_assignments["medium_complexity"] = "gpt-4o"
        changes.append("Implement complexity-based model routing")
        changes.append(f"Low complexity → {small}, medium → gpt-4o, high → current frontier")

    elif category == WasteCategory.CONTEXT_DUPLICATION:
        proposed.context_strategy = "summarized"
        proposed.cache_strategy = "input_hash"
        changes.append("Switch context strategy from full_history to summarized")
        changes.append("Enable input-hash based caching")

    elif category == WasteCategory.RETRY_WASTE:
        proposed.retry_policy = {"max_retries": 2, "fallback_enabled": True}
        changes.append("Limit retries to 2 before fallback")
        changes.append("Enable fallback tool strategy")

    elif category == WasteCategory.UNNECESSARY_VERIFICATION:
        proposed.verification_enabled = False
        changes.append("Disable unconditional verification on low-risk runs")
        changes.append("Enable conditional verification (risk_score > 0.7)")

    elif category == WasteCategory.REDUNDANT_TOOL_CALLS:
        proposed.cache_strategy = "input_hash"
        changes.append("Enable tool result caching for equivalent inputs")

    elif category == WasteCategory.SERIALIZATION_WASTE:
        proposed.parallelization_enabled = True
        changes.append("Enable parallel execution for independent workflow stages")

    return ConfigComparison(
        current_config=current,
        proposed_config=proposed,
        changes=changes,
    )


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------


def compute_priority(
    impact: ImpactProjection,
    confidence: ConfidenceScore,
) -> tuple[RecommendationPriority, float]:
    """Compute business-value priority and score for ranking.

    Score (0-100) considers: savings magnitude, confidence, quality risk, and effort.
    """
    # Savings component (0-40)
    annual = impact.annual_savings
    if annual >= 120_000:
        savings_score = 40.0
    elif annual >= 60_000:
        savings_score = 30.0
    elif annual >= 12_000:
        savings_score = 20.0
    elif annual >= 3_000:
        savings_score = 10.0
    else:
        savings_score = 5.0

    # Confidence component (0-30)
    confidence_score = confidence.overall_pct * 0.3

    # Quality risk penalty (0 to -20)
    risk_penalty = {
        ConfidenceLevel.LOW: 0,
        ConfidenceLevel.MEDIUM: -10,
        ConfidenceLevel.HIGH: -20,
    }.get(impact.quality_risk, 0)

    # Cost reduction magnitude bonus (0-10)
    reduction_bonus = min(10.0, impact.cost_reduction_pct / 5.0)

    total = max(0.0, min(100.0, savings_score + confidence_score + risk_penalty + reduction_bonus))

    if total >= 75:
        priority = RecommendationPriority.CRITICAL
    elif total >= 55:
        priority = RecommendationPriority.HIGH
    elif total >= 35:
        priority = RecommendationPriority.MEDIUM
    else:
        priority = RecommendationPriority.LOW

    return priority, round(total, 1)


# ---------------------------------------------------------------------------
# Main entry: generate recommendations from opportunities
# ---------------------------------------------------------------------------

# Category -> suggested action items
_ACTION_ITEMS: dict[WasteCategory, list[str]] = {
    WasteCategory.MODEL_OVERPROVISIONING: [
        "Classify workload complexity using input/output token patterns",
        "Replay representative low-complexity inputs against candidate models",
        "Validate quality scores meet threshold before routing",
        "Deploy complexity-based router with gradual rollout",
    ],
    WasteCategory.CONTEXT_DUPLICATION: [
        "Measure context novelty ratio across multi-turn conversations",
        "Implement conversation summarization at turn boundaries",
        "Enable provider-side prompt caching where available",
        "Monitor quality after context reduction",
    ],
    WasteCategory.RETRY_WASTE: [
        "Analyze historical retry success rates by tool and error type",
        "Implement retry budget (max 2 retries before fallback)",
        "Configure fallback tools for high-failure-rate operations",
        "Distinguish infrastructure failures from reasoning failures",
    ],
    WasteCategory.UNNECESSARY_VERIFICATION: [
        "Run ablation analysis across historical traces to measure verifier impact",
        "Implement conditional verification triggered by risk score",
        "Set verification threshold (e.g., risk_score > 0.7)",
        "Monitor quality delta after conditional verification rollout",
    ],
    WasteCategory.REDUNDANT_TOOL_CALLS: [
        "Implement tool result cache keyed on input hash",
        "Cluster similar queries to identify semantic duplication",
        "Restructure agent retrieval strategy to batch related queries",
        "Monitor cache hit rate and quality after deployment",
    ],
    WasteCategory.BAD_ROUTING: [
        "Build task complexity classifier from historical traces",
        "Define model tiers: small (flash), medium (standard), large (frontier)",
        "Implement routing policy based on complexity/risk classification",
        "Validate routing decisions via counterfactual replay",
    ],
    WasteCategory.SERIALIZATION_WASTE: [
        "Map dependency graph to identify parallelizable stages",
        "Implement parallel execution for independent spans",
        "Verify output equivalence between serial and parallel execution",
        "Monitor latency improvements in production",
    ],
}


def generate_recommendations(
    opportunities: list[Opportunity],
    detections_by_category: dict[WasteCategory, list[WasteDetection]],
    traces: list[NormalizedTrace],
    observation_days: int = 7,
    tenant_id: str | None = None,
) -> list[Recommendation]:
    """Generate V2 Recommendations from V1 Opportunities.

    Each Opportunity becomes a Recommendation with full impact projections,
    evidence chain, confidence scoring, config comparison, and business-value priority.
    """
    recommendations: list[Recommendation] = []

    for opp in opportunities:
        detections = detections_by_category.get(opp.category, [])
        if not detections:
            continue

        traces_analyzed = len(traces)

        # Build all V2 components
        confidence = compute_confidence(detections, traces_analyzed, observation_days)
        evidence = build_evidence_chain(detections, traces_analyzed, observation_days)
        impact = project_impact(opp, detections, traces)
        config = generate_config_comparison(opp.category, detections, traces)
        priority, bv_score = compute_priority(impact, confidence)

        # Effort estimate based on category
        effort = _estimate_effort(opp.category)

        # Affected models/tools
        affected_models: set[str] = set()
        affected_tools: set[str] = set()
        for d in detections:
            for t in traces:
                if d.trace_id == t.trace_id:
                    affected_models.update(t.unique_models)
                    affected_tools.update(t.unique_tools)
                    break

        rec = Recommendation(
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
            status=RecommendationStatus.PENDING,
            status_history=[{
                "status": "pending",
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "actor": "system",
            }],
            category=opp.category,
            opportunity_id=opp.opportunity_id,
            priority=priority,
            business_value_score=bv_score,
            engineering_effort=effort,
            title=opp.title,
            description=opp.description,
            action_items=_ACTION_ITEMS.get(opp.category, ["Review and optimize."]),
            impact=impact,
            evidence=evidence,
            confidence=confidence,
            config_comparison=config,
            tenant_id=tenant_id,
            affected_task_classes=list({
                t.task_class for t in traces if t.task_class
            }),
            affected_models=sorted(affected_models),
            affected_tools=sorted(affected_tools),
            source_detection_ids=[d.detection_id for d in detections[:20]],
            traces_analyzed=traces_analyzed,
        )
        recommendations.append(rec)

    # Sort by business value score descending
    recommendations.sort(key=lambda r: r.business_value_score, reverse=True)

    logger.info(
        "recommender.generated",
        count=len(recommendations),
        top_priority=recommendations[0].priority.value if recommendations else "none",
    )

    return recommendations


def _estimate_effort(category: WasteCategory) -> str:
    """Rough effort estimate by category."""
    low = {WasteCategory.SERIALIZATION_WASTE, WasteCategory.UNNECESSARY_VERIFICATION}
    high = {WasteCategory.BAD_ROUTING, WasteCategory.CONTEXT_DUPLICATION}
    if category in low:
        return "low"
    if category in high:
        return "high"
    return "medium"
