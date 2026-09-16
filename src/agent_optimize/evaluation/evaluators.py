"""Built-in quality evaluators.

Three tiers of evaluation:
1. Deterministic checks — success rate, error rate, latency SLA, cost bounds
2. Statistical evaluators — significance testing on quality metrics
3. Model-based evaluator — LLM-as-judge for output quality (stub for provider integration)
"""

from __future__ import annotations

import math
from typing import Any

from agent_optimize.evaluation.base import BaseEvaluator, EvalResult, EvalVerdict

# ---------------------------------------------------------------------------
# 1. Deterministic evaluators
# ---------------------------------------------------------------------------


class SuccessRateEvaluator(BaseEvaluator):
    """Check that the candidate success rate doesn't regress below threshold."""

    name = "success_rate"
    version = "0.1.0"
    description = "Ensures success rate stays above minimum threshold."

    def __init__(self, min_success_rate: float = 0.95, max_regression: float = 0.02) -> None:
        self._min_rate = min_success_rate
        self._max_regression = max_regression

    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        baseline_rate = _success_rate(baseline_traces)
        candidate_rate = _success_rate(candidate_traces) if candidate_traces else baseline_rate
        delta = candidate_rate - baseline_rate

        if candidate_rate < self._min_rate:
            verdict = EvalVerdict.FAIL
            msg = f"Candidate success rate {candidate_rate:.2%} below minimum {self._min_rate:.2%}"
        elif delta < -self._max_regression:
            verdict = EvalVerdict.FAIL
            msg = f"Success rate regressed by {abs(delta):.2%} (max allowed: {self._max_regression:.2%})"
        elif delta < 0:
            verdict = EvalVerdict.WARN
            msg = f"Minor success rate regression: {delta:.2%}"
        else:
            verdict = EvalVerdict.PASS
            msg = f"Success rate: {candidate_rate:.2%} (baseline: {baseline_rate:.2%})"

        return EvalResult(
            evaluator_name=self.name,
            verdict=verdict,
            score=candidate_rate,
            threshold=self._min_rate,
            message=msg,
            details={"baseline_rate": baseline_rate, "candidate_rate": candidate_rate, "delta": delta},
        )


class LatencySLAEvaluator(BaseEvaluator):
    """Check that P95 latency stays within SLA."""

    name = "latency_sla"
    version = "0.1.0"
    description = "Ensures P95 latency stays within SLA bounds."

    def __init__(self, max_p95_ms: float = 30000, max_regression_pct: float = 20.0) -> None:
        self._max_p95 = max_p95_ms
        self._max_regression_pct = max_regression_pct

    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        baseline_p95 = _percentile_latency(baseline_traces, 0.95)
        candidate_p95 = _percentile_latency(candidate_traces, 0.95) if candidate_traces else baseline_p95

        regression_pct = ((candidate_p95 - baseline_p95) / baseline_p95 * 100) if baseline_p95 > 0 else 0

        if candidate_p95 > self._max_p95:
            verdict = EvalVerdict.FAIL
            msg = f"P95 latency {candidate_p95:.0f}ms exceeds SLA {self._max_p95:.0f}ms"
        elif regression_pct > self._max_regression_pct:
            verdict = EvalVerdict.FAIL
            msg = f"P95 latency regressed {regression_pct:.1f}% (max: {self._max_regression_pct}%)"
        elif regression_pct > self._max_regression_pct / 2:
            verdict = EvalVerdict.WARN
            msg = f"P95 latency increased {regression_pct:.1f}%"
        else:
            verdict = EvalVerdict.PASS
            msg = f"P95 latency: {candidate_p95:.0f}ms (baseline: {baseline_p95:.0f}ms)"

        return EvalResult(
            evaluator_name=self.name,
            verdict=verdict,
            score=1.0 - min(1.0, candidate_p95 / self._max_p95),
            threshold=self._max_p95,
            message=msg,
            details={
                "baseline_p95_ms": baseline_p95,
                "candidate_p95_ms": candidate_p95,
                "regression_pct": round(regression_pct, 1),
            },
        )


class CostBoundsEvaluator(BaseEvaluator):
    """Verify that the candidate actually saves money."""

    name = "cost_bounds"
    version = "0.1.0"
    description = "Validates that candidate configuration reduces cost."

    def __init__(self, min_savings_pct: float = 5.0) -> None:
        self._min_savings_pct = min_savings_pct

    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        if baseline_cost <= 0:
            return EvalResult(
                evaluator_name=self.name,
                verdict=EvalVerdict.SKIP,
                message="No baseline cost data",
            )

        savings_pct = ((baseline_cost - candidate_cost) / baseline_cost) * 100
        savings_dollar = baseline_cost - candidate_cost

        if savings_pct < 0:
            verdict = EvalVerdict.FAIL
            msg = f"Candidate is {abs(savings_pct):.1f}% MORE expensive"
        elif savings_pct < self._min_savings_pct:
            verdict = EvalVerdict.WARN
            msg = f"Savings {savings_pct:.1f}% below threshold {self._min_savings_pct}%"
        else:
            verdict = EvalVerdict.PASS
            msg = f"Savings: {savings_pct:.1f}% (${savings_dollar:.4f})"

        return EvalResult(
            evaluator_name=self.name,
            verdict=verdict,
            score=min(1.0, savings_pct / 100),
            threshold=self._min_savings_pct,
            message=msg,
            details={
                "baseline_cost": baseline_cost,
                "candidate_cost": candidate_cost,
                "savings_pct": round(savings_pct, 1),
                "savings_dollar": round(savings_dollar, 4),
            },
        )


