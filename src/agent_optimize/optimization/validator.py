"""V3 Savings validator — produces SavingsProof from replay experiments and canary data.

The validator ties together the evaluation framework, replay results, and trace data
to produce a proof that savings are real and quality is preserved.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from agent_optimize.evaluation.base import EvalSuite, EvalVerdict
from agent_optimize.evaluation.registry import EvaluatorRegistry
from agent_optimize.models.proof import (
    Canary,
    CanaryCheckpoint,
    CanaryStatus,
    CanaryThresholds,
    MetricSnapshot,
    ProofStatus,
    SavingsProof,
)
from agent_optimize.models.traces import NormalizedTrace
from agent_optimize.models.waste import ConfidenceLevel

logger = structlog.get_logger()


class SavingsValidator:
    """Validates that optimization savings are real and quality is preserved."""

    def __init__(self, evaluator_registry: EvaluatorRegistry) -> None:
        self._evaluators = evaluator_registry

    def validate_from_replay(
        self,
        *,
        recommendation_id: str,
        experiment_id: str,
        baseline_traces: list[NormalizedTrace],
        candidate_traces: list[NormalizedTrace] | None = None,
        baseline_cost: float,
        candidate_cost: float,
        claimed_monthly_savings: float = 0.0,
        observation_days: int = 7,
    ) -> SavingsProof:
        """Validate savings from a replay experiment."""
        # Build metric snapshots
        before = _snapshot_from_traces(baseline_traces)
        after = _snapshot_from_traces(candidate_traces) if candidate_traces else MetricSnapshot()
        after.total_cost = candidate_cost

        # Run evaluation suite
        suite = self._evaluators.run_suite(
            experiment_id=experiment_id,
            config_id="candidate",
            baseline_traces=baseline_traces,
            candidate_traces=candidate_traces,
            baseline_cost=baseline_cost,
            candidate_cost=candidate_cost,
        )

        # Calculate savings
        savings_pct = ((baseline_cost - candidate_cost) / baseline_cost * 100) if baseline_cost > 0 else 0
        monthly_multiplier = 30.0 / observation_days if observation_days > 0 else 1.0
        actual_monthly_savings = (baseline_cost - candidate_cost) * monthly_multiplier
        accuracy = (actual_monthly_savings / claimed_monthly_savings * 100) if claimed_monthly_savings > 0 else 0

        # Quality assessment
        quality_delta = after.success_rate - before.success_rate if candidate_traces else 0.0
        latency_delta = (
            ((after.p95_latency_ms - before.p95_latency_ms) / before.p95_latency_ms * 100)
            if before.p95_latency_ms > 0
            else 0.0
        )

        quality_preserved = suite.fail_count == 0

        # Determine confidence
        traces_analyzed = len(baseline_traces) + (len(candidate_traces) if candidate_traces else 0)
        confidence, confidence_pct = _compute_proof_confidence(
            traces_analyzed, observation_days, suite, savings_pct,
        )

        # Status
        if suite.overall_verdict == EvalVerdict.FAIL:
            status = ProofStatus.REJECTED
            summary = "Savings validation failed. Quality regression detected."
        elif suite.overall_verdict == EvalVerdict.WARN:
            status = ProofStatus.VALIDATED
            summary = f"Savings validated with warnings. {savings_pct:.1f}% cost reduction. Review recommended."
        elif savings_pct > 0 and quality_preserved:
            status = ProofStatus.VALIDATED
            summary = (
                f"Savings validated: {savings_pct:.1f}% cost reduction "
                f"(${actual_monthly_savings:,.2f}/month). Quality preserved."
            )
        else:
            status = ProofStatus.REJECTED
            summary = "Savings not confirmed or candidate is more expensive."

        proof = SavingsProof(
            recommendation_id=recommendation_id,
            experiment_id=experiment_id,
            status=status,
            validated_at=datetime.now(tz=UTC) if status == ProofStatus.VALIDATED else None,
            before=before,
            after=after,
            actual_savings_pct=round(savings_pct, 2),
            actual_monthly_savings=round(actual_monthly_savings, 2),
            claimed_monthly_savings=round(claimed_monthly_savings, 2),
            savings_accuracy_pct=round(accuracy, 1),
            quality_preserved=quality_preserved,
            quality_delta=round(quality_delta, 4),
            latency_delta_pct=round(latency_delta, 1),
            eval_suite=suite,
            eval_verdict=suite.overall_verdict,
            confidence=confidence,
            confidence_pct=round(confidence_pct, 1),
            observation_window_days=observation_days,
            traces_analyzed=traces_analyzed,
            summary=summary,
        )

        logger.info(
            "validator.proof_generated",
            recommendation_id=recommendation_id,
            status=status.value,
            savings_pct=savings_pct,
            quality_preserved=quality_preserved,
            confidence=confidence.value,
        )

        return proof

    def check_canary(
        self,
        *,
        baseline_traces: list[NormalizedTrace],
        canary_traces: list[NormalizedTrace],
        thresholds: CanaryThresholds,
    ) -> CanaryCheckpoint:
        """Evaluate a single canary checkpoint against thresholds."""
        baseline = _snapshot_from_traces(baseline_traces)
        current = _snapshot_from_traces(canary_traces)

        # Compute deltas
        success_delta = current.success_rate - baseline.success_rate
        error_delta = current.error_rate - baseline.error_rate
        latency_delta = (
            ((current.p95_latency_ms - baseline.p95_latency_ms) / baseline.p95_latency_ms * 100)
            if baseline.p95_latency_ms > 0
            else 0.0
        )
        cost_savings = (
            ((baseline.avg_cost_per_trace - current.avg_cost_per_trace) / baseline.avg_cost_per_trace * 100)
            if baseline.avg_cost_per_trace > 0
            else 0.0
        )

        issues: list[str] = []
        healthy = True

        if error_delta > thresholds.max_error_rate_increase:
            issues.append(
                f"Error rate increased by {error_delta:.2%} (max: {thresholds.max_error_rate_increase:.2%})"
            )
            healthy = False

        if latency_delta > thresholds.max_latency_increase_pct:
            issues.append(
                f"P95 latency increased by {latency_delta:.1f}% (max: {thresholds.max_latency_increase_pct}%)"
            )
            healthy = False

        if current.success_rate < thresholds.min_success_rate:
            issues.append(
                f"Success rate {current.success_rate:.2%} below minimum {thresholds.min_success_rate:.2%}"
            )
            healthy = False

        if cost_savings < thresholds.min_cost_savings_pct:
            issues.append(
                f"Cost savings {cost_savings:.1f}% below minimum {thresholds.min_cost_savings_pct}%"
            )

        return CanaryCheckpoint(
            metrics=current,
            baseline_metrics=baseline,
            cost_savings_pct=round(cost_savings, 2),
            success_rate_delta=round(success_delta, 4),
            latency_delta_pct=round(latency_delta, 1),
            error_rate_delta=round(error_delta, 4),
            healthy=healthy,
            issues=issues,
        )


# ---------------------------------------------------------------------------
# Canary manager
# ---------------------------------------------------------------------------


class CanaryManager:
    """Manages canary deployments and their monitoring lifecycle."""

    def __init__(self, validator: SavingsValidator) -> None:
        self._validator = validator
        self._canaries: dict[str, Canary] = {}

    def create_canary(
        self,
        recommendation_id: str,
        experiment_id: str | None = None,
        thresholds: CanaryThresholds | None = None,
        traffic_pct: float = 10.0,
    ) -> Canary:
        canary = Canary(
            recommendation_id=recommendation_id,
            experiment_id=experiment_id,
            thresholds=thresholds or CanaryThresholds(),
            traffic_pct=traffic_pct,
        )
        self._canaries[canary.canary_id] = canary

        logger.info(
            "canary.created",
            canary_id=canary.canary_id,
            recommendation_id=recommendation_id,
            traffic_pct=traffic_pct,
        )
        return canary

    def start_canary(
        self, canary_id: str, baseline_traces: list[NormalizedTrace],
    ) -> Canary:
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")

        canary.status = CanaryStatus.RUNNING
        canary.started_at = datetime.now(tz=UTC)
        canary.baseline_metrics = _snapshot_from_traces(baseline_traces)

        logger.info("canary.started", canary_id=canary_id)
        return canary

    def add_checkpoint(
        self,
        canary_id: str,
        canary_traces: list[NormalizedTrace],
        baseline_traces: list[NormalizedTrace],
    ) -> CanaryCheckpoint:
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")

        checkpoint = self._validator.check_canary(
            baseline_traces=baseline_traces,
            canary_traces=canary_traces,
            thresholds=canary.thresholds,
        )
        canary.checkpoints.append(checkpoint)

        # Update canary status based on checkpoint
        if not checkpoint.healthy:
            canary.status = CanaryStatus.REGRESSED
            canary.final_verdict = EvalVerdict.FAIL
            canary.final_summary = f"Regression detected: {'; '.join(checkpoint.issues)}"
            logger.warning("canary.regressed", canary_id=canary_id, issues=checkpoint.issues)
        elif checkpoint.issues:
            canary.status = CanaryStatus.DEGRADED
            logger.info("canary.degraded", canary_id=canary_id, issues=checkpoint.issues)
        else:
            canary.status = CanaryStatus.HEALTHY

        return checkpoint

    def complete_canary(self, canary_id: str) -> Canary:
        canary = self._canaries.get(canary_id)
        if not canary:
            raise ValueError(f"Canary {canary_id} not found")

        if canary.status in (CanaryStatus.HEALTHY, CanaryStatus.DEGRADED):
            canary.status = CanaryStatus.COMPLETED
            canary.completed_at = datetime.now(tz=UTC)

            healthy_checks = sum(1 for c in canary.checkpoints if c.healthy)
            total_checks = len(canary.checkpoints)

            canary.final_verdict = (
                EvalVerdict.PASS if healthy_checks == total_checks
                else EvalVerdict.WARN
            )
            canary.final_summary = (
                f"Canary completed: {healthy_checks}/{total_checks} healthy checkpoints."
            )
        elif canary.status == CanaryStatus.REGRESSED:
            canary.status = CanaryStatus.ROLLED_BACK
            canary.completed_at = datetime.now(tz=UTC)

        return canary

    def get_canary(self, canary_id: str) -> Canary | None:
        return self._canaries.get(canary_id)

    def list_canaries(self) -> list[Canary]:
        return list(self._canaries.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot_from_traces(traces: list[NormalizedTrace]) -> MetricSnapshot:
    if not traces:
        return MetricSnapshot()

    total_cost = sum(t.total_cost for t in traces)
    successes = sum(1 for t in traces if t.success)
    durations = sorted(t.duration_ms for t in traces if t.duration_ms > 0)

    p50 = durations[len(durations) // 2] if durations else 0.0
    p95 = durations[int(len(durations) * 0.95)] if durations else 0.0

    return MetricSnapshot(
        total_cost=round(total_cost, 4),
        avg_cost_per_trace=round(total_cost / len(traces), 6),
        success_rate=round(successes / len(traces), 4),
        p50_latency_ms=round(p50, 1),
        p95_latency_ms=round(p95, 1),
        error_rate=round(1 - successes / len(traces), 4),
        traces_count=len(traces),
    )


def _compute_proof_confidence(
    traces_analyzed: int,
    observation_days: int,
    suite: EvalSuite,
    savings_pct: float,
) -> tuple[ConfidenceLevel, float]:
    """Compute confidence in a savings proof."""
    score = 0.0

    # Sample size (0-30)
    if traces_analyzed >= 5000:
        score += 30
    elif traces_analyzed >= 1000:
        score += 25
    elif traces_analyzed >= 200:
        score += 15
    elif traces_analyzed >= 50:
        score += 8

    # Observation window (0-25)
    score += min(25, observation_days / 14.0 * 25)

    # Evaluation pass rate (0-30)
    total_evals = suite.pass_count + suite.fail_count + suite.warn_count
    if total_evals > 0:
        pass_rate = suite.pass_count / total_evals
        score += pass_rate * 30

    # Savings magnitude bonus (0-15) — bigger savings are easier to validate
    if savings_pct >= 30:
        score += 15
    elif savings_pct >= 15:
        score += 10
    elif savings_pct >= 5:
        score += 5

    if score >= 80:
        level = ConfidenceLevel.HIGH
    elif score >= 50:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW

    return level, score
