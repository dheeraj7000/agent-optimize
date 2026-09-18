"""Onboarding service — tracks setup progress and seeds demo data."""

from __future__ import annotations

import random
import uuid
from datetime import datetime

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class OnboardingStep(BaseModel):
    key: str
    title: str
    description: str
    completed: bool = False
    completed_at: datetime | None = None


class OnboardingStatus(BaseModel):
    tenant_id: str = ""
    steps: list[OnboardingStep] = Field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0
    pct_complete: float = 0.0
    all_complete: bool = False


_STEPS = [
    OnboardingStep(key="connect_traces", title="Connect traces",
                   description="Send your first OpenTelemetry traces to /v1/traces"),
    OnboardingStep(key="view_dashboard", title="View dashboard",
                   description="Open the opportunity dashboard to see cost analysis"),
    OnboardingStep(key="generate_recommendations", title="Generate recommendations",
                   description="Run waste analysis and generate optimization recommendations"),
    OnboardingStep(key="review_recommendation", title="Review a recommendation",
                   description="Drill into a recommendation to see impact, evidence, and action items"),
    OnboardingStep(key="run_replay", title="Run a replay experiment",
                   description="Validate a recommendation with counterfactual replay"),
    OnboardingStep(key="configure_autopilot", title="Configure autopilot",
                   description="Set constraints and enable at least 'suggest' mode"),
]


class OnboardingService:
    """Tracks per-tenant onboarding progress."""

    def __init__(self) -> None:
        self._progress: dict[str, set[str]] = {}  # tenant_id -> completed step keys

    def get_status(self, tenant_id: str = "default") -> OnboardingStatus:
        completed = self._progress.get(tenant_id, set())
        steps = []
        for s in _STEPS:
            step = s.model_copy()
            step.completed = step.key in completed
            steps.append(step)

        done = sum(1 for s in steps if s.completed)
        return OnboardingStatus(
            tenant_id=tenant_id,
            steps=steps,
            completed_count=done,
            total_count=len(steps),
            pct_complete=round(done / len(steps) * 100, 1) if steps else 0,
            all_complete=done == len(steps),
        )

    def complete_step(self, tenant_id: str, step_key: str) -> OnboardingStatus:
        if tenant_id not in self._progress:
            self._progress[tenant_id] = set()
        self._progress[tenant_id].add(step_key)
        logger.info("onboarding.step_completed", tenant_id=tenant_id, step=step_key)
        return self.get_status(tenant_id)


def generate_demo_traces(count: int = 20) -> list[dict]:
    """Generate synthetic OTLP trace payloads for demo/onboarding."""
    models = ["gpt-4o", "gpt-4o", "gpt-4o-mini", "gpt-4o", "claude-sonnet-4-20250514"]
    tools = ["web_search", "calculator", "code_interpreter", "web_search", "web_search"]
    payloads = []

    for i in range(count):
        trace_id = f"demo-{uuid.uuid4().hex[:8]}"
        n_spans = random.randint(3, 8)
        start_ns = 1700000000000000000 + i * 10_000_000_000
        spans = []

        for j in range(n_spans):
            model = random.choice(models)
            input_tok = random.randint(500, 12000)
            output_tok = random.randint(50, 2000)
            is_tool = j % 3 == 2

            attrs = [
                {"key": "gen_ai.system", "value": {"stringValue": "openai" if "gpt" in model else "anthropic"}},
                {"key": "gen_ai.request.model", "value": {"stringValue": model}},
                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": input_tok}},
                {"key": "gen_ai.usage.output_tokens", "value": {"intValue": output_tok}},
            ]
            if is_tool:
                attrs.append({"key": "tool.name", "value": {"stringValue": random.choice(tools)}})

            spans.append({
                "traceId": trace_id,
                "spanId": f"span-{i}-{j}",
                "parentSpanId": f"span-{i}-0" if j > 0 else None,
                "name": "tool_call" if is_tool else "chat",
                "startTimeUnixNano": str(start_ns + j * 1_000_000_000),
                "endTimeUnixNano": str(start_ns + (j + 1) * 1_000_000_000),
                "status": {"code": 1},
                "attributes": attrs,
            })

        payloads.append({
            "resourceSpans": [{
                "resource": {"attributes": [
                    {"key": "service.name", "value": {"stringValue": "demo-agent"}},
                ]},
                "scopeSpans": [{"scope": {}, "spans": spans}],
            }],
        })

    return payloads
