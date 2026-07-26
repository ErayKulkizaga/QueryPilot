from fastapi.testclient import TestClient

from app.llm.generator import GenerationResult
from app.main import app
from app.schemas import AnalysisReport, Citation

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analysis_rejects_unsafe_sql_before_database_access() -> None:
    response = client.post(
        "/api/v1/analyses",
        json={"sql": "DELETE FROM customers"},
    )

    assert response.status_code == 422
    assert "Only SELECT" in response.json()["detail"]


def test_analysis_requires_one_input() -> None:
    response = client.post("/api/v1/analyses", json={})

    assert response.status_code == 422


def test_analysis_returns_fast_result_then_grounded_enrichment(
    monkeypatch,
) -> None:
    class FakeExplainRunner:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, _: str) -> list[dict[str, object]]:
            return [
                {
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Relation Name": "customers",
                        "Plan Rows": 1,
                        "Actual Rows": 1,
                        "Actual Loops": 1,
                        "Rows Removed by Filter": 24_999,
                        "Filter": "(email = 'demo@example.com'::text)",
                    },
                    "Execution Time": 3.7,
                }
            ]

    class FakeReportingService:
        def generate(self, analysis) -> GenerationResult:
            finding = analysis.primary
            return GenerationResult(
                report=AnalysisReport(
                    issue_category=finding.category,
                    severity=finding.severity,
                    summary="Grounded local explanation.",
                    plan_evidence=list(finding.evidence),
                    recommendation=finding.recommendation,
                    recommendation_sql=finding.recommendation_sql,
                    citations=[
                        Citation(
                            document_id="pg-indexes-01",
                            title="PostgreSQL Indexes and Selective Predicates",
                            section="Selective predicates",
                        )
                    ],
                    insufficient_context=False,
                ),
                source="foundry_local",
                repair_attempted=False,
                generation_latency_ms=25,
            )

    monkeypatch.setattr("app.api.analyses.ExplainRunner", FakeExplainRunner)
    monkeypatch.setattr(
        "app.api.analyses.get_reporting_service",
        lambda settings: FakeReportingService(),
    )

    analysis_response = client.post(
        "/api/v1/analyses",
        json={"sql": "SELECT * FROM customers WHERE email = 'demo@example.com'"},
    )

    assert analysis_response.status_code == 200
    analysis_payload = analysis_response.json()
    assert analysis_payload["report_source"] == "deterministic"
    assert analysis_payload["enrichment_available"] is True
    assert analysis_payload["insufficient_context"] is False
    assert analysis_payload["citations"] == []

    enrichment_response = client.post(
        f"/api/v1/analyses/{analysis_payload['analysis_id']}/enrichment"
    )

    assert enrichment_response.status_code == 200
    enrichment_payload = enrichment_response.json()
    assert enrichment_payload["report_source"] == "foundry_local"
    assert enrichment_payload["insufficient_context"] is False
    assert enrichment_payload["citations"][0]["document_id"] == "pg-indexes-01"


def test_enrichment_rejects_unknown_analysis_id() -> None:
    response = client.post("/api/v1/analyses/not-a-real-id/enrichment")

    assert response.status_code == 404
