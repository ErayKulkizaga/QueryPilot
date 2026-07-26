import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        health.raise_for_status()
        analysis = client.post(
            "/api/v1/analyses",
            json={"scenario_id": "missing_customer_email_index"},
        )
        analysis.raise_for_status()
        analysis_payload = analysis.json()
        enrichment = client.post(
            f"/api/v1/analyses/{analysis_payload['analysis_id']}/enrichment"
        )
        enrichment.raise_for_status()

    enrichment_payload = enrichment.json()
    output = {
        "health": health.json(),
        "analysis": {
            "analysis_id": analysis_payload["analysis_id"],
            "issue_category": analysis_payload["issue_category"],
            "severity": analysis_payload["severity"],
            "plan_evidence": analysis_payload["plan_evidence"],
            "recommendation_sql": analysis_payload["recommendation_sql"],
            "insufficient_context": analysis_payload["insufficient_context"],
            "latency_ms": analysis_payload["latency_ms"],
            "report_source": analysis_payload["report_source"],
            "enrichment_available": analysis_payload["enrichment_available"],
        },
        "enrichment": {
            "citations": enrichment_payload["citations"],
            "insufficient_context": enrichment_payload["insufficient_context"],
            "latency_ms": enrichment_payload["latency_ms"],
            "generation_latency_ms": enrichment_payload["generation_latency_ms"],
            "repair_attempted": enrichment_payload["repair_attempted"],
            "report_source": enrichment_payload["report_source"],
        },
    }
    results_path = ROOT / "evaluation" / "api_smoke_result.json"
    results_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
