"""FastAPI application factory and global state management."""

from __future__ import annotations

import os
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
from agent_optimize.onboarding.service import OnboardingService
from agent_optimize.optimization.engine import OptimizationEngine
from agent_optimize.optimization.recommendation_store import RecommendationStore
from agent_optimize.optimization.replay import ReplayEngine
from agent_optimize.optimization.validator import CanaryManager, SavingsValidator
from agent_optimize.webhooks.events import EventBus, WebhookDispatcher

logger = structlog.get_logger()


def _create_warehouse(config: AppConfig):
    """Create trace warehouse — SQLite for production, in-memory for dev."""
    db_path = os.environ.get("AGENTOPTIMIZE_DB_PATH", "")
    if db_path:
        from agent_optimize.storage.database import Database
        from agent_optimize.storage.trace_store import SqliteTraceStore
        db = Database(db_path)
        logger.info("storage.sqlite", path=db_path)
        return SqliteTraceStore(db), db
    from agent_optimize.warehouse.store import TraceWarehouse
    logger.info("storage.memory")
    return TraceWarehouse(retention_hours=config.warehouse.retention_hours), None


class AppState:
    """Holds all shared application state — warehouse, analyzers, detectors, etc."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.warehouse, self.db = _create_warehouse(config)
        self.cost_catalog = CostCatalog(config.cost_catalog)
        self.cost_analyzer = CostAnalyzer(self.cost_catalog)
        self.detector_registry = create_default_registry(
            config.detectors.model_dump() if config.detectors else None
        )
        self.optimization_engine = OptimizationEngine()
        self.replay_engine = ReplayEngine()
        self.recommendation_store = _create_recommendation_store(self.db)
        self.evaluator_registry = create_default_evaluator_registry()
        self.savings_validator = SavingsValidator(self.evaluator_registry)
        self.canary_manager = CanaryManager(self.savings_validator)
        self.proof_store = _create_proof_store(self.db)
        self.policy_engine = PolicyEngine()
        self.model_router = ModelRouter()
        self.adaptive_verifier = AdaptiveVerifier()
        self.recovery_selector = RecoverySelector()
        self.webhook_dispatcher = WebhookDispatcher()
        self.event_bus = EventBus(self.webhook_dispatcher)
        self.onboarding = OnboardingService()


def _create_recommendation_store(db):
    if db is not None:
        from agent_optimize.storage.recommendation_store_sql import SqliteRecommendationStore
        return SqliteRecommendationStore(db)
    return RecommendationStore()


def _create_proof_store(db):
    if db is not None:
        from agent_optimize.storage.proof_store_sql import SqliteProofStore
        return SqliteProofStore(db)
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config()
    state = AppState(config)
    set_state(state)
    normalizer = TraceNormalizer(capture_content=config.privacy.capture_prompts)
    set_normalizer(normalizer)
    set_trace_callback(_on_trace_ingested)
    logger.info(
        "app.started", version="0.4.0", warehouse_backend="sqlite" if state.db else "memory",
        detectors=len(state.detector_registry.list_detectors()),
        evaluators=len(state.evaluator_registry.list_evaluators()),
        providers=state.cost_catalog.list_providers(), autopilot_mode=state.policy_engine.status.mode.value,
    )
    try:
        yield
    finally:
        logger.info(
            "app.shutdown", traces_stored=state.warehouse.trace_count,
            recommendations=state.recommendation_store.count,
            proofs=state.proof_store.count if hasattr(state.proof_store, "count") else len(state.proof_store),
            autopilot_decisions=state.policy_engine.status.decisions_made,
        )
        set_state(None)


async def _on_trace_ingested(trace: NormalizedTrace) -> None:
    state = get_state()
    trace = state.cost_analyzer.analyze_trace(trace)
    await state.warehouse.store(trace)
    report = state.detector_registry.analyze_trace(trace)
    logger.info("pipeline.processed", trace_id=trace.trace_id, cost=trace.total_cost,
                waste=report.total_waste, efficiency=f"{report.efficiency_score:.0%}",
                detections=report.detections_count)


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    from agent_optimize.auth.middleware import ApiKeyManager, AuthMiddleware, is_auth_required
    auth_required = is_auth_required()
    if auth_required and not os.environ.get("AGENTOPTIMIZE_DB_PATH"):
        raise RuntimeError("AGENTOPTIMIZE_DB_PATH must be set when API key authentication is enabled")
    if not auth_required:
        logger.warning(
            "auth.disabled",
            hint="API is unauthenticated. Set AGENTOPTIMIZE_API_KEY_REQUIRED=true "
                 "for any deployment reachable outside localhost.",
        )

    app = FastAPI(
        title="AgentOptimize",
        description="AI-agent FinOps: waste attribution, counterfactual optimization, and quality preservation.",
        version="0.4.0", lifespan=lifespan,
    )
    origins_value = os.environ.get("AGENTOPTIMIZE_CORS_ORIGINS", "")
    cors_origins = [origin.strip() for origin in origins_value.split(",") if origin.strip()]
    if "*" in cors_origins and auth_required:
        raise RuntimeError("Wildcard CORS origins are not allowed when authentication is enabled")
    if cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=cors_origins, allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Accept"],
        )
    if auth_required:
        from agent_optimize.storage.database import Database
        db = Database(os.environ["AGENTOPTIMIZE_DB_PATH"])
        app.add_middleware(AuthMiddleware, key_manager=ApiKeyManager(db), required=True)
        logger.info("auth.enabled")

    from agent_optimize.api.routes import (
        autopilot, dashboard, experiments, health, metrics_route, onboarding_route,
        recommendations, traces, validation, webhooks,
    )
    from agent_optimize.metrics.prometheus import MetricsMiddleware
    app.add_middleware(MetricsMiddleware)
    for route in (health.router, otlp_router, traces.router, dashboard.router, recommendations.router,
                  experiments.router, validation.router, autopilot.router, webhooks.router,
                  metrics_route.router, onboarding_route.router):
        app.include_router(route)
    _mount_dashboard(app)
    return app


def _mount_dashboard(app: FastAPI) -> None:
    """Mount the React dashboard build as static files with SPA fallback."""
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    candidates = [Path(__file__).parent.parent.parent.parent / "dashboard" / "dist",
                  Path("/app/dashboard/dist"), Path("dashboard/dist")]
    dist_dir = next((path for path in candidates if path.is_dir()), None)
    if dist_dir is None:
        logger.info("dashboard.not_found", hint="Run 'npm run build' in dashboard/")
        return
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="dashboard-assets")
    index_html = dist_dir / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str) -> FileResponse:
        file_path = dist_dir / path
        if file_path.is_file() and ".." not in path:
            return FileResponse(str(file_path))
        return FileResponse(str(index_html))
    logger.info("dashboard.mounted", path=str(dist_dir))
