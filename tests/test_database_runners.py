from types import SimpleNamespace

import pytest

from app.database.explain_runner import ExplainRunner, ExplainRunnerError
from app.database.workload_reader import WorkloadReader, WorkloadReaderError


class FakeCursor:
    def __init__(self, *, row=None, rows=None) -> None:
        self.row = row
        self.rows = rows or []
        self.executions: list[tuple[str, object | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, parameters=None) -> None:
        self.executions.append((sql, parameters))

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.rollback_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor

    def rollback(self) -> None:
        self.rollback_count += 1


def _install_fake_psycopg(monkeypatch, connection: FakeConnection) -> None:
    monkeypatch.setitem(
        __import__("sys").modules,
        "psycopg",
        SimpleNamespace(connect=lambda *_args, **_kwargs: connection),
    )


def test_explain_runner_uses_read_only_transaction_and_timeout(monkeypatch) -> None:
    payload = [{"Plan": {"Node Type": "Result"}}]
    cursor = FakeCursor(row=(payload,))
    connection = FakeConnection(cursor)
    _install_fake_psycopg(monkeypatch, connection)

    result = ExplainRunner(
        dsn="postgresql://local",
        statement_timeout_ms=1250,
    ).run("SELECT 1")

    assert result == payload
    assert cursor.executions == [
        ("SET TRANSACTION READ ONLY", None),
        (
            "SELECT set_config('statement_timeout', %s, true)",
            ("1250ms",),
        ),
        ("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT 1", None),
    ]
    assert connection.rollback_count == 1


@pytest.mark.parametrize("row", [None, (), ("not-json",)])
def test_explain_runner_rejects_missing_or_unexpected_payload(
    monkeypatch,
    row,
) -> None:
    connection = FakeConnection(FakeCursor(row=row))
    _install_fake_psycopg(monkeypatch, connection)

    with pytest.raises(ExplainRunnerError):
        ExplainRunner(dsn="postgresql://local").run("SELECT 1")


def test_explain_runner_wraps_database_errors(monkeypatch) -> None:
    def fail_connect(*_args, **_kwargs):
        raise OSError("database details")

    monkeypatch.setitem(
        __import__("sys").modules,
        "psycopg",
        SimpleNamespace(connect=fail_connect),
    )

    with pytest.raises(
        ExplainRunnerError,
        match="PostgreSQL EXPLAIN execution failed",
    ):
        ExplainRunner(dsn="postgresql://local").run("SELECT 1")


def test_workload_reader_executes_bounded_projection(monkeypatch) -> None:
    cursor = FakeCursor(
        rows=[
            (
                "123",
                "SELECT id FROM customers WHERE id = $1",
                4,
                8.0,
                2.0,
                4,
                3,
                0,
            )
        ]
    )
    connection = FakeConnection(cursor)
    _install_fake_psycopg(monkeypatch, connection)

    records = WorkloadReader(
        dsn="postgresql://local",
        statement_timeout_ms=900,
    ).read(limit=5, min_calls=2)

    assert len(records) == 1
    assert records[0].query_id == "123"
    assert cursor.executions[0] == ("SET TRANSACTION READ ONLY", None)
    assert cursor.executions[1][1] == ("900ms",)
    assert cursor.executions[2][1] == (2, 5)
    assert connection.rollback_count == 1


def test_workload_reader_wraps_database_errors(monkeypatch) -> None:
    def fail_connect(*_args, **_kwargs):
        raise OSError("database details")

    monkeypatch.setitem(
        __import__("sys").modules,
        "psycopg",
        SimpleNamespace(connect=fail_connect),
    )

    with pytest.raises(
        WorkloadReaderError,
        match="PostgreSQL workload statistics query failed",
    ):
        WorkloadReader(dsn="postgresql://local").read(limit=5, min_calls=2)
