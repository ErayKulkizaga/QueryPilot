from fastapi.testclient import TestClient

from app.config import Settings, get_settings
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


def test_baseline_create_list_and_compare_are_evidence_only(
    monkeypatch,
    tmp_path,
) -> None:
    plan_state = {
        "node_type": "Index Scan",
        "index_name": "customers_email_idx",
        "execution_time": 2.0,
        "total_cost": 10.0,
    }

    class MutableExplainRunner:
        def __init__(self, **_: object) -> None:
            pass

        def run(self, _: str) -> list[dict[str, object]]:
            plan: dict[str, object] = {
                "Node Type": plan_state["node_type"],
                "Relation Name": "customers",
                "Plan Rows": 1,
                "Actual Rows": 1,
                "Actual Loops": 1,
                "Total Cost": plan_state["total_cost"],
                "Actual Total Time": plan_state["execution_time"],
            }
            if plan_state["index_name"]:
                plan["Index Name"] = plan_state["index_name"]
            return [
                {
                    "Plan": plan,
                    "Execution Time": plan_state["execution_time"],
                }
            ]

    settings = Settings(
        baseline_database_path=tmp_path / "baselines.sqlite3",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.analyses.ExplainRunner", MutableExplainRunner)

    try:
        baseline_analysis = client.post(
            "/api/v1/analyses",
            json={"sql": "SELECT * FROM customers WHERE email = 'demo@example.com'"},
        ).json()
        baseline_response = client.post(
            "/api/v1/baselines",
            json={
                "analysis_id": baseline_analysis["analysis_id"],
                "name": "customer email baseline",
            },
        )
        assert baseline_response.status_code == 201
        baseline = baseline_response.json()

        listed = client.get("/api/v1/baselines").json()["baselines"]
        assert [item["baseline_id"] for item in listed] == [baseline["baseline_id"]]

        plan_state.update(
            {
                "node_type": "Seq Scan",
                "index_name": None,
                "execution_time": 4.0,
                "total_cost": 15.0,
            }
        )
        current_analysis = client.post(
            "/api/v1/analyses",
            json={"sql": "SELECT * FROM customers WHERE email = 'demo@example.com'"},
        ).json()
        comparison_response = client.post(
            f"/api/v1/baselines/{baseline['baseline_id']}/comparisons",
            json={"analysis_id": current_analysis["analysis_id"]},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert comparison_response.status_code == 200
    comparison = comparison_response.json()
    assert comparison["regression_detected"] is True
    assert comparison["recommendations_generated"] is False
    assert comparison["execution_time_change_percent"] == 100.0
    assert any(
        "sequential scan" in reason
        for reason in comparison["regression_reasons"]
    )


def test_baseline_comparison_rejects_different_query(
    monkeypatch,
    tmp_path,
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
                        "Total Cost": 10,
                        "Actual Total Time": 2,
                    },
                    "Execution Time": 2,
                }
            ]

    settings = Settings(
        baseline_database_path=tmp_path / "baselines.sqlite3",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.analyses.ExplainRunner", FakeExplainRunner)

    try:
        first = client.post(
            "/api/v1/analyses",
            json={"sql": "SELECT * FROM customers WHERE id = 1"},
        ).json()
        baseline = client.post(
            "/api/v1/baselines",
            json={"analysis_id": first["analysis_id"], "name": "id lookup"},
        ).json()
        second = client.post(
            "/api/v1/analyses",
            json={"sql": "SELECT * FROM customers WHERE id = 2"},
        ).json()
        response = client.post(
            f"/api/v1/baselines/{baseline['baseline_id']}/comparisons",
            json={"analysis_id": second["analysis_id"]},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 409
