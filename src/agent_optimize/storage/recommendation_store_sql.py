"""SQLite-backed recommendation store — persists recommendations, proofs, and canaries.

Drop-in replacement for the in-memory RecommendationStore with the same query interface.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import structlog

from agent_optimize.models.recommendations import (
    Recommendation,
    RecommendationPriority,
    RecommendationStatus,
    RecommendationSummary,
)
from agent_optimize.models.waste import WasteCategory
from agent_optimize.storage.database import Database, deserialize_json, serialize_json

logger = structlog.get_logger()

# Valid lifecycle transitions (same as in-memory store)
_VALID_TRANSITIONS: dict[RecommendationStatus, set[RecommendationStatus]] = {
    RecommendationStatus.PENDING: {RecommendationStatus.ACCEPTED, RecommendationStatus.REJECTED},
    RecommendationStatus.ACCEPTED: {
        RecommendationStatus.REPLAYING, RecommendationStatus.DEPLOYED, RecommendationStatus.REJECTED,
    },
    RecommendationStatus.REPLAYING: {RecommendationStatus.VALIDATED, RecommendationStatus.REJECTED},
    RecommendationStatus.VALIDATED: {RecommendationStatus.DEPLOYED, RecommendationStatus.REJECTED},
    RecommendationStatus.DEPLOYED: {RecommendationStatus.VERIFIED, RecommendationStatus.ROLLED_BACK},
    RecommendationStatus.REJECTED: set(),
    RecommendationStatus.VERIFIED: set(),
    RecommendationStatus.ROLLED_BACK: {RecommendationStatus.PENDING},
}


class SqliteRecommendationStore:
    """SQLite-backed recommendation store with lifecycle management."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def count(self) -> int:
        return self._db.count("recommendations")

    def store(self, rec: Recommendation) -> Recommendation:
        self._db.insert(
            """INSERT OR REPLACE INTO recommendations
               (recommendation_id, tenant_id, status, priority, category, title,
                business_value_score, monthly_savings, annual_savings, confidence, data, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.recommendation_id, rec.tenant_id, rec.status.value, rec.priority.value,
                rec.category.value, rec.title, rec.business_value_score,
                rec.impact.monthly_savings, rec.impact.annual_savings,
                rec.confidence.overall.value, serialize_json(rec),
                datetime.now(tz=UTC).isoformat(),
            ),
        )
        return rec

    def store_batch(self, recs: list[Recommendation]) -> list[Recommendation]:
        for rec in recs:
            self.store(rec)
        return recs

    def get(self, recommendation_id: str) -> Recommendation | None:
        row = self._db.execute_one(
            "SELECT data FROM recommendations WHERE recommendation_id = ?", (recommendation_id,),
        )
        if not row:
            return None
        return Recommendation.model_validate(deserialize_json(row["data"]))

    def transition(
        self, recommendation_id: str, new_status: RecommendationStatus,
        actor: str = "user", notes: str = "",
    ) -> Recommendation:
        rec = self.get(recommendation_id)
        if rec is None:
            raise ValueError(f"Recommendation {recommendation_id} not found")

        valid_next = _VALID_TRANSITIONS.get(rec.status, set())
        if new_status not in valid_next:
            raise ValueError(
                f"Cannot transition from {rec.status.value} to {new_status.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )

        old_status = rec.status
        rec.status = new_status
        rec.updated_at = datetime.now(tz=UTC)
        rec.status_history.append({
            "status": new_status.value, "from_status": old_status.value,
            "timestamp": rec.updated_at.isoformat(), "actor": actor, "notes": notes,
        })
        self.store(rec)

        logger.info("recommendation_store_sql.transitioned",
                     id=recommendation_id, from_status=old_status.value, to_status=new_status.value)
        return rec

    def link_replay(self, recommendation_id: str, experiment_id: str) -> Recommendation:
        rec = self.get(recommendation_id)
        if rec is None:
            raise ValueError(f"Recommendation {recommendation_id} not found")
        rec.replay_experiment_id = experiment_id
        rec.updated_at = datetime.now(tz=UTC)
        self.store(rec)
        return rec

    def query(
        self, *, tenant_id: str | None = None, status: RecommendationStatus | None = None,
        category: WasteCategory | None = None, priority: RecommendationPriority | None = None,
        min_savings: float | None = None, limit: int = 100,
    ) -> list[Recommendation]:
        conditions: list[str] = []
        params: list = []

        if tenant_id:
            conditions.append("tenant_id = ?")
            params.append(tenant_id)
        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if category:
            conditions.append("category = ?")
            params.append(category.value)
        if priority:
            conditions.append("priority = ?")
            params.append(priority.value)
        if min_savings is not None:
            conditions.append("monthly_savings >= ?")
            params.append(min_savings)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT data FROM recommendations WHERE {where} ORDER BY business_value_score DESC LIMIT ?"
        params.append(limit)

        rows = self._db.execute(sql, tuple(params))
        return [Recommendation.model_validate(deserialize_json(r["data"])) for r in rows]

    def get_summaries(
        self, *, tenant_id: str | None = None, status: RecommendationStatus | None = None, limit: int = 100,
    ) -> list[RecommendationSummary]:
        recs = self.query(tenant_id=tenant_id, status=status, limit=limit)
        return [
            RecommendationSummary(
                recommendation_id=r.recommendation_id, status=r.status, priority=r.priority,
                category=r.category, title=r.title, monthly_savings=r.impact.monthly_savings,
                annual_savings=r.impact.annual_savings, confidence=r.confidence.overall,
                quality_risk=r.impact.quality_risk, created_at=r.created_at,
            )
            for r in recs
        ]

    def get_stats(self, tenant_id: str | None = None) -> dict:
        recs = self.query(tenant_id=tenant_id, limit=10000)
        if not recs:
            return {"total": 0, "by_status": {}, "by_priority": {}, "by_category": {},
                    "total_identified_savings": 0.0, "total_accepted_savings": 0.0,
                    "total_verified_savings": 0.0}

        by_status: dict[str, int] = defaultdict(int)
        by_priority: dict[str, int] = defaultdict(int)
        by_category: dict[str, int] = defaultdict(int)
        total = accepted = verified = 0.0

        for r in recs:
            by_status[r.status.value] += 1
            by_priority[r.priority.value] += 1
            by_category[r.category.value] += 1
            total += r.impact.monthly_savings
            if r.status in (RecommendationStatus.ACCEPTED, RecommendationStatus.REPLAYING,
                            RecommendationStatus.VALIDATED, RecommendationStatus.DEPLOYED,
                            RecommendationStatus.VERIFIED):
                accepted += r.impact.monthly_savings
            if r.status == RecommendationStatus.VERIFIED:
                verified += r.impact.monthly_savings

        return {"total": len(recs), "by_status": dict(by_status), "by_priority": dict(by_priority),
                "by_category": dict(by_category), "total_identified_savings": round(total, 2),
                "total_accepted_savings": round(accepted, 2), "total_verified_savings": round(verified, 2)}
