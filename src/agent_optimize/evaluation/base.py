"""Base evaluator and result models.

Quality is the guardrail. A cheap failed outcome is not an optimization.
Every proposed change must be evaluated against quality, latency, reliability,
risk, and cost — not cost alone.
"""

from __future__ import annotations

import abc
import enum
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class EvalVerdict(str, enum.Enum):
    """Whether an evaluation passed, failed, or is inconclusive."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"  # Marginal — human review recommended
    SKIP = "skip"  # Could not evaluate (missing data)


class EvalResult(BaseModel):
    """Result of a single evaluator run against one trace or a batch."""

    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evaluator_name: str = ""
    verdict: EvalVerdict = EvalVerdict.SKIP
    score: float | None = None  # 0.0-1.0 where applicable
    threshold: float | None = None  # The pass/fail threshold used
    message: str = ""
    details: dict = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class EvalSuite(BaseModel):
    """Aggregated results from running all evaluators on a replay experiment."""

    suite_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str = ""
    config_id: str = ""

    results: list[EvalResult] = Field(default_factory=list)

    # Aggregate
    pass_count: int = 0
    fail_count: int = 0
    warn_count: int = 0
    overall_verdict: EvalVerdict = EvalVerdict.SKIP

    # Timing
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    duration_ms: float = 0.0

    def recompute(self) -> None:
        self.pass_count = sum(1 for r in self.results if r.verdict == EvalVerdict.PASS)
        self.fail_count = sum(1 for r in self.results if r.verdict == EvalVerdict.FAIL)
        self.warn_count = sum(1 for r in self.results if r.verdict == EvalVerdict.WARN)

        if self.fail_count > 0:
            self.overall_verdict = EvalVerdict.FAIL
        elif self.warn_count > 0:
            self.overall_verdict = EvalVerdict.WARN
        elif self.pass_count > 0:
            self.overall_verdict = EvalVerdict.PASS
        else:
            self.overall_verdict = EvalVerdict.SKIP


class BaseEvaluator(abc.ABC):
    """Abstract base for quality evaluators.

    Evaluators are the hard guardrails for cost optimization. They answer:
    did the optimization preserve quality, latency, reliability, and safety?
    """

    name: str = "base"
    version: str = "0.1.0"
    description: str = ""

    @abc.abstractmethod
    def evaluate(
        self,
        baseline_traces: list,
        candidate_traces: list | None = None,
        *,
        baseline_cost: float = 0.0,
        candidate_cost: float = 0.0,
        metadata: dict | None = None,
    ) -> EvalResult:
        """Evaluate quality comparing baseline to candidate."""
        ...
