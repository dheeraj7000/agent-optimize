"""SQLite-backed trace store — replaces the in-memory TraceWarehouse for production.

Stores denormalized trace summaries in indexed columns for fast dashboard queries,
with the full NormalizedTrace JSON for drill-down.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from agent_optimize.models.traces import NormalizedTrace, RunSummary
from agent_optimize.storage.database import Database, deserialize_json, serialize_json

logger = structlog.get_logger()


class SqliteTraceStore:
    """SQLite-backed trace storage with the same query interface as TraceWarehouse."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def trace_count(self) -> int:
        return self._db.count("traces")

    async def store(self, trace: NormalizedTrace) -> None:
        """Store a normalized trace."""
        self._db.insert(
            """INSERT OR REPLACE INTO traces
               (trace_id, tenant_id, task_class, start_time, end_time,
                duration_ms, total_cost, total_input_tokens, total_output_tokens,
                model_call_count, tool_call_count, retry_count, success,
                source_framework, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trace.trace_id,
                trace.tenant_id,
                trace.task_class,
                trace.start_time.isoformat(),
                trace.end_time.isoformat(),
                trace.duration_ms,
                trace.total_cost,
                trace.total_input_tokens,
                trace.total_output_tokens,
                trace.model_call_count,
                trace.tool_call_count,
                trace.retry_count,
                1 if trace.success else 0,
                trace.source_framework,
                serialize_json(trace),
            ),
        )

    def get_trace(self, trace_id: str) -> NormalizedTrace | None:
        """Get a full trace by ID."""
        row = self._db.execute_one("SELECT data FROM traces WHERE trace_id = ?", (trace_id,))
        if not row:
            return None
        return NormalizedTrace.model_validate(deserialize_json(row["data"]))

    def get_all_traces(self) -> list[NormalizedTrace]:
        """Get all traces (use with caution in production)."""
        rows = self._db.execute("SELECT data FROM traces ORDER BY start_time DESC LIMIT 10000")
        return [NormalizedTrace.model_validate(deserialize_json(r["data"])) for r in rows]

    def query_traces(
        self,
        *,
        tenant_id: str | None = None,
        task_class: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_cost: float | None = None,
        success_only: bool | None = None,
        limit: int = 1000,
    ) -> list[NormalizedTrace]:
        """Query traces with SQL-backed filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if task_class:
            conditions.append("task_class = ?")
            params.append(task_class)
        if start_time:
            conditions.append("start_time >= ?")
            params.append(start_time.isoformat())
        if end_time:
            conditions.append("end_time <= ?")
            params.append(end_time.isoformat())
        if min_cost is not None:
            conditions.append("total_cost >= ?")
            params.append(min_cost)
        if success_only is not None:
            conditions.append("success = ?")
            params.append(1 if success_only else 0)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT data FROM traces WHERE {where} ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        rows = self._db.execute(sql, tuple(params))
        return [NormalizedTrace.model_validate(deserialize_json(r["data"])) for r in rows]

    def get_run_summaries(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[RunSummary]:
        """Get lightweight run summaries for the dashboard."""
        conditions = ["1=1"]
        params: list[Any] = []

        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)

        where = " AND ".join(conditions)
        sql = f"""SELECT trace_id, task_class, start_time, duration_ms, total_cost,
                         model_call_count, tool_call_count, retry_count, success
                  FROM traces WHERE {where}
                  ORDER BY start_time DESC LIMIT ?"""
        params.append(limit)

        rows = self._db.execute(sql, tuple(params))
        return [
            RunSummary(
                trace_id=r["trace_id"],
                task_class=r["task_class"],
                start_time=datetime.fromisoformat(r["start_time"]),
                duration_ms=r["duration_ms"],
                total_cost=r["total_cost"],
                model_call_count=r["model_call_count"],
                tool_call_count=r["tool_call_count"],
                retry_count=r["retry_count"],
                success=bool(r["success"]),
            )
            for r in rows
        ]

    def get_aggregate_stats(
        self,
        *,
        tenant_id: str | None = None,
        window_hours: int = 168,
    ) -> dict:
        """Compute aggregate stats using SQL aggregation."""
        cutoff = (datetime.now(tz=UTC) - timedelta(hours=window_hours)).isoformat()
        conditions = ["start_time >= ?"]
        params: list[Any] = [cutoff]

        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)

        where = " AND ".join(conditions)
        sql = f"""SELECT
                    COUNT(*) as traces,
                    COALESCE(SUM(total_cost), 0) as total_cost,
                    COALESCE(SUM(total_input_tokens), 0) as total_input_tokens,
                    COALESCE(SUM(total_output_tokens), 0) as total_output_tokens,
                    COALESCE(SUM(model_call_count), 0) as model_calls,
                    COALESCE(SUM(tool_call_count), 0) as tool_calls,
                    COALESCE(SUM(retry_count), 0) as retries,
                    COALESCE(AVG(total_cost), 0) as avg_cost,
                    COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
                    COALESCE(AVG(success), 0) as success_rate
                  FROM traces WHERE {where}"""

        row = self._db.execute_one(sql, tuple(params))
        if not row or row["traces"] == 0:
            return {
                "traces": 0, "total_cost": 0.0, "total_input_tokens": 0,
                "total_output_tokens": 0, "model_calls": 0, "tool_calls": 0,
                "retries": 0, "avg_cost": 0.0, "avg_duration_ms": 0.0, "success_rate": 0.0,
            }

        return {
            "traces": row["traces"],
            "total_cost": round(row["total_cost"], 4),
            "total_input_tokens": row["total_input_tokens"],
            "total_output_tokens": row["total_output_tokens"],
            "model_calls": row["model_calls"],
            "tool_calls": row["tool_calls"],
            "retries": row["retries"],
            "avg_cost": round(row["avg_cost"], 4),
            "avg_duration_ms": round(row["avg_duration_ms"], 2),
            "success_rate": round(row["success_rate"], 4),
        }

    def get_unique_models(self) -> list[str]:
        """Extract unique models from stored trace data."""
        rows = self._db.execute(
            "SELECT DISTINCT json_each.value FROM traces, json_each(json_extract(data, '$.unique_models'))"
        )
        return sorted(r[0] for r in rows if r[0])

    def get_unique_tools(self) -> list[str]:
        """Extract unique tools from stored trace data."""
        rows = self._db.execute(
            "SELECT DISTINCT json_each.value FROM traces, json_each(json_extract(data, '$.unique_tools'))"
        )
        return sorted(r[0] for r in rows if r[0])

    def evict_expired(self) -> int:
        """Alias for cleanup compatibility with in-memory store."""
        return self._db.cleanup_old_traces()
