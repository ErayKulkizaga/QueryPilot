import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import Settings, get_settings
from app.database.workload_reader import WorkloadReader, WorkloadReaderError
from app.schemas import WorkloadQuery, WorkloadQueryListResponse

router = APIRouter(prefix="/api/v1/workload", tags=["workload"])
PARAMETER_PATTERN = re.compile(r"\$\d+\b")


@router.get("/queries", response_model=WorkloadQueryListResponse)
def list_workload_queries(
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> WorkloadQueryListResponse:
    try:
        records = WorkloadReader(
            dsn=settings.database_url,
            statement_timeout_ms=settings.statement_timeout_ms,
        ).read(limit=limit, min_calls=settings.workload_min_calls)
    except WorkloadReaderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local PostgreSQL workload statistics are unavailable.",
        ) from exc

    queries = [
        WorkloadQuery(
            rank=rank,
            query_id=record.query_id,
            normalized_sql=record.normalized_sql,
            calls=record.calls,
            total_exec_time_ms=round(record.total_exec_time_ms, 3),
            mean_exec_time_ms=round(record.mean_exec_time_ms, 3),
            result_rows=record.result_rows,
            shared_blocks_read=record.shared_blocks_read,
            temp_blocks_written=record.temp_blocks_written,
            ranking_reason=(
                f"Ranked #{rank} by total execution time "
                f"({record.total_exec_time_ms:.3f} ms across {record.calls} calls)."
            ),
            requires_representative_sql=bool(
                PARAMETER_PATTERN.search(record.normalized_sql)
            ),
        )
        for rank, record in enumerate(records, start=1)
    ]

    return WorkloadQueryListResponse(
        captured_at=datetime.now(UTC),
        ranking_basis="total_exec_time_ms",
        recommendations_generated=False,
        queries=queries,
    )
