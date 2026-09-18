"""CLI entry point for AgentOptimize."""

from __future__ import annotations

import os

import click
import structlog
import uvicorn

from agent_optimize.config import load_config


def _configure_logging() -> None:
    """Configure structlog: JSON for production, console for dev."""
    log_format = os.environ.get("AGENTOPTIMIZE_LOG_FORMAT", "console")
    log_level = os.environ.get("AGENTOPTIMIZE_LOG_LEVEL", "info").upper()

    if log_format == "json":
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(structlog, log_level, structlog.INFO),
            ),
        )
    else:
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.dev.ConsoleRenderer(),
            ],
        )


_configure_logging()


@click.group()
@click.version_option(version="0.4.0", prog_name="agent-optimize")
def main() -> None:
    """AgentOptimize — AI-agent FinOps: Observe. Diagnose. Optimize. Prove."""


@main.command()
@click.option("--host", default=None, help="Server host (default: from config)")
@click.option("--port", default=None, type=int, help="Server port (default: from config)")
@click.option("--config", "config_path", default=None, help="Path to config YAML file")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--json-logs", is_flag=True, help="Enable JSON structured logging")
def serve(
    host: str | None, port: int | None, config_path: str | None,
    reload: bool, json_logs: bool,
) -> None:
    """Start the AgentOptimize server."""
    if json_logs:
        os.environ["AGENTOPTIMIZE_LOG_FORMAT"] = "json"
        _configure_logging()

    config = load_config(config_path)
    server_host = host or config.server.host
    server_port = port or config.server.port

    click.echo(f"Starting AgentOptimize server on {server_host}:{server_port}")
    click.echo(f"  OTLP HTTP endpoint: http://{server_host}:{server_port}/v1/traces")
    click.echo(f"  Dashboard:          http://{server_host}:{server_port}/")
    click.echo(f"  API docs:           http://{server_host}:{server_port}/docs")

    uvicorn.run(
        "agent_optimize.api.app:create_app",
        host=server_host,
        port=server_port,
        reload=reload,
        factory=True,
    )


@main.command()
@click.option("--config", "config_path", default=None, help="Path to config YAML file")
def check_config(config_path: str | None) -> None:
    """Validate the configuration file."""
    try:
        config = load_config(config_path)
        click.echo("Configuration is valid.")
        click.echo(f"  Server: {config.server.host}:{config.server.port}")
        click.echo(f"  Warehouse: {config.warehouse.backend} ({config.warehouse.retention_hours}h retention)")
        click.echo(f"  Providers: {list(config.cost_catalog.providers.keys())}")

        detector_status = []
        detectors = config.detectors.model_dump()
        for name, cfg in detectors.items():
            if isinstance(cfg, dict):
                enabled = cfg.get("enabled", True)
                detector_status.append(f"    {name}: {'enabled' if enabled else 'disabled'}")
        click.echo("  Detectors:")
        for line in detector_status:
            click.echo(line)
    except Exception as e:
        click.echo(f"Configuration error: {e}", err=True)
        raise SystemExit(1) from e


@main.command()
@click.option("--config", "config_path", default=None, help="Path to config YAML file")
def list_models(config_path: str | None) -> None:
    """List all models in the cost catalog."""
    config = load_config(config_path)
    from agent_optimize.cost.catalog import CostCatalog

    catalog = CostCatalog(config.cost_catalog)
    for provider in catalog.list_providers():
        click.echo(f"\n{provider}:")
        for model in catalog.list_models(provider):
            pricing = catalog.get_model_pricing(provider, model)
            click.echo(
                f"  {model}: "
                f"${pricing.input_cost_per_1m}/1M input, "
                f"${pricing.output_cost_per_1m}/1M output"
            )


if __name__ == "__main__":
    main()
