import json
from dataclasses import dataclass
from typing import Any


class PlanParseError(ValueError):
    """Raised when an EXPLAIN payload does not contain a valid plan tree."""


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanParseError(f"Expected a numeric plan value, got {value!r}.")
    return float(value)


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


@dataclass(frozen=True, slots=True)
class PlanNode:
    path: str
    parent_path: str | None
    depth: int
    node_type: str
    relation_name: str | None
    alias: str | None
    index_name: str | None
    parent_relationship: str | None
    plan_rows: float
    actual_rows: float
    actual_loops: float
    total_cost: float
    actual_total_time_ms: float
    rows_removed_by_filter: float
    filter_condition: str | None
    index_condition: str | None
    sort_method: str | None
    sort_space_type: str | None
    sort_space_used_kb: float
    temp_read_blocks: float
    temp_written_blocks: float
    shared_hit_blocks: float
    shared_read_blocks: float

    @property
    def cardinality_ratio(self) -> float:
        return max(self.actual_rows, 1.0) / max(self.plan_rows, 1.0)

    @property
    def rows_examined(self) -> float:
        return self.actual_rows + self.rows_removed_by_filter


@dataclass(frozen=True, slots=True)
class NormalizedPlan:
    nodes: tuple[PlanNode, ...]
    planning_time_ms: float
    execution_time_ms: float

    @property
    def root(self) -> PlanNode:
        return self.nodes[0]


def _unwrap_payload(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PlanParseError("EXPLAIN payload is not valid JSON.") from exc

    if isinstance(payload, list):
        if len(payload) != 1 or not isinstance(payload[0], dict):
            raise PlanParseError("EXPLAIN JSON must contain one top-level result.")
        summary = payload[0]
    elif isinstance(payload, dict):
        summary = payload
    else:
        raise PlanParseError("EXPLAIN payload must be a JSON object or one-item list.")

    root = summary.get("Plan", summary)
    if not isinstance(root, dict) or not isinstance(root.get("Node Type"), str):
        raise PlanParseError("EXPLAIN payload does not contain a Plan node.")
    return summary, root


def parse_explain(payload: Any) -> NormalizedPlan:
    summary, root = _unwrap_payload(payload)
    nodes: list[PlanNode] = []

    def visit(
        raw: dict[str, Any],
        *,
        path: str,
        parent_path: str | None,
        depth: int,
    ) -> None:
        node_type = raw.get("Node Type")
        if not isinstance(node_type, str) or not node_type:
            raise PlanParseError(f"Plan node at {path} is missing Node Type.")

        nodes.append(
            PlanNode(
                path=path,
                parent_path=parent_path,
                depth=depth,
                node_type=node_type,
                relation_name=_optional_text(raw.get("Relation Name")),
                alias=_optional_text(raw.get("Alias")),
                index_name=_optional_text(raw.get("Index Name")),
                parent_relationship=_optional_text(raw.get("Parent Relationship")),
                plan_rows=_number(raw.get("Plan Rows")),
                actual_rows=_number(raw.get("Actual Rows")),
                actual_loops=_number(raw.get("Actual Loops")),
                total_cost=_number(raw.get("Total Cost")),
                actual_total_time_ms=_number(raw.get("Actual Total Time")),
                rows_removed_by_filter=_number(raw.get("Rows Removed by Filter")),
                filter_condition=_optional_text(raw.get("Filter")),
                index_condition=_optional_text(raw.get("Index Cond")),
                sort_method=_optional_text(raw.get("Sort Method")),
                sort_space_type=_optional_text(raw.get("Sort Space Type")),
                sort_space_used_kb=_number(raw.get("Sort Space Used")),
                temp_read_blocks=_number(raw.get("Temp Read Blocks")),
                temp_written_blocks=_number(raw.get("Temp Written Blocks")),
                shared_hit_blocks=_number(raw.get("Shared Hit Blocks")),
                shared_read_blocks=_number(raw.get("Shared Read Blocks")),
            )
        )

        children = raw.get("Plans", [])
        if not isinstance(children, list):
            raise PlanParseError(f"Plans at {path} must be a list.")
        for index, child in enumerate(children):
            if not isinstance(child, dict):
                raise PlanParseError(f"Child plan at {path}/{index} must be an object.")
            visit(
                child,
                path=f"{path}/{index}",
                parent_path=path,
                depth=depth + 1,
            )

    visit(root, path="0", parent_path=None, depth=0)
    return NormalizedPlan(
        nodes=tuple(nodes),
        planning_time_ms=_number(summary.get("Planning Time")),
        execution_time_ms=_number(summary.get("Execution Time")),
    )

