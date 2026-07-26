import re
from dataclasses import dataclass

from app.analysis.plan_parser import NormalizedPlan, PlanNode
from app.schemas import AnalysisReport, IssueCategory, Severity


@dataclass(frozen=True, slots=True)
class Finding:
    category: IssueCategory
    severity: Severity
    confidence: float
    summary: str
    evidence: tuple[str, ...]
    recommendation: str
    recommendation_sql: str | None = None


@dataclass(frozen=True, slots=True)
class RuleAnalysis:
    primary: Finding
    findings: tuple[Finding, ...]


_SEVERITY_SCORE = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}
_CATEGORY_PRIORITY = {
    IssueCategory.POTENTIAL_MISSING_INDEX: 4,
    IssueCategory.DISK_BASED_SORT: 3,
    IssueCategory.EXPENSIVE_NESTED_LOOP: 2,
    IssueCategory.CARDINALITY_MISESTIMATION: 1,
    IssueCategory.NO_CLEAR_ISSUE: 0,
}
_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_FILTER_COLUMN = re.compile(r"\(?([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=|<|>|<=|>=)")


def _compact_number(value: float) -> str:
    return f"{value:,.0f}"


def _index_sql(node: PlanNode) -> str | None:
    relation = node.relation_name
    condition = node.filter_condition or ""
    match = _FILTER_COLUMN.search(condition)
    if (
        not relation
        or not match
        or not _IDENTIFIER.fullmatch(relation)
        or not _IDENTIFIER.fullmatch(match.group(1))
    ):
        return None
    column = match.group(1)
    return f"CREATE INDEX idx_{relation}_{column} ON {relation} ({column});"


def _missing_index_findings(plan: NormalizedPlan) -> list[Finding]:
    findings: list[Finding] = []
    for node in plan.nodes:
        if node.node_type != "Seq Scan" or not node.filter_condition:
            continue
        examined = node.rows_examined
        selectivity = node.actual_rows / max(examined, 1.0)
        strong_signal = node.rows_removed_by_filter >= 5_000
        selective_signal = examined >= 1_000 and selectivity <= 0.10
        if not (strong_signal or selective_signal):
            continue
        severity = Severity.HIGH if node.rows_removed_by_filter >= 10_000 else Severity.MEDIUM
        findings.append(
            Finding(
                category=IssueCategory.POTENTIAL_MISSING_INDEX,
                severity=severity,
                confidence=min(0.98, 0.72 + (1.0 - selectivity) * 0.2),
                summary=(
                    f"A sequential scan on {node.relation_name or node.alias or 'a relation'} "
                    "discarded most examined rows."
                ),
                evidence=(
                    f"Seq Scan on {node.relation_name or node.alias or 'unknown relation'}",
                    f"Rows Removed by Filter: {_compact_number(node.rows_removed_by_filter)}",
                    f"Filter selectivity: {selectivity:.2%}",
                ),
                recommendation=(
                    "Review an index whose leading columns match the selective filter. "
                    "Validate write cost and compare the plan before applying it."
                ),
                recommendation_sql=_index_sql(node),
            )
        )
    return findings


def _nested_loop_findings(plan: NormalizedPlan) -> list[Finding]:
    findings: list[Finding] = []
    for node in plan.nodes:
        if node.node_type != "Nested Loop":
            continue
        children = [candidate for candidate in plan.nodes if candidate.parent_path == node.path]
        if len(children) < 2:
            continue
        inner = children[1]
        if inner.actual_loops < 100:
            continue
        expensive = node.actual_total_time_ms >= 5 or inner.actual_loops >= 1_000
        if not expensive:
            continue
        severity = Severity.HIGH if inner.actual_loops >= 5_000 else Severity.MEDIUM
        findings.append(
            Finding(
                category=IssueCategory.EXPENSIVE_NESTED_LOOP,
                severity=severity,
                confidence=min(0.96, 0.70 + inner.actual_loops / 50_000),
                summary="A nested loop repeatedly executes its inner plan.",
                evidence=(
                    f"Nested Loop total time: {node.actual_total_time_ms:.2f} ms",
                    f"Inner node: {inner.node_type}",
                    f"Inner loops: {_compact_number(inner.actual_loops)}",
                ),
                recommendation=(
                    "Check join selectivity, indexes on join keys, and current statistics. "
                    "Compare alternative plans rather than forcing a join type."
                ),
            )
        )
    return findings


