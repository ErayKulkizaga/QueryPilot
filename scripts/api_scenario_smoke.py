import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]

CASES = (
    {
        "name": "missing-index",
        "request": {"scenario_id": "missing_customer_email_index"},
        "expected_category": "potential_missing_index",
        "expected_insufficient_context": False,
    },
    {
        "name": "healthy-primary-key",
        "request": {
            "sql": "SELECT id, email, full_name FROM customers WHERE id = 17"
        },
        "expected_category": "no_clear_issue",
        "expected_insufficient_context": True,
    },
)


def main() -> None:
    results = []
    with TestClient(app) as client:
        for case in CASES:
            response = client.post("/api/v1/analyses", json=case["request"])
            response.raise_for_status()
            payload = response.json()
            passed = (
                payload["issue_category"] == case["expected_category"]
                and payload["insufficient_context"]
                is case["expected_insufficient_context"]
            )
            results.append(
                {
                    "name": case["name"],
                    "passed": passed,
                    "issue_category": payload["issue_category"],
                    "insufficient_context": payload["insufficient_context"],
                    "plan_evidence": payload["plan_evidence"],
                    "latency_ms": payload["latency_ms"],
                    "report_source": payload["report_source"],
                }
            )

    output = {
        "scenario_count": len(results),
        "passed_count": sum(result["passed"] for result in results),
        "results": results,
    }
    results_path = ROOT / "evaluation" / "api_scenario_smoke_result.json"
    results_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    if output["passed_count"] != output["scenario_count"]:
        raise SystemExit("One or more release scenarios failed.")


if __name__ == "__main__":
    main()
