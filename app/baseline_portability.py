from __future__ import annotations

from app.analysis.plan_comparator import PlanSnapshot, snapshot_from_dict
from app.baseline_store import PlanBaseline
from app.schemas import PlanBaselineExport, PortablePlan


def export_baseline(baseline: PlanBaseline) -> PlanBaselineExport:
    return PlanBaselineExport(
        name=baseline.name,
        query_fingerprint=baseline.query_fingerprint,
        normalized_sql=baseline.normalized_sql,
        measurement_group=baseline.measurement_group,
        sample_count=baseline.sample_count,
        source_created_at=baseline.created_at,
        plan=PortablePlan.model_validate(
            {
                "planning_time_ms": baseline.plan.planning_time_ms,
                "execution_time_ms": baseline.plan.execution_time_ms,
                "nodes": [
                    {
                        "path": node.path,
                        "node_type": node.node_type,
                        "relation_name": node.relation_name,
                        "index_name": node.index_name,
                        "total_cost": node.total_cost,
                        "actual_total_time_ms": node.actual_total_time_ms,
                        "actual_rows": node.actual_rows,
                        "actual_loops": node.actual_loops,
                    }
                    for node in baseline.plan.nodes
                ],
            }
        ),
    )


def imported_plan(payload: PlanBaselineExport) -> PlanSnapshot:
    return snapshot_from_dict(payload.plan.model_dump())


def render_baseline_markdown(baseline: PlanBaseline) -> str:
    node_rows = "\n".join(
        "| "
        + " | ".join(
            (
                node.path.replace("|", "\\|"),
                node.node_type.replace("|", "\\|"),
                (node.relation_name or "-").replace("|", "\\|"),
                (node.index_name or "-").replace("|", "\\|"),
                f"{node.total_cost:.3f}",
                f"{node.actual_total_time_ms:.3f}",
            )
        )
        + " |"
        for node in baseline.plan.nodes
    )
    indented_sql = "\n".join(
        f"    {line}" for line in baseline.normalized_sql.splitlines()
    )
    return (
        f"# QueryPilot plan baseline: {baseline.name}\n\n"
        f"- Baseline ID: `{baseline.baseline_id}`\n"
        f"- Created: `{baseline.created_at.isoformat()}`\n"
        f"- Measurement group: `{baseline.measurement_group}`\n"
        f"- Samples: `{baseline.sample_count}`\n"
        f"- Execution time: `{baseline.plan.execution_time_ms:.3f} ms`\n"
        f"- Root cost: `{baseline.plan.root_total_cost:.3f}`\n"
        f"- Query fingerprint: `{baseline.query_fingerprint}`\n\n"
        "## Normalized SQL\n\n"
        f"{indented_sql}\n\n"
        "## Plan nodes\n\n"
        "| Path | Node type | Relation | Index | Cost | Actual time (ms) |\n"
        "| --- | --- | --- | --- | ---: | ---: |\n"
        f"{node_rows}\n\n"
        "> Evidence report only. QueryPilot did not execute a schema change or "
        "generate an optimization from this export.\n"
    )
