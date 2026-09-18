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


def _make_rec(**kwargs) -> Recommendation:
    defaults = {
        "category": "model_overprovisioning",
        "title": "Test recommendation",
        "impact": ImpactProjection(monthly_savings=1000, annual_savings=12000),
        "confidence": ConfidenceScore(overall="high", overall_pct=85.0),
    }
    defaults.update(kwargs)
    return Recommendation(**defaults)


class TestRecommendationLifecycle:
    def test_happy_path(self):
        """pending → accepted → deployed → verified"""
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
        """pending → accepted → replaying → validated → deployed → verified"""
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)

        store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(rec.recommendation_id, RecommendationStatus.REPLAYING)
        store.transition(rec.recommendation_id, RecommendationStatus.VALIDATED)
        store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        rec = store.transition(rec.recommendation_id, RecommendationStatus.VERIFIED)
        assert rec.status == RecommendationStatus.VERIFIED
        assert len(rec.status_history) == 5

    def test_reject_from_pending(self):
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)

        rec = store.transition(rec.recommendation_id, RecommendationStatus.REJECTED)
        assert rec.status == RecommendationStatus.REJECTED

    def test_rollback_from_deployed(self):
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)

        store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        rec = store.transition(rec.recommendation_id, RecommendationStatus.ROLLED_BACK)
        assert rec.status == RecommendationStatus.ROLLED_BACK

    def test_invalid_transition_raises(self):
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)

        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)

    def test_cannot_transition_from_rejected(self):
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)

        store.transition(rec.recommendation_id, RecommendationStatus.REJECTED)
        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)

    def test_cannot_transition_from_verified(self):
        store = RecommendationStore()
        rec = _make_rec()
        store.store(rec)

        store.transition(rec.recommendation_id, RecommendationStatus.ACCEPTED)
        store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)
        store.transition(rec.recommendation_id, RecommendationStatus.VERIFIED)
        with pytest.raises(ValueError, match="Cannot transition"):
            store.transition(rec.recommendation_id, RecommendationStatus.DEPLOYED)

    def test_query_by_status(self):
        store = RecommendationStore()
        r1 = _make_rec()
        r2 = _make_rec()
        store.store(r1)
        store.store(r2)
        store.transition(r2.recommendation_id, RecommendationStatus.ACCEPTED)

        pending = store.query(status=RecommendationStatus.PENDING)
        accepted = store.query(status=RecommendationStatus.ACCEPTED)
        assert len(pending) == 1
        assert len(accepted) == 1

    def test_stats(self):
        store = RecommendationStore()
        r1 = _make_rec()
        r2 = _make_rec()
        store.store(r1)
        store.store(r2)
        store.transition(r2.recommendation_id, RecommendationStatus.ACCEPTED)

        stats = store.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"]["pending"] == 1
        assert stats["by_status"]["accepted"] == 1
        assert stats["total_identified_savings"] == 2000.0


class TestPolicyEngine:
    def test_autonomous_applies_decisions(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.AUTONOMOUS)

        decision = PolicyDecision(
            action_type="model_route",
            expected_savings=100.0,
            expected_quality_impact=-0.001,
        )
        result = engine.make_decision(decision)
        assert result.applied is True
        assert result.outcome == "applied"

    def test_supervised_queues_for_approval(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.SUPERVISED)

        decision = PolicyDecision(action_type="model_route", expected_savings=50.0)
        result = engine.make_decision(decision)
        assert result.applied is False
        assert result.outcome == "pending_approval"

    def test_approve_pending_decision(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.SUPERVISED)

        decision = PolicyDecision(action_type="test", expected_savings=10.0)
        result = engine.make_decision(decision)
        approved = engine.approve_decision(result.decision_id, actor="admin")
        assert approved.applied is True
        assert approved.approved_by == "user:admin"

    def test_reject_pending_decision(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.SUPERVISED)

        decision = PolicyDecision(action_type="test")
        result = engine.make_decision(decision)
        rejected = engine.reject_decision(result.decision_id)
        assert rejected.outcome == "rejected"

    def test_constraint_violation_blocks_decision(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.AUTONOMOUS)
        engine.set_constraints(PolicyConstraints(max_quality_regression=0.02))

        decision = PolicyDecision(
            action_type="model_route",
            expected_savings=500.0,
            expected_quality_impact=-0.05,  # 5% > max 2%
        )
        result = engine.make_decision(decision)
        assert result.applied is False
        assert result.outcome == "constraint_violation"
        assert len(result.constraint_violations) > 0

    def test_off_mode_doesnt_apply(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.OFF)

        decision = PolicyDecision(action_type="test", expected_savings=10.0)
        result = engine.make_decision(decision)
        assert result.applied is False
        assert result.outcome == "autopilot_off"

    def test_stats_track_decisions(self):
        engine = PolicyEngine()
        engine.set_mode(AutopilotMode.AUTONOMOUS)

        engine.make_decision(PolicyDecision(action_type="a", expected_savings=10.0))
        engine.make_decision(PolicyDecision(action_type="b", expected_savings=20.0))

        stats = engine.get_stats()
        assert stats["decisions_made"] == 2
        assert stats["decisions_applied"] == 2
        assert stats["estimated_monthly_savings"] == 30.0
