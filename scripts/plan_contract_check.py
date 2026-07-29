from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.analysis.plan_contracts import PlanContractSet, evaluate_plan_contract
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT_PATH = ROOT / "contracts" / "plan_contracts.json"
DEFAULT_OUTPUT_PATH = ROOT / "evaluation" / "plan_contract_result.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify checked-in query plan contracts against PostgreSQL."
    )
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def load_contracts(path: Path) -> PlanContractSet:
    return PlanContractSet.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    contract_set = load_contracts(args.contracts)
    results: list[dict[str, object]] = []

    with TestClient(app) as client:
        for contract in contract_set.contracts:
            response = client.post(
                "/api/v1/analyses",
                json={"sql": contract.sql},
            )
            response.raise_for_status()
            analysis = response.json()
            evaluation = evaluate_plan_contract(
                contract,
                issue_category=analysis["issue_category"],
                insufficient_context=analysis["insufficient_context"],
                raw_plan=analysis["raw_plan"],
            )
            results.append(
                {
                    "name": contract.name,
                    "release": contract.release,
                    "passed": evaluation.passed,
                    "errors": evaluation.errors,
                    "observed_issue_category": (
                        evaluation.observed_issue_category
                    ),
                    "observed_node_types": evaluation.observed_node_types,
                }
            )

    output = {
        "captured_at": datetime.now(UTC).isoformat(),
        "schema_version": contract_set.schema_version,
        "contract_count": len(results),
        "passed_count": sum(bool(result["passed"]) for result in results),
        "contracts": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))

    failures = [result for result in results if not result["passed"]]
    if failures:
        failed_names = ", ".join(str(result["name"]) for result in failures)
        raise SystemExit(f"Plan contracts failed: {failed_names}")


if __name__ == "__main__":
    main()
