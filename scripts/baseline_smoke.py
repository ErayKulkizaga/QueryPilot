from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "evaluation" / "baseline_smoke_result.json"
REQUEST = {"scenario_id": "missing_customer_email_index"}


def main() -> None:
    with TestClient(app) as client:
        baseline_analysis = client.post("/api/v1/analyses", json=REQUEST)
        baseline_analysis.raise_for_status()
        baseline_payload = baseline_analysis.json()

        baseline_response = client.post(
            "/api/v1/baselines",
            json={
                "analysis_id": baseline_payload["analysis_id"],
                "name": "live missing-index smoke baseline",
            },
        )
        baseline_response.raise_for_status()
        baseline = baseline_response.json()

        current_analysis = client.post("/api/v1/analyses", json=REQUEST)
        current_analysis.raise_for_status()
        current_payload = current_analysis.json()

        comparison_response = client.post(
            f"/api/v1/baselines/{baseline['baseline_id']}/comparisons",
            json={"analysis_id": current_payload["analysis_id"]},
        )
        comparison_response.raise_for_status()
        comparison = comparison_response.json()

    if comparison["recommendations_generated"]:
        raise SystemExit("Plan comparison must never generate recommendations.")
    if comparison["query_fingerprint"] != baseline["query_fingerprint"]:
        raise SystemExit("Baseline and current query fingerprints do not match.")

    output = {
        "captured_at": datetime.now(UTC).isoformat(),
        "baseline_id": baseline["baseline_id"],
        "query_fingerprint": comparison["query_fingerprint"],
        "baseline_execution_time_ms": comparison["baseline_execution_time_ms"],
        "current_execution_time_ms": comparison["current_execution_time_ms"],
        "execution_time_delta_ms": comparison["execution_time_delta_ms"],
        "root_cost_delta": comparison["root_cost_delta"],
        "node_count_delta": comparison["node_count_delta"],
        "regression_detected": comparison["regression_detected"],
        "regression_reasons": comparison["regression_reasons"],
        "recommendations_generated": comparison["recommendations_generated"],
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
