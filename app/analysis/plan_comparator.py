from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Literal

from app.analysis.plan_parser import NormalizedPlan

NodeChangeType = Literal["added", "removed", "node_type_changed", "index_changed"]
INDEX_ACCESS_TYPES = {"Index Scan", "Index Only Scan", "Bitmap Heap Scan"}


@dataclass(frozen=True, slots=True)
class PlanNodeSnapshot:
    path: str
    node_type: str
    relation_name: str | None
    index_name: str | None
    total_cost: float
    actual_total_time_ms: float
    actual_rows: float
    actual_loops: float


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    planning_time_ms: float
    execution_time_ms: float
    nodes: tuple[PlanNodeSnapshot, ...]

    @property
    def root_total_cost(self) -> float:
        return self.nodes[0].total_cost


@dataclass(frozen=True, slots=True)
class PlanNodeChange:
    path: str
    change_type: NodeChangeType
    before_node_type: str | None
    after_node_type: str | None
    before_index_name: str | None = None
    after_index_name: str | None = None


@dataclass(frozen=True, slots=True)
class PlanComparison:
    execution_time_delta_ms: float
    execution_time_change_percent: float | None
    root_cost_delta: float
    root_cost_change_percent: float | None
    node_count_delta: int
    node_changes: tuple[PlanNodeChange, ...]
    regression_detected: bool
    regression_reasons: tuple[str, ...]


def query_fingerprint(normalized_sql: str) -> str:
    return sha256(normalized_sql.encode("utf-8")).hexdigest()


def snapshot_plan(plan: NormalizedPlan) -> PlanSnapshot:
    return PlanSnapshot(
        planning_time_ms=plan.planning_time_ms,
        execution_time_ms=plan.execution_time_ms,
        nodes=tuple(
            PlanNodeSnapshot(
                path=node.path,
                node_type=node.node_type,
                relation_name=node.relation_name,
                index_name=node.index_name,
                total_cost=node.total_cost,
                actual_total_time_ms=node.actual_total_time_ms,
                actual_rows=node.actual_rows,
                actual_loops=node.actual_loops,
            )
            for node in plan.nodes
        ),
    )


def snapshot_to_dict(snapshot: PlanSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


def snapshot_from_dict(payload: dict[str, Any]) -> PlanSnapshot:
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, (list, tuple)) or not raw_nodes:
        raise ValueError("Stored baseline plan must contain at least one node.")
    return PlanSnapshot(
        planning_time_ms=float(payload["planning_time_ms"]),
        execution_time_ms=float(payload["execution_time_ms"]),
        nodes=tuple(PlanNodeSnapshot(**node) for node in raw_nodes),
    )


def _percent_change(before: float, after: float) -> float | None:
    if before <= 0:
        return None
    return ((after - before) / before) * 100


def _node_changes(
    baseline: PlanSnapshot,
    current: PlanSnapshot,
) -> tuple[PlanNodeChange, ...]:
    before_by_path = {node.path: node for node in baseline.nodes}
    after_by_path = {node.path: node for node in current.nodes}
    changes: list[PlanNodeChange] = []

    for path in sorted(before_by_path.keys() | after_by_path.keys()):
        before = before_by_path.get(path)
        after = after_by_path.get(path)
        if before is None and after is not None:
            changes.append(
                PlanNodeChange(
                    path=path,
                    change_type="added",
                    before_node_type=None,
                    after_node_type=after.node_type,
                    after_index_name=after.index_name,
                )
            )
        elif before is not None and after is None:
            changes.append(
                PlanNodeChange(
                    path=path,
                    change_type="removed",
                    before_node_type=before.node_type,
                    after_node_type=None,
                    before_index_name=before.index_name,
                )
            )
        elif before is not None and after is not None:
            if before.node_type != after.node_type:
                changes.append(
                    PlanNodeChange(
                        path=path,
                        change_type="node_type_changed",
                        before_node_type=before.node_type,
                        after_node_type=after.node_type,
                        before_index_name=before.index_name,
                        after_index_name=after.index_name,
                    )
                )
            elif before.index_name != after.index_name:
                changes.append(
                    PlanNodeChange(
                        path=path,
                        change_type="index_changed",
                        before_node_type=before.node_type,
                        after_node_type=after.node_type,
                        before_index_name=before.index_name,
                        after_index_name=after.index_name,
                    )
                )
    return tuple(changes)


def _access_path_regressions(
    baseline: PlanSnapshot,
    current: PlanSnapshot,
) -> list[str]:
    baseline_access: dict[str, set[str]] = {}
    current_access: dict[str, set[str]] = {}
    for node in baseline.nodes:
        if node.relation_name:
            baseline_access.setdefault(node.relation_name, set()).add(node.node_type)
    for node in current.nodes:
        if node.relation_name:
            current_access.setdefault(node.relation_name, set()).add(node.node_type)

    reasons: list[str] = []
    for relation in sorted(baseline_access.keys() & current_access.keys()):
        before_types = baseline_access[relation]
        after_types = current_access[relation]
        if before_types & INDEX_ACCESS_TYPES and "Seq Scan" in after_types:
            reasons.append(
                f"Access path for {relation} changed from index-backed access "
                "to a sequential scan."
            )
    return reasons


def compare_plan_snapshots(
    baseline: PlanSnapshot,
    current: PlanSnapshot,
    *,
    execution_ratio_threshold: float = 1.5,
    execution_delta_threshold_ms: float = 1.0,
    cost_ratio_threshold: float = 1.25,
) -> PlanComparison:
    execution_delta = current.execution_time_ms - baseline.execution_time_ms
    execution_percent = _percent_change(
        baseline.execution_time_ms,
        current.execution_time_ms,
    )
    cost_delta = current.root_total_cost - baseline.root_total_cost
    cost_percent = _percent_change(
        baseline.root_total_cost,
        current.root_total_cost,
    )
    reasons: list[str] = []

    if (
        baseline.execution_time_ms > 0
        and current.execution_time_ms
        >= baseline.execution_time_ms * execution_ratio_threshold
        and execution_delta >= execution_delta_threshold_ms
    ):
        reasons.append(
            "Execution time increased from "
            f"{baseline.execution_time_ms:.3f} ms to "
            f"{current.execution_time_ms:.3f} ms "
            f"(+{execution_delta:.3f} ms)."
        )

    if (
        baseline.root_total_cost > 0
        and current.root_total_cost
        >= baseline.root_total_cost * cost_ratio_threshold
    ):
        reasons.append(
            "Root plan cost increased from "
            f"{baseline.root_total_cost:.3f} to {current.root_total_cost:.3f}."
        )

    reasons.extend(_access_path_regressions(baseline, current))
    changes = _node_changes(baseline, current)
    return PlanComparison(
        execution_time_delta_ms=execution_delta,
        execution_time_change_percent=execution_percent,
        root_cost_delta=cost_delta,
        root_cost_change_percent=cost_percent,
        node_count_delta=len(current.nodes) - len(baseline.nodes),
        node_changes=changes,
        regression_detected=bool(reasons),
        regression_reasons=tuple(reasons),
    )
