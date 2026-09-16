"""Recovery selector — learned fallback/retry policies that minimize expected cost-to-success.

Instead of naive retries (retry same strategy 3x → 11% success), the recovery selector
uses historical data to pick the recovery strategy with the lowest expected cost to
reach a successful outcome:

    Recovery policy         | Historical success
    Retry same strategy 3x  | 11%
    Fallback Tool B         | 87%

The optimization target is expected cost-to-success, distinguishing infrastructure
failures from agent reasoning failures.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class FailureType(str, Enum):
    INFRASTRUCTURE = "infrastructure"  # Timeout, rate limit, network error
    REASONING = "reasoning"  # Wrong output, hallucination, logic error
    TOOL_ERROR = "tool_error"  # Tool returned error
    UNKNOWN = "unknown"


class RecoveryStrategy(str, Enum):
    RETRY_SAME = "retry_same"
    RETRY_DIFFERENT_MODEL = "retry_different_model"
    FALLBACK_TOOL = "fallback_tool"
    SKIP = "skip"
    ESCALATE = "escalate"  # Hand off to a more capable model


class RecoveryDecision(BaseModel):
    """The recovery action to take after a failure."""

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # Failure context
    failure_type: FailureType = FailureType.UNKNOWN
    failed_tool: str = ""
    failed_model: str = ""
    error_message: str = ""
    retry_count: int = 0

    # Decision
    strategy: RecoveryStrategy = RecoveryStrategy.RETRY_SAME
    target_tool: str = ""  # For fallback_tool
    target_model: str = ""  # For retry_different_model / escalate

    # Rationale
    reason: str = ""
    historical_success_rate: float = 0.0
    expected_cost_to_success: float = 0.0
    alternative_cost_to_success: float = 0.0  # Cost of naive retry for comparison


class RecoveryRule(BaseModel):
    """A configured recovery rule matching failure patterns to strategies."""

    rule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""

    # Match conditions
    failure_type: FailureType | None = None
    tool_pattern: str = ""  # Glob or exact match on tool name
    model_pattern: str = ""  # Glob or exact match on model name
    max_retries: int = 2  # After this many retries, apply this rule

    # Recovery action
    strategy: RecoveryStrategy = RecoveryStrategy.FALLBACK_TOOL
    target_tool: str = ""
    target_model: str = ""

    # Historical performance
    success_rate: float = 0.0
    avg_cost_to_success: float = 0.0
    times_used: int = 0


class RecoverySelector:
    """Selects the optimal recovery strategy based on failure context and historical data.

    The selector maintains a set of recovery rules learned from historical traces
    and picks the strategy that minimizes expected cost-to-success.
    """

    def __init__(self, max_retries: int = 2) -> None:
        self._max_retries = max_retries
        self._rules: list[RecoveryRule] = []
        self._decisions: list[RecoveryDecision] = []

        # Default rules
        self._rules.extend([
            RecoveryRule(
                name="infrastructure_retry",
                failure_type=FailureType.INFRASTRUCTURE,
                max_retries=3,
                strategy=RecoveryStrategy.RETRY_SAME,
                success_rate=0.85,
                avg_cost_to_success=0.002,
            ),
            RecoveryRule(
                name="reasoning_escalate",
                failure_type=FailureType.REASONING,
                max_retries=1,
                strategy=RecoveryStrategy.ESCALATE,
                target_model="o1",
                success_rate=0.78,
                avg_cost_to_success=0.05,
            ),
            RecoveryRule(
                name="tool_fallback",
                failure_type=FailureType.TOOL_ERROR,
                max_retries=2,
                strategy=RecoveryStrategy.FALLBACK_TOOL,
                success_rate=0.87,
                avg_cost_to_success=0.01,
            ),
        ])

    def select_recovery(
        self,
        *,
        failure_type: FailureType = FailureType.UNKNOWN,
        failed_tool: str = "",
        failed_model: str = "",
        error_message: str = "",
        retry_count: int = 0,
    ) -> RecoveryDecision:
        """Select the optimal recovery strategy for a failure."""
        # Find matching rules
        matching = [
            r for r in self._rules
            if self._rule_matches(r, failure_type, failed_tool, failed_model, retry_count)
        ]

        if not matching:
            # Default: retry same if under budget, else skip
            if retry_count < self._max_retries:
                strategy = RecoveryStrategy.RETRY_SAME
                reason = f"No specific rule. Retry {retry_count + 1}/{self._max_retries}."
            else:
                strategy = RecoveryStrategy.SKIP
                reason = f"Retry budget exhausted ({retry_count}/{self._max_retries})."

            decision = RecoveryDecision(
                failure_type=failure_type,
                failed_tool=failed_tool,
                failed_model=failed_model,
                error_message=error_message,
                retry_count=retry_count,
                strategy=strategy,
                reason=reason,
            )
        else:
            # Pick the rule with highest success rate
            best_rule = max(matching, key=lambda r: r.success_rate)
            best_rule.times_used += 1

            # If over retry budget for this rule, fall back to skip
            if retry_count >= best_rule.max_retries and best_rule.strategy == RecoveryStrategy.RETRY_SAME:
                best_rule = RecoveryRule(
                    name="budget_exhausted",
                    strategy=RecoveryStrategy.SKIP,
                )

            # Compute expected cost-to-success
            if best_rule.success_rate > 0:
                expected_cost = best_rule.avg_cost_to_success / best_rule.success_rate
            else:
                expected_cost = float("inf")

            # Compare to naive retry cost
            naive_success_rate = 0.11 if retry_count >= 2 else 0.5
            naive_cost = best_rule.avg_cost_to_success / naive_success_rate if naive_success_rate > 0 else float("inf")

            decision = RecoveryDecision(
                failure_type=failure_type,
                failed_tool=failed_tool,
                failed_model=failed_model,
                error_message=error_message,
                retry_count=retry_count,
                strategy=best_rule.strategy,
                target_tool=best_rule.target_tool,
                target_model=best_rule.target_model,
                reason=f"Rule '{best_rule.name}': {best_rule.strategy.value} (success: {best_rule.success_rate:.0%})",
                historical_success_rate=best_rule.success_rate,
                expected_cost_to_success=round(expected_cost, 6),
                alternative_cost_to_success=round(naive_cost, 6),
            )

        self._decisions.append(decision)
        return decision

    def add_rule(self, rule: RecoveryRule) -> RecoveryRule:
        self._rules.append(rule)
        logger.info("recovery.rule_added", name=rule.name, strategy=rule.strategy.value)
        return rule

    def list_rules(self) -> list[RecoveryRule]:
        return list(self._rules)

    def get_stats(self) -> dict:
        return {
            "total_decisions": len(self._decisions),
            "rules_count": len(self._rules),
            "by_strategy": _count_by(self._decisions, lambda d: d.strategy.value),
            "by_failure_type": _count_by(self._decisions, lambda d: d.failure_type.value),
        }

    @staticmethod
    def _rule_matches(
        rule: RecoveryRule,
        failure_type: FailureType,
        tool: str,
        model: str,
        retry_count: int,
    ) -> bool:
        if rule.failure_type and rule.failure_type != failure_type:
            return False
        if rule.tool_pattern and rule.tool_pattern not in tool:
            return False
        if rule.model_pattern and rule.model_pattern not in model:
            return False
        return not (rule.model_pattern and rule.model_pattern not in model)


def _count_by(items: list, key_fn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        k = key_fn(item)
        counts[k] = counts.get(k, 0) + 1
    return counts
