"""Tests for waste detectors — each detector must produce accurate, evidence-backed detections."""

from agent_optimize.detectors import create_default_registry
from agent_optimize.detectors.model_overprovisioning import ModelOverprovisioningDetector
from agent_optimize.detectors.context_duplication import ContextDuplicationDetector
from agent_optimize.detectors.retry_waste import RetryWasteDetector
from agent_optimize.detectors.unnecessary_verification import UnnecessaryVerificationDetector
from agent_optimize.detectors.redundant_tools import RedundantToolsDetector
from agent_optimize.detectors.bad_routing import BadRoutingDetector
from agent_optimize.detectors.serialization_waste import SerializationWasteDetector
from agent_optimize.models.traces import SpanKind, SpanStatus
from agent_optimize.models.waste import WasteCategory

from tests.conftest import make_span, make_trace


class TestModelOverprovisioning:
    def test_detects_frontier_on_low_complexity(self):
        """Frontier model on small input/output should be flagged."""
        detector = ModelOverprovisioningDetector()
        spans = [
            make_span(model="gpt-4o", input_tokens=500, output_tokens=100,
                      input_cost=0.00125, output_cost=0.001),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) >= 1
        assert detections[0].category == WasteCategory.MODEL_OVERPROVISIONING

    def test_ignores_small_model(self):
        """Small models should not be flagged."""
        detector = ModelOverprovisioningDetector()
        spans = [
            make_span(model="gemini-2.0-flash", input_tokens=500, output_tokens=100,
                      input_cost=0.0001, output_cost=0.0001),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) == 0

    def test_ignores_high_complexity(self):
        """Frontier model on large input/output should not be flagged."""
        detector = ModelOverprovisioningDetector()
        spans = [
            make_span(model="gpt-4o", input_tokens=10000, output_tokens=2000,
                      input_cost=0.025, output_cost=0.02),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) == 0


class TestContextDuplication:
    def test_detects_growing_context(self):
        """Monotonically growing input tokens with low novelty should be flagged."""
        detector = ContextDuplicationDetector()
        # Each call grows substantially but increments are small relative to total
        # → high duplication ratio
        spans = [
            make_span(input_tokens=8000, output_tokens=200, input_cost=0.02, output_cost=0.002),
            make_span(input_tokens=14000, output_tokens=200, input_cost=0.035, output_cost=0.002),
            make_span(input_tokens=19000, output_tokens=200, input_cost=0.0475, output_cost=0.002),
            make_span(input_tokens=23000, output_tokens=200, input_cost=0.0575, output_cost=0.002),
            make_span(input_tokens=26000, output_tokens=200, input_cost=0.065, output_cost=0.002),
            make_span(input_tokens=28000, output_tokens=200, input_cost=0.07, output_cost=0.002),
            make_span(input_tokens=30000, output_tokens=200, input_cost=0.075, output_cost=0.002),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) >= 1
        assert detections[0].category == WasteCategory.CONTEXT_DUPLICATION

    def test_ignores_stable_context(self):
        """Stable input tokens should not be flagged."""
        detector = ContextDuplicationDetector()
        spans = [
            make_span(input_tokens=2000, output_tokens=200),
            make_span(input_tokens=2100, output_tokens=200),
            make_span(input_tokens=1900, output_tokens=200),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) == 0


class TestRetryWaste:
    def test_detects_repeated_tool_failures(self):
        """Sequential failures of the same tool should be flagged."""
        detector = RetryWasteDetector()
        spans = [
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_success=False, status=SpanStatus.ERROR,
                      input_cost=0.001, output_cost=0.0),
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_success=False, status=SpanStatus.ERROR,
                      input_cost=0.001, output_cost=0.0),
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_success=False, status=SpanStatus.ERROR,
                      input_cost=0.001, output_cost=0.0),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) >= 1
        assert detections[0].category == WasteCategory.RETRY_WASTE

    def test_ignores_single_failure(self):
        """A single tool failure should not be flagged."""
        detector = RetryWasteDetector()
        spans = [
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_success=False, status=SpanStatus.ERROR),
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_success=True, status=SpanStatus.OK),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) == 0


