import pytest

from app.analysis.plan_parser import PlanParseError, parse_explain


def test_recursively_normalizes_plan_tree() -> None:
    raw = [
        {
            "Plan": {
                "Node Type": "Nested Loop",
                "Plan Rows": 10,
                "Actual Rows": 12,
                "Actual Loops": 1,
                "Plans": [
                    {
                        "Node Type": "Seq Scan",
                        "Relation Name": "customers",
                        "Plan Rows": 5,
                        "Actual Rows": 5,
                        "Actual Loops": 1,
                    },
                    {
                        "Node Type": "Index Scan",
                        "Relation Name": "orders",
                        "Index Name": "orders_customer_id_idx",
                        "Plan Rows": 2,
                        "Actual Rows": 2,
                        "Actual Loops": 5,
                    },
                ],
            },
            "Planning Time": 0.4,
            "Execution Time": 3.2,
        }
    ]

    plan = parse_explain(raw)

    assert len(plan.nodes) == 3
    assert plan.root.node_type == "Nested Loop"
    assert plan.nodes[2].path == "0/1"
    assert plan.nodes[2].parent_path == "0"
    assert plan.execution_time_ms == pytest.approx(3.2)


def test_rejects_payload_without_plan_node() -> None:
    with pytest.raises(PlanParseError):
        parse_explain([{"Planning Time": 1.0}])

