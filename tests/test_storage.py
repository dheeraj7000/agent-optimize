"""Tests for SQLite persistence layer."""

import asyncio
from datetime import UTC, datetime, timedelta

from agent_optimize.auth.middleware import ApiKeyManager, generate_api_key, hash_key
from agent_optimize.storage.database import Database
from agent_optimize.storage.trace_store import SqliteTraceStore

from tests.conftest import make_trace


class TestDatabase:
    def test_schema_created(self, sqlite_db: Database):
        tables = sqlite_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = {r["name"] for r in tables}
        assert "traces" in table_names
        assert "recommendations" in table_names
        assert "proofs" in table_names
        assert "api_keys" in table_names
        assert "audit_log" in table_names

    def test_schema_version(self, sqlite_db: Database):
        row = sqlite_db.execute_one("SELECT MAX(version) as v FROM schema_version")
        assert row["v"] == 1

    def test_count(self, sqlite_db: Database):
        assert sqlite_db.count("traces") == 0


class TestSqliteTraceStore:
    def test_store_and_retrieve(self, sqlite_db: Database):
        store = SqliteTraceStore(sqlite_db)
        trace = make_trace(trace_id="t-1", tenant_id="tenant-a")
        asyncio.get_event_loop().run_until_complete(store.store(trace))

        assert store.trace_count == 1
        retrieved = store.get_trace("t-1")
        assert retrieved is not None
        assert retrieved.trace_id == "t-1"
        assert retrieved.tenant_id == "tenant-a"

    def test_query_by_tenant(self, sqlite_db: Database):
        store = SqliteTraceStore(sqlite_db)
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="t-1", tenant_id="a"))
        )
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="t-2", tenant_id="b"))
        )
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="t-3", tenant_id="a"))
        )

        results = store.query_traces(tenant_id="a")
        assert len(results) == 2

        results_b = store.query_traces(tenant_id="b")
        assert len(results_b) == 1

    def test_query_by_success(self, sqlite_db: Database):
        store = SqliteTraceStore(sqlite_db)
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="ok", success=True))
        )
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="fail", success=False))
        )

        ok = store.query_traces(success_only=True)
        assert len(ok) == 1
        assert ok[0].trace_id == "ok"

    def test_aggregate_stats(self, sqlite_db: Database):
        store = SqliteTraceStore(sqlite_db)
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="t1", total_cost=0.5))
        )
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="t2", total_cost=1.5))
        )

        stats = store.get_aggregate_stats()
        assert stats["traces"] == 2
        assert stats["total_cost"] == 2.0
        assert stats["avg_cost"] == 1.0

    def test_run_summaries(self, sqlite_db: Database):
        store = SqliteTraceStore(sqlite_db)
        asyncio.get_event_loop().run_until_complete(
            store.store(make_trace(trace_id="t1", tenant_id="x"))
        )
        summaries = store.get_run_summaries(tenant_id="x")
        assert len(summaries) == 1
        assert summaries[0].trace_id == "t1"

    def test_get_nonexistent_trace(self, sqlite_db: Database):
        store = SqliteTraceStore(sqlite_db)
        assert store.get_trace("does-not-exist") is None


class TestApiKeyManager:
    def test_create_and_validate(self, sqlite_db: Database):
        mgr = ApiKeyManager(sqlite_db)
        raw_key = mgr.create_key("tenant-1", "my key")

        assert raw_key.startswith("ao_live_")
        tenant = mgr.validate_key(raw_key)
        assert tenant == "tenant-1"

    def test_invalid_key_returns_none(self, sqlite_db: Database):
        mgr = ApiKeyManager(sqlite_db)
        assert mgr.validate_key("ao_live_bogus") is None

    def test_revoke_key(self, sqlite_db: Database):
        mgr = ApiKeyManager(sqlite_db)
        raw_key = mgr.create_key("tenant-1", "revoke-me")

        assert mgr.validate_key(raw_key) == "tenant-1"
        mgr.revoke_key(raw_key)
        assert mgr.validate_key(raw_key) is None

    def test_list_keys(self, sqlite_db: Database):
        mgr = ApiKeyManager(sqlite_db)
        mgr.create_key("tenant-1", "key-a")
        mgr.create_key("tenant-1", "key-b")
        mgr.create_key("tenant-2", "key-c")

        keys = mgr.list_keys("tenant-1")
        assert len(keys) == 2

    def test_hash_key_deterministic(self):
        assert hash_key("test") == hash_key("test")
        assert hash_key("a") != hash_key("b")

    def test_generate_key_unique(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2
        assert k1.startswith("ao_live_")
