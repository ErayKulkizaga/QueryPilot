from app.analysis.plan_comparator import (
    compare_plan_snapshots,
    snapshot_from_dict,
    snapshot_plan,
    snapshot_to_dict,
)
from app.analysis.plan_parser import parse_explain


def _plan(
    *,
    node_type: str,
    execution_time_ms: float,
    total_cost: float,
    index_name: str | None = None,
):
    plan = {
        "Node Type": node_type,
        "Relation Name": "customers",
        "Plan Rows": 1,
        "Actual Rows": 1,
        "Actual Loops": 1,
        "Total Cost": total_cost,
        "Actual Total Time": execution_time_ms,
    }
    if index_name:
        plan["Index Name"] = index_name
    return parse_explain(
        [
            {
                "Plan": plan,
                "Planning Time": 0.2,
                "Execution Time": execution_time_ms,
            }
        ]
    )


def test_snapshot_round_trip_preserves_plan_metrics() -> None:
    snapshot = snapshot_plan(
        _plan(
            node_type="Index Scan",
            execution_time_ms=2.0,
            total_cost=10.0,
            index_name="customers_pkey",
        )
    )

    restored = snapshot_from_dict(snapshot_to_dict(snapshot))

    assert restored == snapshot


def test_comparison_detects_measured_and_access_path_regression() -> None:
    baseline = snapshot_plan(
        _plan(
            node_type="Index Scan",
            execution_time_ms=2.0,
            total_cost=10.0,
            index_name="customers_pkey",
        )
    )
    current = snapshot_plan(
        _plan(
            node_type="Seq Scan",
            execution_time_ms=4.0,
            total_cost=15.0,
        )
    )

    comparison = compare_plan_snapshots(baseline, current)

    assert comparison.regression_detected is True
    assert comparison.execution_time_delta_ms == 2.0
    assert comparison.execution_time_change_percent == 100.0
    assert comparison.root_cost_delta == 5.0
    assert len(comparison.regression_reasons) == 3
    assert comparison.node_changes[0].change_type == "node_type_changed"


def test_comparison_ignores_small_timing_noise() -> None:
    baseline = snapshot_plan(
        _plan(
            node_type="Index Scan",
            execution_time_ms=2.0,
            total_cost=10.0,
            index_name="customers_pkey",
        )
    )
    current = snapshot_plan(
        _plan(
            node_type="Index Scan",
            execution_time_ms=2.4,
            total_cost=11.0,
            index_name="customers_pkey",
        )
    )

    comparison = compare_plan_snapshots(baseline, current)

    assert comparison.regression_detected is False
    assert comparison.regression_reasons == ()
