import json
from collections import Counter
from pathlib import Path

from app.analysis.plan_parser import parse_explain
from app.analysis.rule_engine import analyze_plan, build_fallback_report

ROOT = Path(__file__).resolve().parents[1]


def load_scenarios() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (ROOT / "evaluation" / "scenarios.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def test_evaluation_dataset_has_required_distribution() -> None:
    scenarios = load_scenarios()
    distribution = Counter(str(item["expected_category"]) for item in scenarios)

    assert len(scenarios) == 12
    assert distribution["potential_missing_index"] == 3
    assert distribution["expensive_nested_loop"] == 2
    assert distribution["disk_based_sort"] == 2
    assert distribution["cardinality_misestimation"] == 2
    assert distribution["no_clear_issue"] == 3
    assert sum(bool(item["evaluate_generation"]) for item in scenarios) == 4


def test_all_fixture_diagnoses_and_no_answer_labels_match() -> None:
    for scenario in load_scenarios():
        analysis = analyze_plan(parse_explain(scenario["plan"]))
        report = build_fallback_report(analysis)

        assert analysis.primary.category.value == scenario["expected_category"], scenario[
            "scenario_id"
        ]
        assert (
            report.insufficient_context == scenario["expected_insufficient_context"]
        ), scenario["scenario_id"]

