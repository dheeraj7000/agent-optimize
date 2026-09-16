"""Evaluator registry — runs all configured evaluators and produces an EvalSuite."""

from __future__ import annotations

import time

import structlog

from agent_optimize.evaluation.base import BaseEvaluator, EvalResult, EvalSuite
from agent_optimize.evaluation.evaluators import (
    CostBoundsEvaluator,
    ErrorRateEvaluator,
    LatencySLAEvaluator,
    ModelBasedEvaluator,
    StatisticalQualityEvaluator,
    SuccessRateEvaluator,
)

logger = structlog.get_logger()


class EvaluatorRegistry:
    """Manages and runs quality evaluators."""

    def __init__(self) -> None:
        self._evaluators: list[BaseEvaluator] = []

    def register(self, evaluator: BaseEvaluator) -> None:
        self._evaluators.append(evaluator)

    def list_evaluators(self) -> list[dict]:
        return [
            {"name": e.name, "version": e.version, "description": e.description}
            for e in self._evaluators
        ]

    def run_suite(
        self,
        *,
        experiment_id: str = "",
        config_id: str = "",
        baseline_traces: list,
        candidate_traces: list | None = None,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalSuite:
        """Run all evaluators and return an aggregated suite."""
        start = time.monotonic()
        results: list[EvalResult] = []

        for evaluator in self._evaluators:
            try:
                result = evaluator.evaluate(
                    baseline_traces=baseline_traces,
                    candidate_traces=candidate_traces,
                    baseline_cost=baseline_cost,
                    candidate_cost=candidate_cost,
                    metadata=metadata,
                )
                results.append(result)
            except Exception:
                logger.exception("evaluator.error", evaluator=evaluator.name)
                results.append(EvalResult(
                    evaluator_name=evaluator.name,
                    verdict="skip",
                    message="Evaluator raised an exception",
                ))

        duration = (time.monotonic() - start) * 1000

        suite = EvalSuite(
            experiment_id=experiment_id,
            config_id=config_id,
            results=results,
            duration_ms=round(duration, 2),
        )
        suite.recompute()

        logger.info(
            "evaluator_registry.suite_complete",
            experiment_id=experiment_id,
            pass_count=suite.pass_count,
            fail_count=suite.fail_count,
            warn_count=suite.warn_count,
            verdict=suite.overall_verdict.value,
        )

        return suite


def create_default_evaluator_registry() -> EvaluatorRegistry:
    """Create a registry with all built-in evaluators."""
    registry = EvaluatorRegistry()
    registry.register(SuccessRateEvaluator())
    registry.register(LatencySLAEvaluator())
    registry.register(CostBoundsEvaluator())
    registry.register(ErrorRateEvaluator())
    registry.register(StatisticalQualityEvaluator())
    registry.register(ModelBasedEvaluator())  # Unconfigured stub
    return registry
