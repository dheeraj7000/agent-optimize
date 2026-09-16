"""In-memory recommendation store with lifecycle management.

Handles CRUD, lifecycle transitions, and querying for recommendations.
Will be backed by a persistent store in later phases.
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

logger = structlog.get_logger()

# Valid lifecycle transitions
_VALID_TRANSITIONS: dict[RecommendationStatus, set[RecommendationStatus]] = {
    RecommendationStatus.PENDING: {
        RecommendationStatus.ACCEPTED,
        RecommendationStatus.REJECTED,
    },
    RecommendationStatus.ACCEPTED: {
        RecommendationStatus.REPLAYING,
        RecommendationStatus.DEPLOYED,  # Skip replay if team is confident
        RecommendationStatus.REJECTED,
    },
    RecommendationStatus.REPLAYING: {
        RecommendationStatus.VALIDATED,
        RecommendationStatus.REJECTED,
    },
    RecommendationStatus.VALIDATED: {
        RecommendationStatus.DEPLOYED,
        RecommendationStatus.REJECTED,
    },
    RecommendationStatus.DEPLOYED: {
        RecommendationStatus.VERIFIED,
        RecommendationStatus.ROLLED_BACK,
    },
    RecommendationStatus.REJECTED: set(),  # Terminal
    RecommendationStatus.VERIFIED: set(),  # Terminal
    RecommendationStatus.ROLLED_BACK: {
        RecommendationStatus.PENDING,  # Can re-evaluate
    },
}


class RecommendationStore:
    """In-memory store for V2 recommendations with lifecycle management."""

    def __init__(self) -> None:
        self._recommendations: dict[str, Recommendation] = {}
        self._by_tenant: dict[str, set[str]] = defaultdict(set)
        self._by_category: dict[WasteCategory, set[str]] = defaultdict(set)
        self._by_status: dict[RecommendationStatus, set[str]] = defaultdict(set)

    @property
    def count(self) -> int:
        return len(self._recommendations)

    def store(self, rec: Recommendation) -> Recommendation:
        """Store a new recommendation."""
        self._recommendations[rec.recommendation_id] = rec
        self._index(rec)
        logger.debug(
            "recommendation_store.stored",
            id=rec.recommendation_id,
            category=rec.category.value,
            priority=rec.priority.value,
        )
        return rec

    def store_batch(self, recs: list[Recommendation]) -> list[Recommendation]:
        """Store multiple recommendations."""
        for rec in recs:
            self.store(rec)
        return recs

    def get(self, recommendation_id: str) -> Recommendation | None:
        return self._recommendations.get(recommendation_id)

    def transition(
        self,
        recommendation_id: str,
        new_status: RecommendationStatus,
        actor: str = "user",
        notes: str = "",
    ) -> Recommendation:
        """Transition a recommendation to a new lifecycle state.

        Raises ValueError if the transition is not valid.
        """
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            raise ValueError(f"Recommendation {recommendation_id} not found")

        valid_next = _VALID_TRANSITIONS.get(rec.status, set())
        if new_status not in valid_next:
            raise ValueError(
                f"Cannot transition from {rec.status.value} to {new_status.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )

        # Update indexes
        self._by_status[rec.status].discard(rec.recommendation_id)

        old_status = rec.status
        rec.status = new_status
        rec.updated_at = datetime.now(tz=UTC)
        rec.status_history.append({
            "status": new_status.value,
            "from_status": old_status.value,
            "timestamp": rec.updated_at.isoformat(),
            "actor": actor,
            "notes": notes,
        })

        self._by_status[new_status].add(rec.recommendation_id)

        logger.info(
            "recommendation_store.transitioned",
            id=recommendation_id,
            from_status=old_status.value,
            to_status=new_status.value,
            actor=actor,
        )

        return rec

    def link_replay(self, recommendation_id: str, experiment_id: str) -> Recommendation:
        """Link a replay experiment to a recommendation."""
        rec = self._recommendations.get(recommendation_id)
        if rec is None:
            raise ValueError(f"Recommendation {recommendation_id} not found")
        rec.replay_experiment_id = experiment_id
        rec.updated_at = datetime.now(tz=UTC)
        return rec

    def query(
        self,
        *,
        tenant_id: str | None = None,
        status: RecommendationStatus | None = None,
        category: WasteCategory | None = None,
        priority: RecommendationPriority | None = None,
        min_savings: float | None = None,
        limit: int = 100,
    ) -> list[Recommendation]:
        """Query recommendations with filters."""
        # Start with candidate set
        if status is not None and status in self._by_status:
            candidate_ids = set(self._by_status[status])
        elif category is not None and category in self._by_category:
            candidate_ids = set(self._by_category[category])
        elif tenant_id is not None and tenant_id in self._by_tenant:
            candidate_ids = set(self._by_tenant[tenant_id])
        else:
            candidate_ids = set(self._recommendations.keys())

        results: list[Recommendation] = []
        for rid in candidate_ids:
            rec = self._recommendations.get(rid)
            if rec is None:
                continue

            if tenant_id is not None and rec.tenant_id != tenant_id:
                continue
            if status is not None and rec.status != status:
                continue
            if category is not None and rec.category != category:
                continue
            if priority is not None and rec.priority != priority:
                continue
            if min_savings is not None and rec.impact.monthly_savings < min_savings:
                continue

            results.append(rec)
            if len(results) >= limit:
                break

        # Sort by business value score
        results.sort(key=lambda r: r.business_value_score, reverse=True)
        return results

    def get_summaries(
        self,
        *,
        tenant_id: str | None = None,
        status: RecommendationStatus | None = None,
        limit: int = 100,
    ) -> list[RecommendationSummary]:
        """Get lightweight recommendation summaries."""
        recs = self.query(tenant_id=tenant_id, status=status, limit=limit)
        return [_to_summary(r) for r in recs]

    def get_stats(self, tenant_id: str | None = None) -> dict:
        """Get aggregate recommendation statistics."""
        recs = self.query(tenant_id=tenant_id, limit=10000)
        if not recs:
            return {
                "total": 0,
                "by_status": {},
                "by_priority": {},
                "by_category": {},
                "total_identified_savings": 0.0,
                "total_accepted_savings": 0.0,
                "total_verified_savings": 0.0,
            }

        by_status: dict[str, int] = defaultdict(int)
        by_priority: dict[str, int] = defaultdict(int)
        by_category: dict[str, int] = defaultdict(int)
        total_savings = 0.0
        accepted_savings = 0.0
        verified_savings = 0.0

        for r in recs:
            by_status[r.status.value] += 1
            by_priority[r.priority.value] += 1
            by_category[r.category.value] += 1
            total_savings += r.impact.monthly_savings

            if r.status in (
                RecommendationStatus.ACCEPTED,
                RecommendationStatus.REPLAYING,
                RecommendationStatus.VALIDATED,
                RecommendationStatus.DEPLOYED,
                RecommendationStatus.VERIFIED,
            ):
                accepted_savings += r.impact.monthly_savings

            if r.status == RecommendationStatus.VERIFIED:
                verified_savings += r.impact.monthly_savings

        return {
            "total": len(recs),
            "by_status": dict(by_status),
            "by_priority": dict(by_priority),
            "by_category": dict(by_category),
            "total_identified_savings": round(total_savings, 2),
            "total_accepted_savings": round(accepted_savings, 2),
            "total_verified_savings": round(verified_savings, 2),
        }

    def _index(self, rec: Recommendation) -> None:
        if rec.tenant_id:
            self._by_tenant[rec.tenant_id].add(rec.recommendation_id)
        self._by_category[rec.category].add(rec.recommendation_id)
        self._by_status[rec.status].add(rec.recommendation_id)


def _to_summary(rec: Recommendation) -> RecommendationSummary:
    return RecommendationSummary(
        recommendation_id=rec.recommendation_id,
        status=rec.status,
        priority=rec.priority,
        category=rec.category,
        title=rec.title,
        monthly_savings=rec.impact.monthly_savings,
        annual_savings=rec.impact.annual_savings,
        confidence=rec.confidence.overall,
        quality_risk=rec.impact.quality_risk,
        created_at=rec.created_at,
    )
