"""Tests for policy guardrails and recommendation lifecycle behavior."""

import pytest

from agent_optimize.autopilot.policy import AutopilotMode, PolicyConstraints, PolicyDecision, PolicyEngine
from agent_optimize.models.recommendations import ConfidenceScore, ImpactProjection, Recommendation, RecommendationStatus
from agent_optimize.models.waste import ConfidenceLevel
from agent_optimize.optimization.recommendation_store import RecommendationStore


def _make_rec(**kwargs) -> Recommendation:
    values = {"category": "model_overprovisioning", "title": "Test recommendation",
              "impact": ImpactProjection(monthly_savings=1000, annual_savings=12000),
              "confidence": ConfidenceScore(overall="high", overall_pct=85.0)}
    values.update(kwargs)
    return Recommendation(**values)


class TestRecommendationLifecycle:
    def test_happy_path(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        assert store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED).status == RecommendationStatus.ACCEPTED
        assert store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED).status == RecommendationStatus.DEPLOYED
        rec = store.transition(rec.recommendation_id, RecommendationStatus.VERIFIED)
        assert rec.status == RecommendationStatus.VERIFIED and len(rec.status_history) == 3

    def test_replay_path(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        for status in (RecommendationStatus.ACCEPTED, RecommendationStatus.REPLAYING,
                       RecommendationStatus.VALIDATED, RecommendationStatus.DEPLOYED,
                       RecommendationStatus.VERIFIED):
            rec = store.transition(rec.recommendation_id, status)
        assert rec.status == RecommendationStatus.VERIFIED and len(rec.status_history) == 5

    def test_reject_and_rollback(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        assert store.transition(rec.recommendation_id, RecommendationStatus.REJECTED).status == RecommendationStatus.REJECTED
        other = _make_rec(); store.store(other)
        store.transition(other.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(other.recommendation_id, RecommendationStatus.DEPLOYED)
        assert store.transition(other.recommendation_id, RecommendationStatus.ROLLED_BACK).status == RecommendationStatus.ROLLED_BACK

    def test_invalid_transition_raises(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)

    def test_query_and_stats(self):
        store = RecommendationStore(); first = _make_rec(); second = _make_rec()
        store.store(first); store.store(second)
        store.transition(second.recommendation_id, RecommendationStatus.ACCEPTED)
        assert len(store.query(status=RecommendationStatus.PENDING)) == 1
        stats = store.get_stats()
        assert stats["total"] == 2 and stats["total_identified_savings"] == 2000.0


class TestPolicyEngine:
    @staticmethod
    def evidence(**updates):
        data = {"projected_quality_score": 0.99, "projected_p50_latency_ms": 1000,
                "projected_p95_latency_ms": 5000, "projected_reliability": 0.99,
                "risk_level": ConfidenceLevel.LOW, "replay_validation_passed": True,
                "canary_passed": True}
        data.update(updates)
        return data

    def test_autonomous_only_authorizes_proposal(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        result = engine.make_decision(PolicyDecision(action_type="route", expected_savings=100,
                                                     **self.evidence()))
        assert result.outcome == "authorized_not_executed" and not result.applied
        assert engine.status.decisions_applied == 0 and engine.status.estimated_monthly_savings == 0

    def test_supervised_approval_is_not_execution(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.SUPERVISED)
        result = engine.make_decision(PolicyDecision(action_type="route", **self.evidence()))
        assert result.outcome == "pending_approval" and not result.applied
        approved = engine.approve_decision(result.decision_id, actor="admin")
        assert approved.outcome == "approved_not_executed" and not approved.applied

    @pytest.mark.parametrize("updates", [
        {}, {"projected_quality_score": 0.5}, {"projected_p50_latency_ms": 20000},
        {"projected_p95_latency_ms": 50000}, {"projected_reliability": 0.5},
        {"risk_level": ConfidenceLevel.HIGH}, {"replay_validation_passed": False},
        {"canary_passed": False},
    ])
    def test_missing_or_failed_evidence_blocks(self, updates):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        result = engine.make_decision(PolicyDecision(action_type="route", **self.evidence(**updates)))
        assert result.outcome == "constraint_violation" and not result.applied

    def test_cost_limits_block(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        engine.set_constraints(PolicyConstraints(max_cost_per_trace=1, max_monthly_budget=100))
        result = engine.make_decision(PolicyDecision(action_type="route", projected_cost_per_trace=2,
            projected_monthly_cost=200, **self.evidence()))
        assert result.outcome == "constraint_violation" and len(result.constraint_violations) >= 2

    def test_off_mode_fails_closed(self):
        result = PolicyEngine().make_decision(PolicyDecision(action_type="route"))
        assert result.outcome == "constraint_violation" and not result.applied

    def test_stats_never_claim_applied_savings(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        for amount in (10, 20):
            engine.make_decision(PolicyDecision(action_type="route", expected_savings=amount,
                                                **self.evidence()))
        assert engine.get_stats()["decisions_applied"] == 0
        assert engine.get_stats()["estimated_monthly_savings"] == 0
