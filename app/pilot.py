from __future__ import annotations

import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import psycopg
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.analysis.plan_comparator import query_fingerprint
from app.analysis.plan_parser import parse_explain
from app.analysis.sql_validator import validate_read_only_sql
from app.analysis.workload_handoff import prepare_representative_sql


class PilotConfigurationError(ValueError):
    """Raised when a non-production pilot is not safely configured."""


class PilotExecutionError(RuntimeError):
    """Raised when a pilot target or query cannot be measured safely."""


class PilotQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    sql: str = Field(min_length=1, max_length=20_000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        name = value.strip()
        if not name or "\n" in name or "\r" in name:
            raise ValueError("Pilot query names must be non-empty single lines.")
        return name

    @field_validator("sql")
    @classmethod
    def validate_sql(cls, value: str) -> str:
        representative_sql = prepare_representative_sql(value)
        return validate_read_only_sql(representative_sql)


class PilotManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    target_label: str = Field(min_length=1, max_length=100)
    measurement_group: Literal["cold_cache", "warm_cache"]
    repetitions: int = Field(default=5, ge=3, le=9)
    queries: list[PilotQuery] = Field(min_length=1, max_length=20)

    @field_validator("target_label")
    @classmethod
    def validate_target_label(cls, value: str) -> str:
        label = value.strip()
        if not label or "\n" in label or "\r" in label:
            raise ValueError("Pilot target label must be a non-empty single line.")
        return label

    @model_validator(mode="after")
    def require_unique_query_names(self) -> PilotManifest:
        names = [query.name.casefold() for query in self.queries]
        if len(names) != len(set(names)):
            raise ValueError("Pilot query names must be unique.")
        return self


def load_pilot_manifest(path: Path) -> PilotManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PilotConfigurationError("Pilot manifest could not be read.") from exc
    if not isinstance(payload, dict):
        raise PilotConfigurationError("Pilot manifest must be a JSON object.")
    try:
        return PilotManifest.model_validate(payload)
    except ValueError as exc:
        raise PilotConfigurationError("Pilot manifest failed validation.") from exc


def calibrate_execution_threshold(samples_ms: list[float]) -> dict[str, Any]:
    if len(samples_ms) < 3:
        raise PilotConfigurationError(
            "Threshold calibration requires at least three execution samples."
        )
    if any(sample < 0 for sample in samples_ms):
        raise PilotConfigurationError("Execution samples cannot be negative.")

    sample_median = float(statistics.median(samples_ms))
    absolute_deviations = [
        abs(sample - sample_median) for sample in samples_ms
    ]
    median_absolute_deviation = float(statistics.median(absolute_deviations))
    observed_noise_delta = median_absolute_deviation * 3
    recommended_delta = max(1.0, observed_noise_delta)
    raw_ratio = (
        1.0 + (observed_noise_delta / sample_median)
        if sample_median > 0
        else 1.5
    )
    recommended_ratio = max(1.5, min(raw_ratio, 10.0))

    return {
        "sample_count": len(samples_ms),
        "median_execution_time_ms": round(sample_median, 6),
        "min_execution_time_ms": round(min(samples_ms), 6),
        "max_execution_time_ms": round(max(samples_ms), 6),
        "median_absolute_deviation_ms": round(
            median_absolute_deviation,
            6,
        ),
        "recommended_execution_ratio": round(recommended_ratio, 6),
        "recommended_execution_delta_ms": round(recommended_delta, 6),
        "ratio_capped_at_product_limit": raw_ratio > 10.0,
    }


def _target_metadata(cursor: psycopg.Cursor[Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT
            current_database(),
            current_user,
            current_setting('server_version'),
            current_setting('transaction_read_only')::boolean,
            role.rolsuper,
            role.rolcreaterole,
            role.rolcreatedb,
            role.rolreplication,
            role.rolbypassrls
        FROM pg_catalog.pg_roles AS role
        WHERE role.rolname = current_user
        """
    )
    row = cursor.fetchone()
    if row is None:
        raise PilotExecutionError("Pilot could not verify the connected role.")
    return {
        "database": row[0],
        "user": row[1],
        "server_version": row[2],
        "transaction_read_only": bool(row[3]),
        "privileged": any(bool(value) for value in row[4:9]),
    }


def _summarize_sample(payload: Any, *, include_execution: bool) -> dict[str, Any]:
    plan = parse_explain(payload)
    return {
        "planning_time_ms": round(plan.planning_time_ms, 6),
        "execution_time_ms": (
            round(plan.execution_time_ms, 6) if include_execution else None
        ),
        "root_node_type": plan.root.node_type,
        "root_total_cost": round(plan.root.total_cost, 6),
        "node_count": len(plan.nodes),
        "shared_read_blocks": round(
            sum(node.shared_read_blocks for node in plan.nodes),
            6,
        ),
        "temp_written_blocks": round(
            sum(node.temp_written_blocks for node in plan.nodes),
            6,
        ),
    }


def _measure_query(
    cursor: psycopg.Cursor[Any],
    query: PilotQuery,
    *,
    repetitions: int,
    allow_explain_analyze: bool,
) -> dict[str, Any]:
    options = (
        "ANALYZE, BUFFERS, FORMAT JSON"
        if allow_explain_analyze
        else "FORMAT JSON"
    )
    sample_count = repetitions if allow_explain_analyze else 1
    samples: list[dict[str, Any]] = []
    try:
        for _ in range(sample_count):
            cursor.execute(f"EXPLAIN ({options}) {query.sql}")
            row = cursor.fetchone()
            if row is None:
                raise PilotExecutionError(
                    f"Pilot query {query.name!r} returned no plan."
                )
            samples.append(
                _summarize_sample(
                    row[0],
                    include_execution=allow_explain_analyze,
                )
            )
    except PilotExecutionError:
        raise
    except Exception as exc:
        raise PilotExecutionError(
            f"Pilot query {query.name!r} failed; no credentials were recorded."
        ) from exc

    result: dict[str, Any] = {
        "name": query.name,
        "query_fingerprint": query_fingerprint(query.sql),
        "sample_count": sample_count,
        "plan_samples": samples,
        "recommendations_generated": False,
    }
    if allow_explain_analyze:
        result["threshold_calibration"] = calibrate_execution_threshold(
            [
                float(sample["execution_time_ms"])
                for sample in samples
                if sample["execution_time_ms"] is not None
            ]
        )
    return result


def run_non_production_pilot(
    *,
    dsn: str,
    expected_database: str,
    manifest: PilotManifest,
    statement_timeout_ms: int = 3000,
    allow_explain_analyze: bool = False,
) -> dict[str, Any]:
    if not dsn.strip():
        raise PilotConfigurationError("Pilot database URL is required.")
    if not expected_database.strip():
        raise PilotConfigurationError("Expected database name is required.")
    if not 100 <= statement_timeout_ms <= 30_000:
        raise PilotConfigurationError(
            "Pilot statement timeout must be between 100 and 30000 ms."
        )

    try:
        connection = psycopg.connect(
            dsn,
            autocommit=False,
            connect_timeout=5,
            application_name="querypilot_nonprod_pilot",
        )
    except Exception as exc:
        raise PilotExecutionError(
            "Pilot database connection failed; no credentials were recorded."
        ) from exc

    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{statement_timeout_ms}ms",),
            )
            cursor.execute(
                "SELECT set_config('lock_timeout', %s, true)",
                ("1000ms",),
            )
            target = _target_metadata(cursor)
            if not target["transaction_read_only"]:
                raise PilotExecutionError(
                    "Pilot refused a connection that was not transaction read-only."
                )
            if target["database"] != expected_database:
                raise PilotExecutionError(
                    "Pilot target mismatch: connected database does not match "
                    "the explicitly expected database name."
                )
            if target["privileged"]:
                raise PilotExecutionError(
                    "Pilot refused a privileged PostgreSQL role; use a dedicated "
                    "least-privilege read-only role."
                )

            query_results = [
                _measure_query(
                    cursor,
                    query,
                    repetitions=manifest.repetitions,
                    allow_explain_analyze=allow_explain_analyze,
                )
                for query in manifest.queries
            ]
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()

    calibration = None
    if allow_explain_analyze:
        query_calibrations = [
            result["threshold_calibration"] for result in query_results
        ]
        calibration = {
            "recommended_global_execution_ratio": max(
                calibration["recommended_execution_ratio"]
                for calibration in query_calibrations
            ),
            "recommended_global_execution_delta_ms": max(
                calibration["recommended_execution_delta_ms"]
                for calibration in query_calibrations
            ),
            "automatically_applied": False,
            "requires_human_review": True,
        }

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target": {
            "label": manifest.target_label,
            "database": target["database"],
            "user": target["user"],
            "server_version": target["server_version"],
            "transaction_read_only": target["transaction_read_only"],
            "privileged_role": target["privileged"],
        },
        "run_mode": (
            "explain_analyze" if allow_explain_analyze else "plan_only"
        ),
        "measurement_group": manifest.measurement_group,
        "statement_timeout_ms": statement_timeout_ms,
        "query_count": len(query_results),
        "queries": query_results,
        "threshold_calibration": calibration,
        "credentials_recorded": False,
        "recommendations_generated": False,
        "thresholds_automatically_applied": False,
        "claim_boundary": (
            "Authorized non-production evidence only. Review calibrated "
            "thresholds and plans with a DBA before any production decision."
        ),
    }