class TestUnnecessaryVerification:
    def test_detects_expensive_verification_on_simple_run(self):
        """Verification on a simple successful run should be flagged."""
        detector = UnnecessaryVerificationDetector()
        spans = [
            make_span(input_cost=0.005, output_cost=0.005),
            make_span(span_kind=SpanKind.VERIFICATION, name="verify",
                      input_cost=0.01, output_cost=0.01),
        ]
        trace = make_trace(spans=spans, success=True)
        detections = detector.detect(trace)
        # Verification is 66% of cost on a simple 2-call run → should flag
        assert len(detections) >= 1
        assert detections[0].category == WasteCategory.UNNECESSARY_VERIFICATION

    def test_ignores_when_verification_is_cheap(self):
        """Cheap verification should not be flagged."""
        detector = UnnecessaryVerificationDetector()
        spans = [
            make_span(input_cost=0.05, output_cost=0.05),
            make_span(input_cost=0.04, output_cost=0.04),
            make_span(input_cost=0.03, output_cost=0.03),
            make_span(span_kind=SpanKind.VERIFICATION, name="verify",
                      input_cost=0.001, output_cost=0.001),
        ]
        trace = make_trace(spans=spans, success=True)
        detections = detector.detect(trace)
        assert len(detections) == 0


class TestRedundantTools:
    def test_detects_duplicate_tool_calls(self):
        """Tool calls with identical input hashes should be flagged."""
        detector = RedundantToolsDetector()
        spans = [
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_input_hash="abc123", input_cost=0.01, output_cost=0.0),
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_input_hash="abc123", input_cost=0.01, output_cost=0.0),
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search",
                      tool_input_hash="abc123", input_cost=0.01, output_cost=0.0),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) >= 1
        assert detections[0].category == WasteCategory.REDUNDANT_TOOL_CALLS

    def test_ignores_different_inputs(self):
        """Tool calls with different input hashes should not be flagged."""
        detector = RedundantToolsDetector()
        spans = [
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search", tool_input_hash="aaa"),
            make_span(span_kind=SpanKind.TOOL_CALL, tool_name="search", tool_input_hash="bbb"),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) == 0


class TestBadRouting:
    def test_detects_single_premium_model(self):
        """All calls to a single premium model with some low-complexity should be flagged."""
        detector = BadRoutingDetector()
        spans = [
            make_span(model="gpt-4o", input_tokens=500, output_tokens=50),
            make_span(model="gpt-4o", input_tokens=800, output_tokens=100),
            make_span(model="gpt-4o", input_tokens=600, output_tokens=80),
            make_span(model="gpt-4o", input_tokens=5000, output_tokens=1000),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) >= 1
        assert detections[0].category == WasteCategory.BAD_ROUTING

    def test_ignores_multi_model(self):
        """Using multiple models indicates routing exists."""
        detector = BadRoutingDetector()
        spans = [
            make_span(model="gpt-4o-mini", input_tokens=500, output_tokens=50),
            make_span(model="gpt-4o", input_tokens=5000, output_tokens=1000),
        ]
        trace = make_trace(spans=spans)
        detections = detector.detect(trace)
        assert len(detections) == 0


class TestRegistry:
    def test_all_detectors_registered(self):
        registry = create_default_registry()
        detectors = registry.list_detectors()
        assert len(detectors) == 7
        names = {d["name"] for d in detectors}
        assert "model_overprovisioning" in names
        assert "context_duplication" in names
        assert "retry_waste" in names

    def test_analyze_trace_returns_report(self):
        registry = create_default_registry()
        trace = make_trace()
        report = registry.analyze_trace(trace)
        assert report.total_cost >= 0
        assert report.efficiency_score >= 0
