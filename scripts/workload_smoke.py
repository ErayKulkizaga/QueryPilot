from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from app.config import get_settings
from app.database.workload_reader import WorkloadReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation" / "workload_smoke_result.json"
DEFAULT_OWNER_DSN = (
    "postgresql://querypilot_owner:querypilot_owner_dev@127.0.0.1:5432/querypilot"
)

SLOW_QUERY = "SELECT count(*) FROM orders WHERE total_amount > 500"
FAST_QUERY = "SELECT id FROM customers WHERE id = 17"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify deterministic pg_stat_statements workload ranking."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON result path.",
    )
    return parser.parse_args()


def reset_statistics(owner_dsn: str) -> None:
    with (
        psycopg.connect(owner_dsn, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT pg_stat_statements_reset()")


def generate_workload(app_dsn: str) -> None:
    with (
        psycopg.connect(app_dsn, autocommit=True) as connection,
        connection.cursor() as cursor,
    ):
        for _ in range(6):
            cursor.execute(SLOW_QUERY)
            cursor.fetchone()
        for _ in range(15):
            cursor.execute(FAST_QUERY)
            cursor.fetchone()


def verify_direct_access_is_denied(app_dsn: str) -> bool:
    try:
        with (
            psycopg.connect(app_dsn, autocommit=True) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT query FROM public.pg_stat_statements LIMIT 1")
            cursor.fetchone()
    except psycopg.errors.InsufficientPrivilege:
        return True
    return False


def main() -> None:
    args = parse_args()
    settings = get_settings()
    owner_dsn = os.getenv("QUERYPILOT_OWNER_DATABASE_URL", DEFAULT_OWNER_DSN)

    reset_statistics(owner_dsn)
    generate_workload(settings.database_url)
    direct_access_denied = verify_direct_access_is_denied(settings.database_url)
    records = WorkloadReader(
        dsn=settings.database_url,
        statement_timeout_ms=settings.statement_timeout_ms,
    ).read(limit=10, min_calls=2)

    if not records:
        raise SystemExit("Workload reader returned no eligible SELECT statements.")
    top = records[0]
    if "FROM orders" not in top.normalized_sql:
        raise SystemExit(
            "Expected the repeated orders scan to rank first by total execution time."
        )
    if not direct_access_denied:
        raise SystemExit("Application role could read pg_stat_statements directly.")

    result = {
        "captured_at": datetime.now(UTC).isoformat(),
        "ranking_basis": "total_exec_time_ms",
        "recommendations_generated": False,
        "direct_pg_stat_statements_access_denied": True,
        "top_query": {
            "query_id": top.query_id,
            "normalized_sql": top.normalized_sql,
            "calls": top.calls,
            "total_exec_time_ms": round(top.total_exec_time_ms, 3),
            "mean_exec_time_ms": round(top.mean_exec_time_ms, 3),
            "shared_blocks_read": top.shared_blocks_read,
            "temp_blocks_written": top.temp_blocks_written,
        },
        "eligible_query_count": len(records),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
