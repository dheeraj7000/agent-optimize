"""FastAPI application factory and global state management."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_optimize.api.state import get_state, set_state
from agent_optimize.autopilot.policy import PolicyEngine
from agent_optimize.autopilot.recovery import RecoverySelector
from agent_optimize.autopilot.router import ModelRouter
from agent_optimize.autopilot.verification import AdaptiveVerifier
from agent_optimize.config import AppConfig, load_config
from agent_optimize.cost.analyzer import CostAnalyzer
from agent_optimize.cost.catalog import CostCatalog
from agent_optimize.detectors import create_default_registry
from agent_optimize.evaluation.registry import create_default_evaluator_registry
from agent_optimize.ingestion.normalizer import TraceNormalizer
from agent_optimize.ingestion.otlp_receiver import router as otlp_router
from agent_optimize.ingestion.otlp_receiver import set_normalizer, set_trace_callback
from agent_optimize.models.traces import NormalizedTrace
from agent_optimize.optimization.engine import OptimizationEngine
from agent_optimize.optimization.recommendation_store import RecommendationStore
from agent_optimize.optimization.replay import ReplayEngine
from agent_optimize.optimization.validator import CanaryManager, SavingsValidator
from agent_optimize.warehouse.store import TraceWarehouse

logger = structlog.get_logger()


class AppState:
    """Holds all shared application state — warehouse, analyzers, detectors, etc."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.warehouse = TraceWarehouse(retention_hours=config.warehouse.retention_hours)
        self.cost_catalog = CostCatalog(config.cost_catalog)
        self.cost_analyzer = CostAnalyzer(self.cost_catalog)
        self.detector_registry = create_default_registry(
            config.detectors.model_dump() if config.detectors else None
        )
        self.optimization_engine = OptimizationEngine()
        self.replay_engine = ReplayEngine()
        # V2: Recommendation lifecycle store
        self.recommendation_store = RecommendationStore()
        # V3: Evaluation, validation, and canary monitoring
        self.evaluator_registry = create_default_evaluator_registry()
        self.savings_validator = SavingsValidator(self.evaluator_registry)
        self.canary_manager = CanaryManager(self.savings_validator)
        self.proof_store: dict = {}  # proof_id -> SavingsProof
        # V4: Autopilot — dynamic routing, adaptive verification, recovery
        self.policy_engine = PolicyEngine()
        self.model_router = ModelRouter()
        self.adaptive_verifier = AdaptiveVerifier()
        self.recovery_selector = RecoverySelector()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    config = load_config()
    state = AppState(config)
    set_state(state)

    # Wire up the ingestion pipeline
    normalizer = TraceNormalizer(capture_content=config.privacy.capture_prompts)
    set_normalizer(normalizer)
    set_trace_callback(_on_trace_ingested)

    logger.info(
        "app.started",
        warehouse_backend=config.warehouse.backend,
        detectors=len(state.detector_registry.list_detectors()),
        evaluators=len(state.evaluator_registry.list_evaluators()),
        providers=state.cost_catalog.list_providers(),
        autopilot_mode=state.policy_engine.status.mode.value,
    )

    yield

    logger.info(
        "app.shutdown",
        traces_stored=state.warehouse.trace_count,
        recommendations=state.recommendation_store.count,
        proofs=len(state.proof_store),
        autopilot_decisions=state.policy_engine.status.decisions_made,
    )
    set_state(None)


async def _on_trace_ingested(trace: NormalizedTrace) -> None:
    """Pipeline callback: cost-analyze and store each ingested trace."""
    state = get_state()

    # Step 1: Attribute costs
    trace = state.cost_analyzer.analyze_trace(trace)

    # Step 2: Store in warehouse
    await state.warehouse.store(trace)

    # Step 3: Run waste detection
    report = state.detector_registry.analyze_trace(trace)

    logger.info(
        "pipeline.processed",
        trace_id=trace.trace_id,
        cost=trace.total_cost,
        waste=report.total_waste,
        efficiency=f"{report.efficiency_score:.0%}",
        detections=report.detections_count,
    )


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AgentOptimize",
        description="AI-agent FinOps: waste attribution, counterfactual optimization, and quality preservation.",
        version="0.4.0",
        lifespan=lifespan,
    )

    # CORS for dashboard frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routes — imported here to avoid circular imports
    from agent_optimize.api.routes import (
        autopilot,
        dashboard,
        experiments,
        health,
        recommendations,
        traces,
        validation,
    )

    app.include_router(health.router)
    app.include_router(otlp_router)
    app.include_router(traces.router)
    app.include_router(dashboard.router)
    # V2 routes
    app.include_router(recommendations.router)
    app.include_router(experiments.router)
    # V3 routes
    app.include_router(validation.router)
    # V4 routes
    app.include_router(autopilot.router)

    return app
