from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.analysis.plan_comparator import (
    PlanSnapshot,
    snapshot_from_dict,
    snapshot_to_dict,
)


class BaselineNotFoundError(KeyError):
    """Raised when a plan baseline does not exist."""


class BaselineStoreError(RuntimeError):
    """Raised when the local baseline database cannot be used."""


@dataclass(frozen=True, slots=True)
class PlanBaseline:
    baseline_id: str
    name: str
    query_fingerprint: str
    normalized_sql: str
    plan: PlanSnapshot
    created_at: datetime


class SQLiteBaselineStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS plan_baselines (
                        baseline_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        query_fingerprint TEXT NOT NULL,
                        normalized_sql TEXT NOT NULL,
                        plan_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_plan_baselines_created_at
                    ON plan_baselines(created_at DESC)
                    """
                )
        except (OSError, sqlite3.Error) as exc:
            raise BaselineStoreError("Could not initialize the baseline store.") from exc

    @staticmethod
    def _from_row(row: sqlite3.Row) -> PlanBaseline:
        try:
            payload = json.loads(row["plan_json"])
            plan = snapshot_from_dict(payload)
            created_at = datetime.fromisoformat(row["created_at"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BaselineStoreError("Stored baseline data is invalid.") from exc
        return PlanBaseline(
            baseline_id=row["baseline_id"],
            name=row["name"],
            query_fingerprint=row["query_fingerprint"],
            normalized_sql=row["normalized_sql"],
            plan=plan,
            created_at=created_at,
        )

    def create(
        self,
        *,
        name: str,
        query_fingerprint: str,
        normalized_sql: str,
        plan: PlanSnapshot,
    ) -> PlanBaseline:
        record = PlanBaseline(
            baseline_id=uuid4().hex,
            name=name,
            query_fingerprint=query_fingerprint,
            normalized_sql=normalized_sql,
            plan=plan,
            created_at=datetime.now(UTC),
        )
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO plan_baselines (
                        baseline_id,
                        name,
                        query_fingerprint,
                        normalized_sql,
                        plan_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.baseline_id,
                        record.name,
                        record.query_fingerprint,
                        record.normalized_sql,
                        json.dumps(
                            snapshot_to_dict(record.plan),
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                        record.created_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise BaselineStoreError("Could not save the plan baseline.") from exc
        return record

    def get(self, baseline_id: str) -> PlanBaseline:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT baseline_id, name, query_fingerprint, normalized_sql,
                           plan_json, created_at
                    FROM plan_baselines
                    WHERE baseline_id = ?
                    """,
                    (baseline_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise BaselineStoreError("Could not read the plan baseline.") from exc
        if row is None:
            raise BaselineNotFoundError(baseline_id)
        return self._from_row(row)

    def list(self, *, limit: int = 100) -> list[PlanBaseline]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT baseline_id, name, query_fingerprint, normalized_sql,
                           plan_json, created_at
                    FROM plan_baselines
                    ORDER BY created_at DESC, baseline_id ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise BaselineStoreError("Could not list plan baselines.") from exc
        return [self._from_row(row) for row in rows]


@lru_cache(maxsize=8)
def get_baseline_store(database_path: Path) -> SQLiteBaselineStore:
    return SQLiteBaselineStore(database_path)