def _disk_sort_findings(plan: NormalizedPlan) -> list[Finding]:
    findings: list[Finding] = []
    for node in plan.nodes:
        method = (node.sort_method or "").lower()
        space_type = (node.sort_space_type or "").lower()
        temp_blocks = node.temp_read_blocks + node.temp_written_blocks
        uses_disk = "external" in method or space_type == "disk" or temp_blocks > 0
        if node.node_type != "Sort" or not uses_disk:
            continue
        severity = (
            Severity.HIGH
            if node.sort_space_used_kb >= 100_000 or temp_blocks >= 10_000
            else Severity.MEDIUM
        )
        findings.append(
            Finding(
                category=IssueCategory.DISK_BASED_SORT,
                severity=severity,
                confidence=0.96,
                summary="A sort spilled from memory to temporary disk storage.",
                evidence=(
                    f"Sort Method: {node.sort_method or 'unknown'}",
                    f"Sort Space Type: {node.sort_space_type or 'unknown'}",
                    f"Sort Space Used: {_compact_number(node.sort_space_used_kb)} kB",
                ),
                recommendation=(
                    "Reduce rows before sorting, review a supporting index, and only then "
                    "consider session-level work_mem tuning for this workload."
                ),
            )
        )
    return findings


def _cardinality_findings(plan: NormalizedPlan) -> list[Finding]:
    candidates = [
        node
        for node in plan.nodes
        if node.plan_rows > 0
        and (node.cardinality_ratio >= 10 or node.cardinality_ratio <= 0.10)
    ]
    if not candidates:
        return []
    node = max(
        candidates,
        key=lambda candidate: max(
            candidate.cardinality_ratio,
            1 / max(candidate.cardinality_ratio, 0.000001),
        ),
    )
    error_factor = max(node.cardinality_ratio, 1 / max(node.cardinality_ratio, 0.000001))
    severity = Severity.HIGH if error_factor >= 100 else Severity.MEDIUM
    return [
        Finding(
            category=IssueCategory.CARDINALITY_MISESTIMATION,
            severity=severity,
            confidence=min(0.97, 0.70 + error_factor / 1_000),
            summary="Planner row estimates differ materially from observed rows.",
            evidence=(
                f"Node: {node.node_type}",
                f"Plan Rows: {_compact_number(node.plan_rows)}",
                f"Actual Rows: {_compact_number(node.actual_rows)}",
                f"Estimation error: {error_factor:.1f}x",
            ),
            recommendation=(
                "Refresh statistics and inspect data correlation or skew. Consider higher "
                "statistics targets or extended statistics when the evidence supports it."
            ),
        )
    ]


def analyze_plan(plan: NormalizedPlan) -> RuleAnalysis:
    findings = (
        _missing_index_findings(plan)
        + _nested_loop_findings(plan)
        + _disk_sort_findings(plan)
        + _cardinality_findings(plan)
    )
    if not findings:
        no_issue = Finding(
            category=IssueCategory.NO_CLEAR_ISSUE,
            severity=Severity.LOW,
            confidence=0.80,
            summary="No configured rule found a sufficiently strong performance signal.",
            evidence=(
                f"Execution Time: {plan.execution_time_ms:.2f} ms",
                f"Plan nodes inspected: {len(plan.nodes)}",
            ),
            recommendation=(
                "Do not make a schema change from this plan alone. Capture representative "
                "workload evidence if the query is still considered slow."
            ),
        )
        return RuleAnalysis(primary=no_issue, findings=(no_issue,))

    ranked = sorted(
        findings,
        key=lambda finding: (
            _SEVERITY_SCORE[finding.severity],
            _CATEGORY_PRIORITY[finding.category],
            finding.confidence,
        ),
        reverse=True,
    )
    return RuleAnalysis(primary=ranked[0], findings=tuple(ranked))


def build_fallback_report(analysis: RuleAnalysis) -> AnalysisReport:
    finding = analysis.primary
    return AnalysisReport(
        issue_category=finding.category,
        severity=finding.severity,
        summary=finding.summary,
        plan_evidence=list(finding.evidence),
        recommendation=finding.recommendation,
        recommendation_sql=finding.recommendation_sql,
        citations=[],
        insufficient_context=finding.category == IssueCategory.NO_CLEAR_ISSUE,
    )
