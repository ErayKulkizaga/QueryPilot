from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.pilot import (
    PilotConfigurationError,
    PilotExecutionError,
    load_pilot_manifest,
    run_non_production_pilot,
)

PILOT_DSN_ENV = "QUERYPILOT_PILOT_DATABASE_URL"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a guarded QueryPilot measurement against an explicitly "
            "authorized non-production PostgreSQL database."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=3000,
    )
    parser.add_argument(
        "--acknowledge-authorized-non-production",
        action="store_true",
        help="Confirm that the operator is authorized to measure this target.",
    )
    parser.add_argument(
        "--allow-explain-analyze",
        action="store_true",
        help=(
            "Execute each allowlisted SELECT with EXPLAIN ANALYZE. Without "
            "this flag, QueryPilot only requests non-executing plans."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.acknowledge_authorized_non_production:
        raise SystemExit(
            "Pilot refused: add --acknowledge-authorized-non-production only "
            "after target authorization is confirmed."
        )
    dsn = os.getenv(PILOT_DSN_ENV, "")
    if not dsn:
        raise SystemExit(
            f"Pilot refused: provide the connection only through {PILOT_DSN_ENV}."
        )

    try:
        manifest = load_pilot_manifest(args.manifest)
        result = run_non_production_pilot(
            dsn=dsn,
            expected_database=args.expected_database,
            manifest=manifest,
            statement_timeout_ms=args.statement_timeout_ms,
            allow_explain_analyze=args.allow_explain_analyze,
        )
    except (PilotConfigurationError, PilotExecutionError) as exc:
        raise SystemExit(str(exc)) from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Pilot completed in {result['run_mode']} mode for "
        f"{result['query_count']} allowlisted queries. "
        f"Sanitized report: {args.output}"
    )


if __name__ == "__main__":
    main()
