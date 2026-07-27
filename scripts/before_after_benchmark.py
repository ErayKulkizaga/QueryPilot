from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "evaluation" / "before_after_benchmark.json"
DEFAULT_DSN = (
    "postgresql://querypilot_owner:querypilot_owner_dev@localhost:5432/querypilot"
)
QUERY = (
    "SELECT id, email, full_name FROM customers "
    "WHERE email = 'demo@example.com'"
)
INDEX_NAME = "idx_customers_email"
INDEX_SQL = f"CREATE INDEX {INDEX_NAME} ON customers (email)"


def _walk_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = [node]
    for child in node.get("Plans", []):
        nodes.extend(_walk_nodes(child))
    return nodes


def summarize_plan(payload: list[dict[str, Any]]) -> dict[str, Any]:
    document = payload[0]
    root = document["Plan"]
    nodes = _walk_nodes(root)
    return {
        "root_node": root["Node Type"],
        "node_types": [node["Node Type"] for node in nodes],
        "index_names": sorted(
            {
                node["Index Name"]
                for node in nodes
                if isinstance(node.get("Index Name"), str)
            }
        ),
        "planning_time_ms": document.get("Planning Time"),
        "execution_time_ms": document.get("Execution Time"),
        "shared_hit_blocks": sum(node.get("Shared Hit Blocks", 0) for node in nodes),
        "shared_read_blocks": sum(node.get("Shared Read Blocks", 0) for node in nodes),
        "rows_removed_by_filter": sum(
            node.get("Rows Removed by Filter", 0) for node in nodes
        ),
    }


def measure(connection: psycopg.Connection[Any], repetitions: int) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    with connection.cursor() as cursor:
        for _ in range(repetitions):
            cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {QUERY}")
            payload = cursor.fetchone()[0]
            samples.append(summarize_plan(payload))

    execution_times = [sample["execution_time_ms"] for sample in samples]
    median_time = statistics.median(execution_times)
    representative = min(
        samples,
        key=lambda sample: abs(sample["execution_time_ms"] - median_time),
    )
    return {
        "repetitions": repetitions,
        "median_execution_time_ms": round(median_time, 4),
        "min_execution_time_ms": round(min(execution_times), 4),
        "max_execution_time_ms": round(max(execution_times), 4),
        "representative_plan": representative,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure the QueryPilot fixture before and after its recommended index."
    )
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_PATH,
        help="JSON result path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repetitions < 3:
        raise SystemExit("--repetitions must be at least 3")

    dsn = os.environ.get("QUERYPILOT_BENCHMARK_DATABASE_URL", DEFAULT_DSN)
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
                cursor.execute("ANALYZE customers")
                cursor.execute("SELECT count(*) FROM customers")
                customer_count = cursor.fetchone()[0]

            before = measure(connection, args.repetitions)

            with connection.cursor() as cursor:
                cursor.execute(INDEX_SQL)
                cursor.execute("ANALYZE customers")

            after = measure(connection, args.repetitions)
        finally:
            # Restore the missing-index fixture expected by the default demo.
            with connection.cursor() as cursor:
                cursor.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
                cursor.execute("ANALYZE customers")

    before_ms = before["median_execution_time_ms"]
    after_ms = after["median_execution_time_ms"]
    output = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "fixture": {
            "database": "querypilot",
            "customer_count": customer_count,
            "query": QUERY,
            "recommended_index_sql": f"{INDEX_SQL};",
            "fixture_restored_without_index": True,
        },
        "before": before,
        "after": after,
        "observed_speedup_ratio": (
            round(before_ms / after_ms, 2) if after_ms and before_ms else None
        ),
        "claim_boundary": (
            "This is a local synthetic-fixture observation, not a production "
            "performance guarantee."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
