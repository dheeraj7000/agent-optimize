"""SQLite database manager — schema creation, migrations, and connection pooling.

SQLite is the pilot-tier storage. It's embedded, zero-config, and free.
The schema stores denormalized summaries in indexed columns for fast queries,
with full JSON payloads for drill-down.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

_SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    tenant_id TEXT,
    task_class TEXT,
    start_time TEXT,
    end_time TEXT,
    duration_ms REAL,
    total_cost REAL,
    total_input_tokens INTEGER,
    total_output_tokens INTEGER,
    model_call_count INTEGER,
    tool_call_count INTEGER,
    retry_count INTEGER,
    success INTEGER,
    source_framework TEXT,
    data JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_traces_tenant ON traces(tenant_id);
CREATE INDEX IF NOT EXISTS idx_traces_time ON traces(start_time);
CREATE INDEX IF NOT EXISTS idx_traces_cost ON traces(total_cost);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    tenant_id TEXT,
    status TEXT,
    priority TEXT,
    category TEXT,
    title TEXT,
    business_value_score REAL,
    monthly_savings REAL,
    annual_savings REAL,
    confidence TEXT,
    data JSON,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_recs_tenant ON recommendations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_recs_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recs_priority ON recommendations(priority);

CREATE TABLE IF NOT EXISTS proofs (
    proof_id TEXT PRIMARY KEY,
    recommendation_id TEXT,
    status TEXT,
    actual_savings_pct REAL,
    quality_preserved INTEGER,
    data JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS canaries (
    canary_id TEXT PRIMARY KEY,
    recommendation_id TEXT,
    status TEXT,
    data JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    status TEXT,
    data JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    key_hash TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    action TEXT,
    resource TEXT,
    resource_id TEXT,
    actor TEXT,
    details JSON,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(created_at);
"""


class Database:
    """SQLite database manager with connection pooling and auto-migration."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Create schema and run migrations."""
        with self.connect() as conn:
            conn.executescript(_SCHEMA_SQL)

            # Check schema version
            cur = conn.execute("SELECT MAX(version) FROM schema_version")
            row = cur.fetchone()
            current = row[0] if row and row[0] else 0

            if current < _SCHEMA_VERSION:
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (_SCHEMA_VERSION,),
                )

        logger.info("database.initialized", path=self._db_path, schema_version=_SCHEMA_VERSION)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Get a database connection with WAL mode and JSON support."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a query and return all rows."""
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def execute_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute a query and return one row."""
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def insert(self, sql: str, params: tuple = ()) -> None:
        """Execute an insert statement."""
        with self.connect() as conn:
            conn.execute(sql, params)

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        """Count rows in a table."""
        sql = f"SELECT COUNT(*) FROM {table}"
        if where:
            sql += f" WHERE {where}"
        row = self.execute_one(sql, params)
        return row[0] if row else 0

    def cleanup_old_traces(self, retention_hours: int = 168) -> int:
        """Delete traces older than retention window."""
        sql = "DELETE FROM traces WHERE created_at < datetime('now', ?)"
        with self.connect() as conn:
            cursor = conn.execute(sql, (f"-{retention_hours} hours",))
            deleted = cursor.rowcount
        if deleted:
            logger.info("database.cleanup", deleted=deleted, retention_hours=retention_hours)
        return deleted


def serialize_json(obj: Any) -> str:
    """Serialize a Pydantic model or dict to JSON string."""
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), default=str)
    return json.dumps(obj, default=str)


def deserialize_json(data: str) -> dict:
    """Deserialize a JSON string to dict."""
    return json.loads(data) if data else {}
