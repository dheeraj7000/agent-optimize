"""Tests for V3 quality evaluators — the guardrails for every optimization."""

from agent_optimize.evaluation.base import EvalVerdict
from agent_optimize.evaluation.evaluators import (
    CostBoundsEvaluator,
    ErrorRateEvaluator,
    LatencySLAEvaluator,
    ModelBasedEvaluator,
    StatisticalQualityEvaluator,
    SuccessRateEvaluator,
)
from agent_optimize.evaluation.registry import create_default_evaluator_registry


class MockTrace:
    def __init__(self, success=True, duration_ms=1000.0, total_cost=0.05):
        self.success = success
        self.duration_ms = duration_ms
        self.total_cost = total_cost


class TestSuccessRateEvaluator:
    def test_pass_when_rate_above_threshold(self):
        evaluator = SuccessRateEvaluator(min_success_rate=0.90)
        baseline = [MockTrace(success=True) for _ in range(100)]
        result = evaluator.evaluate(baseline)
        assert result.verdict == EvalVerdict.PASS

    def test_fail_when_candidate_regresses(self):
        evaluator = SuccessRateEvaluator(max_regression=0.02)
        baseline = [MockTrace(success=True) for _ in range(100)]
        # 5% failure rate = 5% regression
        candidate = [MockTrace(success=(i % 20 != 0)) for i in range(100)]
        result = evaluator.evaluate(baseline, candidate)
        assert result.verdict == EvalVerdict.FAIL

    def test_warn_on_minor_regression(self):
        evaluator = SuccessRateEvaluator(max_regression=0.05)
        baseline = [MockTrace(success=True) for _ in range(100)]
        # 1% failure
        candidate = [MockTrace(success=(i != 0)) for i in range(100)]
        result = evaluator.evaluate(baseline, candidate)
        assert result.verdict == EvalVerdict.WARN


class TestLatencySLAEvaluator:
    def test_pass_within_sla(self):
        evaluator = LatencySLAEvaluator(max_p95_ms=5000)
        traces = [MockTrace(duration_ms=1000) for _ in range(100)]
        result = evaluator.evaluate(traces)
        assert result.verdict == EvalVerdict.PASS

    def test_fail_exceeds_sla(self):
        evaluator = LatencySLAEvaluator(max_p95_ms=500)
        traces = [MockTrace(duration_ms=1000) for _ in range(100)]
        result = evaluator.evaluate(traces)
        assert result.verdict == EvalVerdict.FAIL


class TestCostBoundsEvaluator:
    def test_pass_with_savings(self):
        evaluator = CostBoundsEvaluator(min_savings_pct=5.0)
        result = evaluator.evaluate([], baseline_cost=10.0, candidate_cost=8.0)
        assert result.verdict == EvalVerdict.PASS
        assert result.details["savings_pct"] == 20.0

    def test_fail_when_more_expensive(self):
        evaluator = CostBoundsEvaluator()
        result = evaluator.evaluate([], baseline_cost=10.0, candidate_cost=12.0)
        assert result.verdict == EvalVerdict.FAIL

    def test_warn_on_small_savings(self):
        evaluator = CostBoundsEvaluator(min_savings_pct=10.0)
        result = evaluator.evaluate([], baseline_cost=10.0, candidate_cost=9.5)
        assert result.verdict == EvalVerdict.WARN


class TestErrorRateEvaluator:
    def test_pass_low_error_rate(self):
        evaluator = ErrorRateEvaluator(max_error_rate=0.05)
        baseline = [MockTrace(success=True) for _ in range(100)]
        candidate = [MockTrace(success=True) for _ in range(100)]
        result = evaluator.evaluate(baseline, candidate)
        assert result.verdict == EvalVerdict.PASS

    def test_fail_high_error_rate(self):
        evaluator = ErrorRateEvaluator(max_error_rate=0.03)
        baseline = [MockTrace(success=True) for _ in range(100)]
        candidate = [MockTrace(success=(i % 10 != 0)) for i in range(100)]
        result = evaluator.evaluate(baseline, candidate)
        assert result.verdict == EvalVerdict.FAIL


class TestStatisticalQualityEvaluator:
    def test_skip_insufficient_samples(self):
        evaluator = StatisticalQualityEvaluator(min_sample_size=30)
        result = evaluator.evaluate([MockTrace()] * 10, [MockTrace()] * 10)
        assert result.verdict == EvalVerdict.WARN

    def test_pass_no_regression(self):
        evaluator = StatisticalQualityEvaluator(min_sample_size=30)
        baseline = [MockTrace(success=True) for _ in range(100)]
        candidate = [MockTrace(success=True) for _ in range(100)]
        result = evaluator.evaluate(baseline, candidate)
        assert result.verdict == EvalVerdict.PASS

    def test_fail_significant_regression(self):
        evaluator = StatisticalQualityEvaluator(min_sample_size=30)
        baseline = [MockTrace(success=True) for _ in range(200)]
        # 15% failure rate — clearly significant
        candidate = [MockTrace(success=(i % 7 != 0)) for i in range(200)]
        result = evaluator.evaluate(baseline, candidate)
        assert result.verdict == EvalVerdict.FAIL
        assert result.details["significant"] is True


class TestModelBasedEvaluator:
    def test_skip_when_unconfigured(self):
        evaluator = ModelBasedEvaluator()
        result = evaluator.evaluate([])
        assert result.verdict == EvalVerdict.SKIP


class TestEvaluatorRegistry:
    def test_default_registry_has_6_evaluators(self):
        registry = create_default_evaluator_registry()
        assert len(registry.list_evaluators()) == 6

    def test_run_suite_aggregates_verdicts(self):
        registry = create_default_evaluator_registry()
        baseline = [MockTrace() for _ in range(50)]
        suite = registry.run_suite(
            baseline_traces=baseline,
            baseline_cost=5.0,
            candidate_cost=3.0,
        )
        assert suite.pass_count + suite.fail_count + suite.warn_count + \
               len([r for r in suite.results if r.verdict == EvalVerdict.SKIP]) == len(suite.results)
        assert suite.overall_verdict in (EvalVerdict.PASS, EvalVerdict.FAIL, EvalVerdict.WARN, EvalVerdict.SKIP)
