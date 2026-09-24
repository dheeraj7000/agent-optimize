"""Tests for recommendation lifecycle state machine and autopilot policy engine."""

import pytest

from agent_optimize.models.recommendations import (
    ConfidenceScore,
    ImpactProjection,
    Recommendation,
    RecommendationStatus,
)
from agent_optimize.optimization.recommendation_store import RecommendationStore
from agent_optimize.autopilot.policy import (
    AutopilotMode,
    PolicyConstraints,
    PolicyDecision,
    PolicyEngine,
)
from agent_optimize.models.waste import ConfidenceLevel


def _make_rec(**kwargs) -> Recommendation:
    defaults = {
        "category": "model_overprovisioning", "title": "Test recommendation",
        "impact": ImpactProjection(monthly_savings=1000, annual_savings=12000),
        "confidence": ConfidenceScore(overall="high", overall_pct=85.0),
    }
    defaults.update(kwargs)
    return Recommendation(**defaults)


class TestRecommendationLifecycle:
    def test_happy_path(self):
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)
        rec = store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        assert rec.status == RecommendationStatus.ACCEPTED
        rec = store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        assert rec.status == RecommendationStatus.DEPLOYED
        rec = store.transition(rec.recommendation_id, RecommendationStatus.VERIFIED)
        assert rec.status == RecommendationStatus.VERIFIED
        assert len(rec.status_history) == 3

    def test_replay_path(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(rec.recommendation_id, RecommendationStatus.REPLAYING)
        store.transition(rec.recommendation_id, RecommendationStatus.VALIDATED)
        store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        rec = store.transition(rec.recommendation_id, RecommendationStatus.VERIFIED)
        assert rec.status == RecommendationStatus.VERIFIED
        assert len(rec.status_history) == 5

    def test_reject_from_pending(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        assert store.transition(rec.recommendation_id, RecommendationStatus.REJECTED).status == RecommendationStatus.REJECTED

    def test_rollback_from_deployed(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        assert store.transition(rec.recommendation_id, RecommendationStatus.ROLLED_BACK).status == RecommendationStatus.ROLLED_BACK

    def test_invalid_transition_raises(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)

    def test_cannot_transition_from_rejected(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        store.transition(rec.recommendation_id, RecommendationStatus.REJECTED)
        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)

    def test_cannot_transition_from_verified(self):
        store = RecommendationStore(); rec = _make_rec(); store.store(rec)
        store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        store.transition(rec.recommendation_id, RecommendationStatus.VERIFIED)
        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)

    def test_query_by_status(self):
        store = RecommendationStore(); r1 = _make_rec(); r2 = _make_rec()
        store.store(r1); store.store(r2)
        store.transition(r2.recommendation_id, RecommendationStatus.ACCEPTED)
        assert len(store.query(status=RecommendationStatus.PENDING)) == 1
        assert len(store.query(status=RecommendationStatus.ACCEPTED)) == 1

    def test_stats(self):
        store = RecommendationStore(); r1 = _make_rec(); r2 = _make_rec()
        store.store(r1); store.store(r2)
        store.transition(r2.recommendation_id, RecommendationStatus.ACCEPTED)
        stats = store.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"]["pending"] == 1
        assert stats["by_status"]["accepted"] == 1
        assert stats["total_identified_savings"] == 2000.0


class TestPolicyEngine:
    def _valid_evidence(self, **kwargs):
        values = {
            "projected_quality_score": 0.99, "projected_p50_latency_ms": 1000,
            "projected_p95_latency_ms": 5000, "projected_reliability": 0.99,
            "risk_level": ConfidenceLevel.LOW, "replay_validation_passed": True,
            "canary_passed": True,
        }
        values.update(kwargs)
        return values

    def test_autonomous_authorizes_but_does_not_claim_execution(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        result = engine.make_decision(PolicyDecision(action_type="model_route", expected_savings=100,
            expected_quality_impact=-0.001, **self._valid_evidence()))
        assert result.applied is False
        assert result.outcome == "authorized_not_executed"
        assert engine.status.decisions_applied == 0

    def test_supervised_queues_for_approval(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.SUPERVISED)
        result = engine.make_decision(PolicyDecision(action_type="model_route", expected_savings=50,
            **self._valid_evidence()))
        assert result.applied is False
        assert result.outcome == "pending_approval"

    def test_approve_pending_decision_only_records_approval(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.SUPERVISED)
        result = engine.make_decision(PolicyDecision(action_type="test", **self._valid_evidence()))
        approved = engine.approve_decision(result.decision_id, actor="admin")
        assert approved.applied is False
        assert approved.outcome == "approved_not_executed"
        assert approved.approved_by == "user:admin"

    def test_reject_pending_decision(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.SUPERVISED)
        result = engine.make_decision(PolicyDecision(action_type="test", **self._valid_evidence()))
        assert engine.reject_decision(result.decision_id).outcome == "rejected"

    def test_missing_guardrail_evidence_blocks_decision(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        result = engine.make_decision(PolicyDecision(action_type="model_route", expected_savings=500))
        assert result.applied is False
        assert result.outcome == "constraint_violation"
        assert result.constraint_violations

    @pytest.mark.parametrize("field,value", [
        ("projected_quality_score", 0.5), ("projected_p50_latency_ms", 20000),
        ("projected_p95_latency_ms", 50000), ("projected_reliability", 0.5),
        ("risk_level", ConfidenceLevel.HIGH), ("replay_validation_passed", False),
        ("canary_passed", False),
    ])
    def test_guardrail_violations_block(self, field, value):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        evidence = self._valid_evidence(**{field: value})
        result = engine.make_decision(PolicyDecision(action_type="test", **evidence))
        assert result.outcome == "constraint_violation"
        assert not result.applied

    def test_configured_cost_caps_block_decision(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        engine.set_constraints(PolicyConstraints(max_cost_per_trace=1, max_monthly_budget=100))
        result = engine.make_decision(PolicyDecision(action_type="test", projected_cost_per_trace=2,
            projected_monthly_cost=200, **self._valid_evidence()))
        assert result.outcome == "constraint_violation"
        assert len(result.constraint_violations) >= 2

    def test_off_mode_doesnt_apply(self):
        result = PolicyEngine().make_decision(PolicyDecision(action_type="test", expected_savings=10))
        assert result.applied is False
        assert result.outcome == "constraint_violation"

    def test_stats_track_decisions_without_false_execution_counts(self):
        engine = PolicyEngine(); engine.set_mode(AutopilotMode.AUTONOMOUS)
        engine.make_decision(PolicyDecision(action_type="a", expected_savings=10, **self._valid_evidence()))
        engine.make_decision(PolicyDecision(action_type="b", expected_savings=20, **self._valid_evidence()))
        stats = engine.get_stats()
        assert stats["decisions_made"] == 2
        assert stats["decisions_applied"] == 0
        assert stats["estimated_monthly_savings"] == 0
