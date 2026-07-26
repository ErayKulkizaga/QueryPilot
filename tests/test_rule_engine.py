import pytest

from app.analysis.plan_parser import parse_explain
from app.analysis.rule_engine import analyze_plan
from app.schemas import IssueCategory, Severity


def analyze(root: dict, execution_time: float = 20.0):
    plan = parse_explain(
        [{"Plan": root, "Planning Time": 0.5, "Execution Time": execution_time}]
    )
    return analyze_plan(plan)


def test_detects_potential_missing_index() -> None:
    result = analyze(
        {
            "Node Type": "Seq Scan",
            "Relation Name": "customers",
            "Plan Rows": 1,
            "Actual Rows": 1,
            "Actual Loops": 1,
            "Rows Removed by Filter": 19_999,
            "Filter": "(email = 'demo@example.com'::text)",
            "Actual Total Time": 18.6,
        }
    )

    assert result.primary.category == IssueCategory.POTENTIAL_MISSING_INDEX
    assert result.primary.severity == Severity.HIGH
    assert result.primary.recommendation_sql == (
        "CREATE INDEX idx_customers_email ON customers (email);"
    )


def test_detects_expensive_nested_loop() -> None:
    result = analyze(
        {
            "Node Type": "Nested Loop",
            "Plan Rows": 1000,
            "Actual Rows": 1000,
            "Actual Loops": 1,
            "Actual Total Time": 48,
            "Plans": [
                {
                    "Node Type": "Seq Scan",
                    "Relation Name": "customers",
                    "Plan Rows": 1000,
                    "Actual Rows": 1000,
                    "Actual Loops": 1,
                },
                {
                    "Node Type": "Index Scan",
                    "Relation Name": "orders",
                    "Plan Rows": 1,
                    "Actual Rows": 1,
                    "Actual Loops": 1000,
                },
            ],
        }
    )

    assert result.primary.category == IssueCategory.EXPENSIVE_NESTED_LOOP


def test_detects_disk_based_sort() -> None:
    result = analyze(
        {
            "Node Type": "Sort",
            "Plan Rows": 50_000,
            "Actual Rows": 50_000,
            "Actual Loops": 1,
            "Sort Method": "external merge",
            "Sort Space Type": "Disk",
            "Sort Space Used": 24_000,
        }
    )

    assert result.primary.category == IssueCategory.DISK_BASED_SORT


@pytest.mark.parametrize(
    ("planned", "actual"),
    [(10, 1000), (1000, 10)],
)
def test_detects_cardinality_misestimation(planned: int, actual: int) -> None:
    result = analyze(
        {
            "Node Type": "Aggregate",
            "Plan Rows": planned,
            "Actual Rows": actual,
            "Actual Loops": 1,
        }
    )

    assert result.primary.category == IssueCategory.CARDINALITY_MISESTIMATION


def test_returns_no_clear_issue_when_thresholds_are_not_met() -> None:
    result = analyze(
        {
            "Node Type": "Index Scan",
            "Relation Name": "customers",
            "Plan Rows": 10,
            "Actual Rows": 9,
            "Actual Loops": 1,
            "Actual Total Time": 0.2,
        },
        execution_time=0.3,
    )

    assert result.primary.category == IssueCategory.NO_CLEAR_ISSUE
    assert result.primary.severity == Severity.LOW

