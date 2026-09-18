"""Tests for core data models — traces, waste, recommendations."""

from datetime import UTC, datetime, timedelta

import pytest

from agent_optimize.models.traces import (
    CostBreakdown,
    NormalizedTrace,
    SpanKind,
    TokenUsage,
)
from agent_optimize.models.waste import WasteCategory, WasteDetection, WasteReport
from agent_optimize.models.recommendations import (
    ConfidenceScore,
    ImpactProjection,
    Recommendation,
    RecommendationPriority,
    RecommendationStatus,
)

from tests.conftest import make_span, make_trace


class TestTokenUsage:
    def test_auto_total(self):
        t = TokenUsage(input_tokens=100, output_tokens=50)
        assert t.total_tokens == 150

    def test_explicit_total(self):
        t = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=200)
        assert t.total_tokens == 200


class TestCostBreakdown:
    def test_auto_total(self):
        c = CostBreakdown(input_cost=0.01, output_cost=0.02)
        assert c.total_cost == 0.03

    def test_with_tool_cost(self):
        c = CostBreakdown(input_cost=0.01, output_cost=0.02, tool_cost=0.005)
        assert c.total_cost == pytest.approx(0.035)


class TestNormalizedTrace:
    def test_recompute_aggregates(self):
        trace = make_trace()
        trace.recompute_aggregates()
        assert trace.model_call_count == 2
        assert trace.total_input_tokens == 5000
        assert trace.total_output_tokens == 800
        assert trace.total_cost > 0

    def test_duration_auto_computed(self):
        now = datetime.now(tz=UTC)
        trace = NormalizedTrace(
            trace_id="t1",
            start_time=now,
            end_time=now + timedelta(seconds=5),
        )
        assert trace.duration_ms == 5000.0

    def test_unique_models(self):
        spans = [
            make_span(model="gpt-4o"),
            make_span(model="gpt-4o-mini"),
            make_span(model="gpt-4o"),
        ]
        trace = make_trace(spans=spans)
        assert trace.unique_models == ["gpt-4o", "gpt-4o-mini"]

    def test_retry_count(self):
        spans = [
            make_span(),
            make_span(is_retry=True, retry_number=1),
            make_span(is_retry=True, retry_number=2),
        ]
        trace = make_trace(spans=spans)
        assert trace.retry_count == 2


class TestWasteReport:
    def test_recompute(self):
        report = WasteReport(
            total_cost=1.0,
            detections=[
                WasteDetection(
                    detection_id="d1",
                    trace_id="t1",
                    category=WasteCategory.MODEL_OVERPROVISIONING,
                    confidence="high",
                    estimated_waste_cost=0.3,
                ),
                WasteDetection(
                    detection_id="d2",
                    trace_id="t1",
                    category=WasteCategory.RETRY_WASTE,
                    confidence="medium",
                    estimated_waste_cost=0.1,
                ),
            ],
        )
        report.recompute()

        assert report.total_waste == 0.4
        assert report.useful_work_cost == 0.6
        assert report.efficiency_score == 0.6
        assert report.waste_by_category[WasteCategory.MODEL_OVERPROVISIONING] == 0.3
        assert report.waste_by_category[WasteCategory.RETRY_WASTE] == 0.1


class TestRecommendation:
    def test_defaults(self):
        rec = Recommendation()
        assert rec.status == RecommendationStatus.PENDING
        assert rec.priority == RecommendationPriority.MEDIUM
        assert rec.business_value_score == 0.0

    def test_impact_projection(self):
        impact = ImpactProjection(
            current_monthly_cost=10000,
            projected_monthly_cost=7000,
            monthly_savings=3000,
            annual_savings=36000,
            cost_reduction_pct=30.0,
        )
        assert impact.annual_savings == 36000

    def test_confidence_score(self):
        cs = ConfidenceScore(overall="high", overall_pct=85.0, sample_size_score=0.9)
        assert cs.overall_pct == 85.0
