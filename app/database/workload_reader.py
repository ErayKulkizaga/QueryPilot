from dataclasses import dataclass


class WorkloadReaderError(RuntimeError):
    """Raised when PostgreSQL workload statistics cannot be read."""


@dataclass(frozen=True)
class WorkloadQueryRecord:
    query_id: str
    normalized_sql: str
    calls: int
    total_exec_time_ms: float
    mean_exec_time_ms: float
    result_rows: int
    shared_blocks_read: int
    temp_blocks_written: int


WORKLOAD_QUERY_SQL = """
SELECT
    query_id,
    normalized_sql,
    calls,
    total_exec_time_ms,
    mean_exec_time_ms,
    result_rows,
    shared_blocks_read,
    temp_blocks_written
FROM public.querypilot_workload_queries
WHERE calls >= %s
ORDER BY total_exec_time_ms DESC, calls DESC, query_id ASC
LIMIT %s
"""


def _record_from_row(row: tuple[object, ...]) -> WorkloadQueryRecord:
    return WorkloadQueryRecord(
        query_id=str(row[0]),
        normalized_sql=str(row[1]),
        calls=int(row[2]),
        total_exec_time_ms=float(row[3]),
        mean_exec_time_ms=float(row[4]),
        result_rows=int(row[5]),
        shared_blocks_read=int(row[6]),
        temp_blocks_written=int(row[7]),
    )


class WorkloadReader:
    def __init__(self, *, dsn: str, statement_timeout_ms: int = 3000) -> None:
        self._dsn = dsn
        self._statement_timeout_ms = statement_timeout_ms

    def read(self, *, limit: int, min_calls: int) -> list[WorkloadQueryRecord]:
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
                cursor.execute(WORKLOAD_QUERY_SQL, (min_calls, limit))
                rows = cursor.fetchall()
                connection.rollback()
        except Exception as exc:
            raise WorkloadReaderError(
                "PostgreSQL workload statistics query failed."
            ) from exc

        return [_record_from_row(row) for row in rows]
