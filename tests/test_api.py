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
        baseline_analyses = [
            client.post(
                "/api/v1/analyses",
                json={
                    "sql": (
                        "SELECT * FROM customers "
                        "WHERE email = 'demo@example.com'"
                    )
                },
            ).json()
            for _ in range(3)
        ]
        baseline_response = client.post(
            "/api/v1/baselines",
            json={
                "analysis_ids": [
                    analysis["analysis_id"] for analysis in baseline_analyses
                ],
                "name": "customer email baseline",
                "measurement_group": "warm_cache",
            },
        )
        assert baseline_response.status_code == 201
        baseline = baseline_response.json()
        assert baseline["sample_count"] == 3
        assert baseline["measurement_group"] == "warm_cache"

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
        current_analyses = [
            client.post(
                "/api/v1/analyses",
                json={
                    "sql": (
                        "SELECT * FROM customers "
                        "WHERE email = 'demo@example.com'"
                    )
                },
            ).json()
            for _ in range(2)
        ]
        mismatched_group_response = client.post(
            f"/api/v1/baselines/{baseline['baseline_id']}/comparisons",
            json={
                "analysis_ids": [
                    analysis["analysis_id"] for analysis in current_analyses
                ],
                "measurement_group": "cold_cache",
            },
        )
        comparison_response = client.post(
            f"/api/v1/baselines/{baseline['baseline_id']}/comparisons",
            json={
                "analysis_ids": [
                    analysis["analysis_id"] for analysis in current_analyses
                ],
                "measurement_group": "warm_cache",
            },
        )
        delete_response = client.delete(
            f"/api/v1/baselines/{baseline['baseline_id']}"
        )
        remaining_baselines = client.get("/api/v1/baselines").json()["baselines"]
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert comparison_response.status_code == 200
    assert mismatched_group_response.status_code == 409
    assert "measurement group does not match" in (
        mismatched_group_response.json()["detail"]
    )
    comparison = comparison_response.json()
    assert comparison["regression_detected"] is True
    assert comparison["recommendations_generated"] is False
    assert comparison["execution_time_change_percent"] == 100.0
    assert comparison["baseline_sample_count"] == 3
    assert comparison["current_sample_count"] == 2
    assert comparison["current_measurement_group"] == "warm_cache"
    assert any(
        "sequential scan" in reason
        for reason in comparison["regression_reasons"]
    )

    assert delete_response.status_code == 204
    assert remaining_baselines == []


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
            json={
                "analysis_ids": [first["analysis_id"]],
                "name": "id lookup",
                "measurement_group": "cold_cache",
            },
        ).json()
        second = client.post(
            "/api/v1/analyses",
            json={"sql": "SELECT * FROM customers WHERE id = 2"},
        ).json()
        response = client.post(
            f"/api/v1/baselines/{baseline['baseline_id']}/comparisons",
            json={
                "analysis_ids": [second["analysis_id"]],
                "measurement_group": "cold_cache",
            },
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 409


def test_baseline_export_import_and_markdown_report(
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
                        "Node Type": "Index Scan",
                        "Relation Name": "customers",
                        "Index Name": "customers_pkey",
                        "Plan Rows": 1,
                        "Actual Rows": 1,
                        "Actual Loops": 1,
                        "Total Cost": 8.31,
                        "Actual Total Time": 0.03,
                    },
                    "Planning Time": 0.1,
                    "Execution Time": 0.05,
                }
            ]

    settings = Settings(
        baseline_database_path=tmp_path / "portable-baselines.sqlite3",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.analyses.ExplainRunner", FakeExplainRunner)

    try:
        analysis = client.post(
            "/api/v1/analyses",
            json={"sql": "SELECT * FROM customers WHERE id = 17"},
        ).json()
        baseline = client.post(
            "/api/v1/baselines",
            json={
                "analysis_ids": [analysis["analysis_id"]],
                "name": "release 2 healthy lookup",
                "measurement_group": "warm_cache",
            },
        ).json()

        exported_response = client.get(
            f"/api/v1/baselines/{baseline['baseline_id']}/export"
        )
        report_response = client.get(
            f"/api/v1/baselines/{baseline['baseline_id']}/report"
        )
        imported_response = client.post(
            "/api/v1/baselines/imports",
            json=exported_response.json(),
        )

        corrupted = exported_response.json()
        corrupted["query_fingerprint"] = "0" * 64
        corrupted_response = client.post(
            "/api/v1/baselines/imports",
            json=corrupted,
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert exported_response.status_code == 200
    exported = exported_response.json()
    assert exported["schema_version"] == 1
    assert exported["measurement_group"] == "warm_cache"
    assert exported["plan"]["nodes"][0]["index_name"] == "customers_pkey"

    assert report_response.status_code == 200
    assert report_response.headers["content-type"].startswith("text/markdown")
    assert "# QueryPilot plan baseline" in report_response.text
    assert "Evidence report only" in report_response.text

    assert imported_response.status_code == 201
    assert imported_response.json()["baseline_id"] != baseline["baseline_id"]
    assert imported_response.json()["measurement_group"] == "warm_cache"

    assert corrupted_response.status_code == 422
    assert "fingerprint does not match" in corrupted_response.json()["detail"]
