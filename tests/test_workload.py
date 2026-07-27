from pathlib import Path

from fastapi.testclient import TestClient

from app.database.workload_reader import (
    WORKLOAD_QUERY_SQL,
    WorkloadQueryRecord,
    WorkloadReaderError,
    _record_from_row,
)
from app.main import app

client = TestClient(app)


def test_workload_reader_maps_rows_and_uses_deterministic_order() -> None:
    record = _record_from_row(
        (
            "-123",
            "SELECT count(*) FROM orders WHERE total_amount > $1",
            7,
            140.5,
            20.071,
            7,
            240,
            0,
        )
    )

    assert record.query_id == "-123"
    assert record.calls == 7
    assert record.shared_blocks_read == 240
    assert (
        "ORDER BY total_exec_time_ms DESC, calls DESC, query_id ASC"
        in WORKLOAD_QUERY_SQL
    )


def test_workload_api_returns_ranked_candidates_without_recommendations(
    monkeypatch,
) -> None:
    class FakeWorkloadReader:
        def __init__(self, **_: object) -> None:
            pass

        def read(
            self,
            *,
            limit: int,
            min_calls: int,
        ) -> list[WorkloadQueryRecord]:
            assert limit == 10
            assert min_calls == 2
            return [
                WorkloadQueryRecord(
                    query_id="-123",
                    normalized_sql=(
                        "SELECT count(*) FROM orders WHERE total_amount > $1"
                    ),
                    calls=7,
                    total_exec_time_ms=140.5,
                    mean_exec_time_ms=20.071,
                    result_rows=7,
                    shared_blocks_read=240,
                    temp_blocks_written=0,
                ),
                WorkloadQueryRecord(
                    query_id="456",
                    normalized_sql="SELECT id FROM customers WHERE id = $1",
                    calls=20,
                    total_exec_time_ms=12.0,
                    mean_exec_time_ms=0.6,
                    result_rows=20,
                    shared_blocks_read=2,
                    temp_blocks_written=0,
                ),
            ]

    monkeypatch.setattr(
        "app.api.workload.WorkloadReader",
        FakeWorkloadReader,
    )

    response = client.get("/api/v1/workload/queries")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_basis"] == "total_exec_time_ms"
    assert payload["recommendations_generated"] is False
    assert [query["rank"] for query in payload["queries"]] == [1, 2]
    assert payload["queries"][0]["requires_representative_sql"] is True
    assert "140.500 ms across 7 calls" in payload["queries"][0]["ranking_reason"]
    assert "recommendation" not in payload["queries"][0]


def test_workload_api_rejects_invalid_limit() -> None:
    response = client.get("/api/v1/workload/queries?limit=0")

    assert response.status_code == 422


def test_workload_api_returns_safe_unavailable_error(monkeypatch) -> None:
    class FailingWorkloadReader:
        def __init__(self, **_: object) -> None:
            pass

        def read(self, **_: object) -> list[WorkloadQueryRecord]:
            raise WorkloadReaderError("database details")

    monkeypatch.setattr(
        "app.api.workload.WorkloadReader",
        FailingWorkloadReader,
    )

    response = client.get("/api/v1/workload/queries")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "The local PostgreSQL workload statistics are unavailable."
    )
    assert "database details" not in response.text


def test_workload_sql_exposes_only_least_privilege_projection() -> None:
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "004_workload_stats.sql"
    sql = sql_path.read_text(encoding="utf-8")

    assert "SECURITY DEFINER" in sql
    assert "REVOKE ALL ON FUNCTION" in sql
    assert "REVOKE ALL ON public.pg_stat_statements FROM PUBLIC" in sql
    assert "REVOKE ALL ON public.pg_stat_statements FROM querypilot_app" in sql
    assert "GRANT EXECUTE ON FUNCTION" in sql
    assert "REVOKE ALL ON public.querypilot_workload_queries FROM PUBLIC" in sql
    assert "GRANT SELECT ON public.querypilot_workload_queries TO querypilot_app" in sql
    assert "statement.query ~* '^\\s*(SELECT|WITH)\\M'" in sql
    assert "statement.query !~* '^\\s*SELECT\\s+set_config\\('" in sql
    assert "statement.query !~* '^\\s*SELECT\\s+CASE\\s+WHEN\\s+to_regclass\\('" in sql
