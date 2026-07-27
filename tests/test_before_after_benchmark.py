from scripts.before_after_benchmark import summarize_plan


def test_summarize_plan_collects_index_evidence() -> None:
    payload = [
        {
            "Plan": {
                "Node Type": "Index Scan",
                "Index Name": "idx_customers_email",
                "Shared Hit Blocks": 3,
                "Shared Read Blocks": 1,
                "Plans": [],
            },
            "Planning Time": 0.1,
            "Execution Time": 0.2,
        }
    ]

    summary = summarize_plan(payload)

    assert summary["root_node"] == "Index Scan"
    assert summary["index_names"] == ["idx_customers_email"]
    assert summary["execution_time_ms"] == 0.2
    assert summary["shared_hit_blocks"] == 3
