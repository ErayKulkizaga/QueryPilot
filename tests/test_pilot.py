from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app import pilot
from app.pilot import (
    PilotConfigurationError,
    PilotExecutionError,
    PilotManifest,
    calibrate_execution_threshold,
    load_pilot_manifest,
    run_non_production_pilot,
)
from scripts import non_production_pilot


def _plan(execution_time_ms: float = 2.0) -> list[dict[str, Any]]:
    return [
        {
            "Plan": {
                "Node Type": "Seq Scan",
                "Relation Name": "orders",
                "Plan Rows": 1,
                "Actual Rows": 1,
                "Actual Loops": 1,
                "Total Cost": 10.0,
                "Actual Total Time": execution_time_ms,
                "Shared Read Blocks": 2,
            },
            "Planning Time": 0.1,
            "Execution Time": execution_time_ms,
        }
    ]


class FakeCursor:
    def __init__(
        self,
        *,
        database: str = "querypilot",
        privileged: bool = False,
        execution_times: list[float] | None = None,
    ) -> None:
        self.database = database
        self.privileged = privileged
        self.execution_times = iter(execution_times or [2.0])
        self.executed: list[str] = []
        self._row: tuple[Any, ...] | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(
        self,
        query: str,
        _params: tuple[str, ...] | None = None,
    ) -> None:
        self.executed.append(query)
        if "FROM pg_catalog.pg_roles" in query:
            self._row = (
                self.database,
                "querypilot_reader",
                "17.5",
                True,
                self.privileged,
                False,
                False,
                False,
                False,
            )
        elif query.startswith("EXPLAIN"):
            self._row = (_plan(next(self.execution_times, 2.0)),)
        else:
            self._row = None

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def _manifest(*, repetitions: int = 3) -> PilotManifest:
    return PilotManifest.model_validate(
        {
            "schema_version": 1,
            "target_label": "authorized-staging",
            "measurement_group": "warm_cache",
            "repetitions": repetitions,
            "queries": [
                {
                    "name": "orders-count",
                    "sql": (
                        "SELECT count(*) FROM orders "
                        "WHERE total_amount > 250.00"
                    ),
                }
            ],
        }
    )


def _install_fake_connection(
    monkeypatch: pytest.MonkeyPatch,
    cursor: FakeCursor,
) -> FakeConnection:
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        pilot.psycopg,
        "connect",
        lambda *_args, **_kwargs: connection,
    )
    return connection


def test_manifest_rejects_placeholders_writes_and_duplicate_names() -> None:
    with pytest.raises(ValidationError):
        PilotManifest.model_validate(
            {
                "target_label": "staging",
                "measurement_group": "warm_cache",
                "queries": [{"name": "unsafe", "sql": "SELECT * FROM t WHERE id = $1"}],
            }
        )
    with pytest.raises(ValidationError):
        PilotManifest.model_validate(
            {
                "target_label": "staging",
                "measurement_group": "warm_cache",
                "queries": [{"name": "unsafe", "sql": "UPDATE t SET value = 1"}],
            }
        )
    with pytest.raises(ValidationError):
        PilotManifest.model_validate(
            {
                "target_label": "staging",
                "measurement_group": "warm_cache",
                "queries": [
                    {"name": "same", "sql": "SELECT 1"},
                    {"name": "SAME", "sql": "SELECT 2"},
                ],
            }
        )


def test_manifest_file_errors_do_not_echo_contents(tmp_path: Path) -> None:
    manifest_path = tmp_path / "pilot.json"
    manifest_path.write_text('{"password": "do-not-echo"}', encoding="utf-8")

    with pytest.raises(PilotConfigurationError) as exc_info:
        load_pilot_manifest(manifest_path)

    assert "do-not-echo" not in str(exc_info.value)


def test_threshold_calibration_is_conservative() -> None:
    result = calibrate_execution_threshold([10.0, 10.5, 11.0, 30.0, 10.5])
    sub_millisecond = calibrate_execution_threshold([0.060, 0.061, 0.063])

    assert result["median_execution_time_ms"] == 10.5
    assert result["median_absolute_deviation_ms"] == 0.5
    assert result["recommended_execution_delta_ms"] == 1.5
    assert result["recommended_execution_ratio"] == 1.5
    assert sub_millisecond["recommended_execution_ratio"] == 1.5
    assert sub_millisecond["ratio_capped_at_product_limit"] is False


def test_plan_only_pilot_does_not_execute_or_record_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor()
    connection = _install_fake_connection(monkeypatch, cursor)
    secret_dsn = "postgresql://reader:top-secret@db.example.test/querypilot"

    result = run_non_production_pilot(
        dsn=secret_dsn,
        expected_database="querypilot",
        manifest=_manifest(),
    )

    assert result["run_mode"] == "plan_only"
    assert result["threshold_calibration"] is None
    assert result["credentials_recorded"] is False
    assert "top-secret" not in json.dumps(result)
    explain = next(query for query in cursor.executed if query.startswith("EXPLAIN"))
    assert "ANALYZE" not in explain
    assert connection.rolled_back is True
    assert connection.closed is True


def test_analyze_pilot_calibrates_without_applying_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = FakeCursor(execution_times=[5.0, 5.2, 5.1])
    _install_fake_connection(monkeypatch, cursor)

    result = run_non_production_pilot(
        dsn="postgresql://safe",
        expected_database="querypilot",
        manifest=_manifest(),
        allow_explain_analyze=True,
    )

    assert result["run_mode"] == "explain_analyze"
    assert result["queries"][0]["sample_count"] == 3
    assert result["threshold_calibration"]["automatically_applied"] is False
    assert result["thresholds_automatically_applied"] is False
    assert result["recommendations_generated"] is False
    explain_queries = [
        query for query in cursor.executed if query.startswith("EXPLAIN")
    ]
    assert len(explain_queries) == 3
    assert all("ANALYZE" in query for query in explain_queries)


@pytest.mark.parametrize(
    ("database", "privileged"),
    [("wrong_database", False), ("querypilot", True)],
)
def test_pilot_refuses_wrong_target_or_privileged_role(
    monkeypatch: pytest.MonkeyPatch,
    database: str,
    privileged: bool,
) -> None:
    cursor = FakeCursor(database=database, privileged=privileged)
    connection = _install_fake_connection(monkeypatch, cursor)

    with pytest.raises(PilotExecutionError):
        run_non_production_pilot(
            dsn="postgresql://safe",
            expected_database="querypilot",
            manifest=_manifest(),
        )

    assert not any(query.startswith("EXPLAIN") for query in cursor.executed)
    assert connection.rolled_back is True
    assert connection.closed is True


def test_cli_requires_explicit_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "non_production_pilot",
            str(tmp_path / "manifest.json"),
            "--expected-database",
            "querypilot",
            "--output",
            str(tmp_path / "result.json"),
        ],
    )

    with pytest.raises(SystemExit, match="Pilot refused"):
        non_production_pilot.main()


def test_cli_requires_dsn_only_after_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(non_production_pilot.PILOT_DSN_ENV, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "non_production_pilot",
            str(tmp_path / "manifest.json"),
            "--expected-database",
            "querypilot",
            "--output",
            str(tmp_path / "result.json"),
            "--acknowledge-authorized-non-production",
        ],
    )

    with pytest.raises(SystemExit, match=non_production_pilot.PILOT_DSN_ENV):
        non_production_pilot.main()
