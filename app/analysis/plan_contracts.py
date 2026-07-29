from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.analysis.plan_parser import NormalizedPlan, PlanNode, parse_explain
from app.schemas import IssueCategory


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanNodeExpectation(ContractModel):
    node_type: str = Field(min_length=1)
    relation_name: str | None = None
    index_name: str | None = None

    def matches(self, node: PlanNode) -> bool:
        return (
            node.node_type == self.node_type
            and (
                self.relation_name is None
                or node.relation_name == self.relation_name
            )
            and (self.index_name is None or node.index_name == self.index_name)
        )

    def describe(self) -> str:
        fields = [self.node_type]
        if self.relation_name:
            fields.append(f"relation={self.relation_name}")
        if self.index_name:
            fields.append(f"index={self.index_name}")
        return ", ".join(fields)


class NamedPlanContract(ContractModel):
    name: str = Field(min_length=1, max_length=100)
    release: str = Field(min_length=1, max_length=40)
    sql: str = Field(min_length=1, max_length=20_000)
    expected_issue_category: IssueCategory
    expected_insufficient_context: bool
    required_nodes: list[PlanNodeExpectation] = Field(min_length=1)
    forbidden_nodes: list[PlanNodeExpectation] = Field(default_factory=list)


class PlanContractSet(ContractModel):
    schema_version: int = Field(ge=1, le=1)
    contracts: list[NamedPlanContract] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class PlanContractEvaluation:
    contract_name: str
    passed: bool
    errors: tuple[str, ...]
    observed_issue_category: str
    observed_node_types: tuple[str, ...]


def _matching_nodes(
    expectation: PlanNodeExpectation,
    plan: NormalizedPlan,
) -> tuple[PlanNode, ...]:
    return tuple(node for node in plan.nodes if expectation.matches(node))


def evaluate_plan_contract(
    contract: NamedPlanContract,
    *,
    issue_category: str,
    insufficient_context: bool,
    raw_plan: dict[str, Any] | list[Any],
) -> PlanContractEvaluation:
    plan = parse_explain(raw_plan)
    errors: list[str] = []

    if issue_category != contract.expected_issue_category:
        errors.append(
            "Expected issue category "
            f"{contract.expected_issue_category}, observed {issue_category}."
        )
    if insufficient_context != contract.expected_insufficient_context:
        errors.append(
            "Expected insufficient_context="
            f"{contract.expected_insufficient_context}, observed "
            f"{insufficient_context}."
        )

    for expectation in contract.required_nodes:
        if not _matching_nodes(expectation, plan):
            errors.append(f"Required plan node missing: {expectation.describe()}.")
    for expectation in contract.forbidden_nodes:
        if _matching_nodes(expectation, plan):
            errors.append(f"Forbidden plan node present: {expectation.describe()}.")

    return PlanContractEvaluation(
        contract_name=contract.name,
        passed=not errors,
        errors=tuple(errors),
        observed_issue_category=issue_category,
        observed_node_types=tuple(node.node_type for node in plan.nodes),
    )
