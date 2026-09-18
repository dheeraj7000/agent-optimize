"""Abstract storage backend — allows swapping SQLite, Postgres, or ClickHouse.

The backend interface is minimal: store, get, query, count.
Each implementation handles its own connection management and SQL dialect.
"""

from __future__ import annotations

import abc
import os
from typing import Any

import structlog

logger = structlog.get_logger()


class StorageBackend(abc.ABC):
    """Abstract storage backend interface."""

    @abc.abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> list[Any]: ...

    @abc.abstractmethod
    def execute_one(self, sql: str, params: tuple = ()) -> Any | None: ...

    @abc.abstractmethod
    def insert(self, sql: str, params: tuple = ()) -> None: ...

    @abc.abstractmethod
    def count(self, table: str, where: str = "", params: tuple = ()) -> int: ...


class PostgresBackend(StorageBackend):
    """Postgres storage backend using psycopg (sync for compatibility).

    Requires: pip install psycopg[binary]
    Config: AGENTOPTIMIZE_DB_URL=postgresql://user:pass@host:5432/dbname
    """

    def __init__(self, db_url: str) -> None:
        try:
            import psycopg  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Postgres backend requires psycopg. Install with: pip install 'psycopg[binary]'"
            ) from e

        self._conn_str = db_url
        self._init_schema()
        logger.info("storage.postgres", url=db_url.split("@")[-1] if "@" in db_url else "***")

    def _get_conn(self):
        import psycopg
        return psycopg.connect(self._conn_str)

    def _init_schema(self) -> None:
        """Create tables if they don't exist. Postgres-compatible DDL."""
        schema = """
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            tenant_id TEXT,
            task_class TEXT,
            start_time TIMESTAMPTZ,
            end_time TIMESTAMPTZ,
            duration_ms DOUBLE PRECISION,
            total_cost DOUBLE PRECISION,
            total_input_tokens INTEGER,
            total_output_tokens INTEGER,
            model_call_count INTEGER,
            tool_call_count INTEGER,
            retry_count INTEGER,
            success BOOLEAN,
            source_framework TEXT,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_traces_tenant ON traces(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_traces_time ON traces(start_time);

        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id TEXT PRIMARY KEY,
            tenant_id TEXT,
            status TEXT,
            priority TEXT,
            category TEXT,
            title TEXT,
            business_value_score DOUBLE PRECISION,
            monthly_savings DOUBLE PRECISION,
            annual_savings DOUBLE PRECISION,
            confidence TEXT,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_recs_status ON recommendations(status);

        CREATE TABLE IF NOT EXISTS proofs (
            proof_id TEXT PRIMARY KEY,
            recommendation_id TEXT,
            status TEXT,
            actual_savings_pct DOUBLE PRECISION,
            quality_preserved BOOLEAN,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS canaries (
            canary_id TEXT PRIMARY KEY,
            recommendation_id TEXT,
            status TEXT,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            status TEXT,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            key_hash TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS webhook_configs (
            webhook_id TEXT PRIMARY KEY,
            tenant_id TEXT,
            url TEXT,
            name TEXT,
            active BOOLEAN DEFAULT TRUE,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        with self._get_conn() as conn:
            conn.execute(schema)
            conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> list[Any]:
        # Convert ? placeholders to %s for psycopg
        sql = sql.replace("?", "%s")
        with self._get_conn() as conn:
            cur = conn.execute(sql, params)
            if cur.description:
                cols = [d.name for d in cur.description]
                return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
            return []

    def execute_one(self, sql: str, params: tuple = ()) -> Any | None:
        rows = self.execute(sql, params)
        return rows[0] if rows else None

    def insert(self, sql: str, params: tuple = ()) -> None:
        sql = sql.replace("?", "%s")
        with self._get_conn() as conn:
            conn.execute(sql, params)
            conn.commit()

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        if where:
            sql += f" WHERE {where}"
        row = self.execute_one(sql.replace("?", "%s"), params)
        return row["cnt"] if row else 0


def create_storage_backend() -> tuple[Any, Any]:
    """Factory: create the appropriate storage backend from environment.

    Returns (warehouse, db) tuple.
    """
    backend = os.environ.get("AGENTOPTIMIZE_DB_BACKEND", "").lower()
    db_url = os.environ.get("AGENTOPTIMIZE_DB_URL", "")
    db_path = os.environ.get("AGENTOPTIMIZE_DB_PATH", "")

    if backend == "postgres" or db_url.startswith("postgres"):
        pg = PostgresBackend(db_url)
        logger.info("storage.backend", type="postgres")
        return None, pg  # Trace store wraps the backend

    if db_path:
        from agent_optimize.storage.database import Database
        from agent_optimize.storage.trace_store import SqliteTraceStore
        db = Database(db_path)
        logger.info("storage.backend", type="sqlite", path=db_path)
        return SqliteTraceStore(db), db

    # Default: in-memory
    logger.info("storage.backend", type="memory")
    return None, None
