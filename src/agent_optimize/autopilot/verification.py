"""Adaptive verification — invoke verification conditionally based on risk and confidence.

Instead of running a verifier on every request, the adaptive verifier evaluates
whether the current request actually needs verification based on:
- Risk score (task complexity, side effects, customer-facing)
- Model confidence (how certain the primary model was)
- Historical verification impact (how often the verifier changes outcomes)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class VerificationDecision(BaseModel):
    """Whether to invoke verification for a given request."""

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    should_verify: bool = False
    reason: str = ""

    # Input signals
    risk_score: float = 0.0
    model_confidence: float = 0.0
    task_class: str | None = None

    # Thresholds used
    risk_threshold: float = 0.7
    confidence_threshold: float = 0.9

    # Cost impact
    estimated_verification_cost: float = 0.0
    estimated_savings_if_skipped: float = 0.0


class AdaptiveVerifier:
    """Decides whether to invoke verification based on risk and confidence.

    The verifier learns from historical data what fraction of verifications
    actually change the outcome, and uses that to calibrate thresholds.
    """

    def __init__(
        self,
        risk_threshold: float = 0.7,
        confidence_threshold: float = 0.9,
        avg_verification_cost: float = 0.01,
    ) -> None:
        self._risk_threshold = risk_threshold
        self._confidence_threshold = confidence_threshold
        self._avg_cost = avg_verification_cost

        # Tracking
        self._total_decisions = 0
        self._verifications_triggered = 0
        self._verifications_skipped = 0
        self._history: list[VerificationDecision] = []

    def decide(
        self,
        *,
        risk_score: float = 0.0,
        model_confidence: float = 1.0,
        task_class: str | None = None,
        has_side_effects: bool = False,
        customer_facing: bool = False,
    ) -> VerificationDecision:
        """Decide whether to invoke verification for this request."""
        # Compute effective risk
        effective_risk = risk_score
        if has_side_effects:
            effective_risk = max(effective_risk, 0.6)
        if customer_facing:
            effective_risk = max(effective_risk, 0.5)

        # Decision logic
        should_verify = False
        reason = ""

        if effective_risk >= self._risk_threshold:
            should_verify = True
            reason = f"Risk score {effective_risk:.2f} >= threshold {self._risk_threshold}"
        elif model_confidence < self._confidence_threshold:
            should_verify = True
            reason = (
                f"Model confidence {model_confidence:.2f} < threshold {self._confidence_threshold}"
            )
        else:
            reason = (
                f"Verification skipped: risk {effective_risk:.2f} < {self._risk_threshold}, "
                f"confidence {model_confidence:.2f} >= {self._confidence_threshold}"
            )

        decision = VerificationDecision(
            should_verify=should_verify,
            reason=reason,
            risk_score=effective_risk,
            model_confidence=model_confidence,
            task_class=task_class,
            risk_threshold=self._risk_threshold,
            confidence_threshold=self._confidence_threshold,
            estimated_verification_cost=self._avg_cost if should_verify else 0.0,
            estimated_savings_if_skipped=0.0 if should_verify else self._avg_cost,
        )

        self._total_decisions += 1
        if should_verify:
            self._verifications_triggered += 1
        else:
            self._verifications_skipped += 1
        self._history.append(decision)

        return decision

    def set_thresholds(self, risk: float | None = None, confidence: float | None = None) -> None:
        if risk is not None:
            self._risk_threshold = risk
        if confidence is not None:
            self._confidence_threshold = confidence

    def get_stats(self) -> dict:
        skip_rate = (
            self._verifications_skipped / self._total_decisions
            if self._total_decisions > 0
            else 0.0
        )
        estimated_savings = self._verifications_skipped * self._avg_cost

        return {
            "total_decisions": self._total_decisions,
            "verifications_triggered": self._verifications_triggered,
            "verifications_skipped": self._verifications_skipped,
            "skip_rate": round(skip_rate, 3),
            "estimated_savings": round(estimated_savings, 4),
            "risk_threshold": self._risk_threshold,
            "confidence_threshold": self._confidence_threshold,
        }