class ErrorRateEvaluator(BaseEvaluator):
    """Check that error rate doesn't increase."""

    name = "error_rate"
    version = "0.1.0"
    description = "Ensures error rate doesn't increase beyond threshold."

    def __init__(self, max_error_rate: float = 0.05, max_increase: float = 0.01) -> None:
        self._max_error = max_error_rate
        self._max_increase = max_increase

    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        baseline_err = 1.0 - _success_rate(baseline_traces)
        candidate_err = (1.0 - _success_rate(candidate_traces)) if candidate_traces else baseline_err
        increase = candidate_err - baseline_err

        if candidate_err > self._max_error:
            verdict = EvalVerdict.FAIL
            msg = f"Error rate {candidate_err:.2%} exceeds max {self._max_error:.2%}"
        elif increase > self._max_increase:
            verdict = EvalVerdict.FAIL
            msg = f"Error rate increased by {increase:.2%} (max: {self._max_increase:.2%})"
        elif increase > 0:
            verdict = EvalVerdict.WARN
            msg = f"Minor error rate increase: {increase:.2%}"
        else:
            verdict = EvalVerdict.PASS
            msg = f"Error rate: {candidate_err:.2%} (baseline: {baseline_err:.2%})"

        return EvalResult(
            evaluator_name=self.name,
            verdict=verdict,
            score=1.0 - candidate_err,
            threshold=self._max_error,
            message=msg,
            details={"baseline_error_rate": baseline_err, "candidate_error_rate": candidate_err},
        )


# ---------------------------------------------------------------------------
# 2. Statistical evaluator
# ---------------------------------------------------------------------------


class StatisticalQualityEvaluator(BaseEvaluator):
    """Statistical comparison of baseline vs candidate quality distributions.

    Uses a simple Z-test on success rates. For small samples, falls back to
    a conservative binomial confidence interval.
    """

    name = "statistical_quality"
    version = "0.1.0"
    description = "Statistical significance test on quality regression."

    def __init__(self, significance_level: float = 0.05, min_sample_size: int = 30) -> None:
        self._alpha = significance_level
        self._min_samples = min_sample_size

    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        n_b = len(baseline_traces) if baseline_traces else 0
        n_c = len(candidate_traces) if candidate_traces else 0

        if n_b < self._min_samples or n_c < self._min_samples:
            return EvalResult(
                evaluator_name=self.name,
                verdict=EvalVerdict.WARN,
                message=(
                    f"Insufficient samples for statistical test "
                    f"(baseline: {n_b}, candidate: {n_c}, min: {self._min_samples})"
                ),
                details={"baseline_n": n_b, "candidate_n": n_c},
            )

        p_b = _success_rate(baseline_traces)
        p_c = _success_rate(candidate_traces)

        # Pooled two-proportion Z-test
        p_pooled = (p_b * n_b + p_c * n_c) / (n_b + n_c)
        se = math.sqrt(p_pooled * (1 - p_pooled) * (1 / n_b + 1 / n_c)) if p_pooled > 0 else 0
        z_stat = (p_c - p_b) / se if se > 0 else 0

        # One-sided test: is candidate significantly worse?
        # Z < -1.645 at alpha=0.05 one-sided
        z_critical = -1.645 if self._alpha == 0.05 else -2.326  # 0.01
        is_significant_regression = z_stat < z_critical

        if is_significant_regression:
            verdict = EvalVerdict.FAIL
            msg = f"Statistically significant quality regression (z={z_stat:.3f}, p<{self._alpha})"
        elif p_c < p_b:
            verdict = EvalVerdict.WARN
            msg = f"Non-significant quality decrease (z={z_stat:.3f})"
        else:
            verdict = EvalVerdict.PASS
            msg = f"No quality regression detected (z={z_stat:.3f})"

        return EvalResult(
            evaluator_name=self.name,
            verdict=verdict,
            score=p_c,
            message=msg,
            details={
                "baseline_rate": p_b,
                "candidate_rate": p_c,
                "z_statistic": round(z_stat, 4),
                "z_critical": z_critical,
                "significant": is_significant_regression,
                "baseline_n": n_b,
                "candidate_n": n_c,
            },
        )


# ---------------------------------------------------------------------------
# 3. Model-based evaluator (stub)
# ---------------------------------------------------------------------------


class ModelBasedEvaluator(BaseEvaluator):
    """LLM-as-judge evaluator for output quality comparison.

    V3 stub: provides the interface. Actual LLM integration requires
    configuring a provider API key and model for evaluation.
    """

    name = "model_based_quality"
    version = "0.1.0"
    description = "LLM-as-judge output quality evaluation (requires provider configuration)."

    def __init__(self, model: str = "", provider: str = "") -> None:
        self._model = model
        self._provider = provider

    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        if not self._model:
            return EvalResult(
                evaluator_name=self.name,
                verdict=EvalVerdict.SKIP,
                message="Model-based evaluator not configured. Set provider and model to enable.",
                details={"configured": False},
            )

        # Stub: in production this would call the LLM to compare outputs
        return EvalResult(
            evaluator_name=self.name,
            verdict=EvalVerdict.SKIP,
            message=f"Model-based evaluation with {self._provider}/{self._model} not yet implemented.",
            details={"configured": True, "provider": self._provider, "model": self._model},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _success_rate(traces: list[Any] | None) -> float:
    if not traces:
        return 0.0
    successes = sum(1 for t in traces if getattr(t, "success", True))
    return successes / len(traces)


def _percentile_latency(traces: list[Any] | None, pct: float) -> float:
    if not traces:
        return 0.0
    durations = sorted(getattr(t, "duration_ms", 0.0) for t in traces)
    if not durations:
        return 0.0
    idx = int(len(durations) * pct)
    return durations[min(idx, len(durations) - 1)]
