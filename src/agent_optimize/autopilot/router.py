"""Dynamic model router — routes requests to optimal model tier based on complexity/risk.

The router classifies incoming workloads by complexity and risk, then selects
the cheapest model that meets quality constraints for that tier:

    LOW complexity    → small model  (flash/haiku/mini)
    MEDIUM complexity → standard model (gpt-4o/sonnet)
    HIGH complexity   → frontier model (o1/opus)
    HIGH + HIGH risk  → frontier + verification
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ComplexityTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RoutingDecision(BaseModel):
    """The result of a model routing decision."""

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    # Classification
    complexity: ComplexityTier = ComplexityTier.MEDIUM
    risk: RiskTier = RiskTier.LOW

    # Decision
    selected_model: str = ""
    original_model: str = ""
    requires_verification: bool = False

    # Rationale
    reason: str = ""
    estimated_cost_savings: float = 0.0
    estimated_quality_delta: float = 0.0

    # Input features used
    input_tokens: int = 0
    output_tokens_estimate: int = 0
    task_class: str | None = None


# Default routing table
_DEFAULT_ROUTING: dict[ComplexityTier, str] = {
    ComplexityTier.LOW: "gpt-4o-mini",
    ComplexityTier.MEDIUM: "gpt-4o",
    ComplexityTier.HIGH: "o1",
}

# Complexity thresholds (based on historical analysis patterns)
_COMPLEXITY_THRESHOLDS = {
    "low_max_input_tokens": 2000,
    "low_max_output_tokens": 300,
    "medium_max_input_tokens": 8000,
    "medium_max_output_tokens": 1500,
    # Above medium → high
}


class ModelRouter:
    """Routes requests to the optimal model based on complexity and risk classification.

    The router learns from historical traces which model tier handles each task class
    most cost-effectively while meeting quality constraints.
    """

    def __init__(
        self,
        routing_table: dict[str, str] | None = None,
        complexity_thresholds: dict[str, int] | None = None,
    ) -> None:
        self._routing: dict[ComplexityTier, str] = {}
        if routing_table:
            for tier_str, model in routing_table.items():
                self._routing[ComplexityTier(tier_str)] = model
        else:
            self._routing = dict(_DEFAULT_ROUTING)

        self._thresholds = complexity_thresholds or dict(_COMPLEXITY_THRESHOLDS)

        # Learned task-class overrides (populated from historical analysis)
        self._task_class_routing: dict[str, ComplexityTier] = {}

        # Performance tracking
        self._routing_history: list[RoutingDecision] = []

    @property
    def routing_table(self) -> dict[str, str]:
        return {tier.value: model for tier, model in self._routing.items()}

    def classify_complexity(
        self,
        *,
        input_tokens: int = 0,
        output_tokens_estimate: int = 0,
        task_class: str | None = None,
    ) -> ComplexityTier:
        """Classify workload complexity from observable features."""
        # Check learned task-class override first
        if task_class and task_class in self._task_class_routing:
            return self._task_class_routing[task_class]

        # Token-based heuristic classification
        low_in = self._thresholds.get("low_max_input_tokens", 2000)
        low_out = self._thresholds.get("low_max_output_tokens", 300)
        med_in = self._thresholds.get("medium_max_input_tokens", 8000)
        med_out = self._thresholds.get("medium_max_output_tokens", 1500)

        if input_tokens <= low_in and output_tokens_estimate <= low_out:
            return ComplexityTier.LOW
        if input_tokens <= med_in and output_tokens_estimate <= med_out:
            return ComplexityTier.MEDIUM
        return ComplexityTier.HIGH

    def classify_risk(
        self,
        *,
        task_class: str | None = None,
        has_side_effects: bool = False,
        customer_facing: bool = False,
    ) -> RiskTier:
        """Classify workload risk level."""
        if has_side_effects and customer_facing:
            return RiskTier.HIGH
        if has_side_effects or customer_facing:
            return RiskTier.MEDIUM
        return RiskTier.LOW

    def route(
        self,
        *,
        original_model: str = "",
        input_tokens: int = 0,
        output_tokens_estimate: int = 0,
        task_class: str | None = None,
        has_side_effects: bool = False,
        customer_facing: bool = False,
    ) -> RoutingDecision:
        """Make a routing decision for a request."""
        complexity = self.classify_complexity(
            input_tokens=input_tokens,
            output_tokens_estimate=output_tokens_estimate,
            task_class=task_class,
        )
        risk = self.classify_risk(
            task_class=task_class,
            has_side_effects=has_side_effects,
            customer_facing=customer_facing,
        )

        # Select model from routing table
        selected = self._routing.get(complexity, original_model or "gpt-4o")

        # High risk bumps up one tier
        if risk == RiskTier.HIGH and complexity != ComplexityTier.HIGH:
            bumped = {ComplexityTier.LOW: ComplexityTier.MEDIUM, ComplexityTier.MEDIUM: ComplexityTier.HIGH}
            higher_tier = bumped.get(complexity, complexity)
            selected = self._routing.get(higher_tier, selected)

        requires_verification = risk == RiskTier.HIGH

        # Estimate savings (rough: based on model tier difference)
        savings = _estimate_routing_savings(original_model, selected, input_tokens)

        decision = RoutingDecision(
            complexity=complexity,
            risk=risk,
            selected_model=selected,
            original_model=original_model,
            requires_verification=requires_verification,
            reason=f"Complexity: {complexity.value}, Risk: {risk.value} → {selected}",
            estimated_cost_savings=round(savings, 6),
            estimated_quality_delta=0.0 if complexity == ComplexityTier.LOW else -0.002,
            input_tokens=input_tokens,
            output_tokens_estimate=output_tokens_estimate,
            task_class=task_class,
        )

        self._routing_history.append(decision)
        return decision

    def set_routing_table(self, table: dict[str, str]) -> None:
        self._routing = {ComplexityTier(k): v for k, v in table.items()}

    def set_task_class_override(self, task_class: str, tier: str) -> None:
        self._task_class_routing[task_class] = ComplexityTier(tier)

    def get_routing_stats(self) -> dict:
        if not self._routing_history:
            return {"total_routed": 0, "by_complexity": {}, "by_model": {}, "total_savings": 0.0}

        by_complexity: dict[str, int] = {}
        by_model: dict[str, int] = {}
        total_savings = 0.0

        for d in self._routing_history:
            by_complexity[d.complexity.value] = by_complexity.get(d.complexity.value, 0) + 1
            by_model[d.selected_model] = by_model.get(d.selected_model, 0) + 1
            total_savings += d.estimated_cost_savings

        return {
            "total_routed": len(self._routing_history),
            "by_complexity": by_complexity,
            "by_model": by_model,
            "total_savings": round(total_savings, 4),
        }


def _estimate_routing_savings(original: str, selected: str, input_tokens: int) -> float:
    """Rough estimate of cost savings from model routing."""
    # Relative cost tiers (approximate)
    tier: dict[str, float] = {
        "o1": 15.0, "o1-pro": 20.0,
        "gpt-4-turbo": 10.0, "gpt-4": 10.0,
        "claude-opus-4-20250514": 15.0, "claude-3-opus": 15.0,
        "gemini-2.5-pro": 1.25,
        "gpt-4o": 2.5, "claude-sonnet-4-20250514": 3.0,
        "gpt-4o-mini": 0.15, "o1-mini": 1.1,
        "claude-haiku-3-20240307": 0.25,
        "gemini-2.0-flash": 0.1,
    }

    original_cost = tier.get(original, 5.0)
    selected_cost = tier.get(selected, 5.0)

    if original_cost <= selected_cost:
        return 0.0

    # Savings per 1M tokens, scaled to actual usage
    return (original_cost - selected_cost) * (input_tokens / 1_000_000)
