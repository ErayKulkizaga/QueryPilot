from typing import Any


class ExplainRunnerError(RuntimeError):
    """Raised when PostgreSQL cannot produce a usable EXPLAIN payload."""


class ExplainRunner:
    def __init__(self, *, dsn: str, statement_timeout_ms: int = 3000) -> None:
        self._dsn = dsn
        self._statement_timeout_ms = statement_timeout_ms

    def run(self, validated_sql: str) -> dict[str, Any] | list[Any]:
        try:
            import psycopg

            with (
                psycopg.connect(self._dsn, autocommit=False) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (f"{self._statement_timeout_ms}ms",),
                )
                cursor.execute(
                    "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + validated_sql
                )
                row = cursor.fetchone()
                connection.rollback()
        except Exception as exc:
            raise ExplainRunnerError("PostgreSQL EXPLAIN execution failed.") from exc

        if not row:
            raise ExplainRunnerError("PostgreSQL returned no EXPLAIN result.")
        payload = row[0]
        if not isinstance(payload, (dict, list)):
            raise ExplainRunnerError("PostgreSQL returned an unexpected EXPLAIN format.")
        return payload
