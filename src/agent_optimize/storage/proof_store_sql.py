"""SQLite-backed proof and canary store."""

from __future__ import annotations

import structlog

from agent_optimize.models.proof import Canary, SavingsProof
from agent_optimize.storage.database import Database, deserialize_json, serialize_json

logger = structlog.get_logger()


class SqliteProofStore:
    """SQLite-backed storage for savings proofs."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def store(self, proof: SavingsProof) -> None:
        self._db.insert(
            """INSERT OR REPLACE INTO proofs
               (proof_id, recommendation_id, status, actual_savings_pct, quality_preserved, data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (proof.proof_id, proof.recommendation_id, proof.status.value,
             proof.actual_savings_pct, 1 if proof.quality_preserved else 0, serialize_json(proof)),
        )

    def get(self, proof_id: str) -> SavingsProof | None:
        row = self._db.execute_one("SELECT data FROM proofs WHERE proof_id = ?", (proof_id,))
        if not row:
            return None
        return SavingsProof.model_validate(deserialize_json(row["data"]))

    def list_proofs(self, recommendation_id: str | None = None, limit: int = 50) -> list[SavingsProof]:
        if recommendation_id:
            rows = self._db.execute(
                "SELECT data FROM proofs WHERE recommendation_id = ? ORDER BY created_at DESC LIMIT ?",
                (recommendation_id, limit),
            )
        else:
            rows = self._db.execute(
                "SELECT data FROM proofs ORDER BY created_at DESC LIMIT ?", (limit,),
            )
        return [SavingsProof.model_validate(deserialize_json(r["data"])) for r in rows]

    @property
    def count(self) -> int:
        return self._db.count("proofs")


class SqliteCanaryStore:
    """SQLite-backed storage for canary deployments."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def store(self, canary: Canary) -> None:
        self._db.insert(
            """INSERT OR REPLACE INTO canaries
               (canary_id, recommendation_id, status, data)
               VALUES (?, ?, ?, ?)""",
            (canary.canary_id, canary.recommendation_id, canary.status.value, serialize_json(canary)),
        )

    def get(self, canary_id: str) -> Canary | None:
        row = self._db.execute_one("SELECT data FROM canaries WHERE canary_id = ?", (canary_id,))
        if not row:
            return None
        return Canary.model_validate(deserialize_json(row["data"]))

    def list_canaries(self, limit: int = 50) -> list[Canary]:
        rows = self._db.execute(
            "SELECT data FROM canaries ORDER BY created_at DESC LIMIT ?", (limit,),
        )
        return [Canary.model_validate(deserialize_json(r["data"])) for r in rows]

    @property
    def count(self) -> int:
        return self._db.count("canaries")
