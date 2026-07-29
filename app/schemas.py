from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IssueCategory(StrEnum):
    POTENTIAL_MISSING_INDEX = "potential_missing_index"
    EXPENSIVE_NESTED_LOOP = "expensive_nested_loop"
    DISK_BASED_SORT = "disk_based_sort"
    CARDINALITY_MISESTIMATION = "cardinality_misestimation"
    NO_CLEAR_ISSUE = "no_clear_issue"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Citation(StrictModel):
    document_id: str
    title: str
    section: str


class AnalysisRequest(StrictModel):
    scenario_id: str | None = None
    sql: str | None = Field(default=None, min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def require_exactly_one_input(self) -> "AnalysisRequest":
        supplied = int(self.scenario_id is not None) + int(self.sql is not None)
        if supplied != 1:
            raise ValueError("Provide exactly one of scenario_id or sql.")
        return self


class AnalysisReport(StrictModel):
    issue_category: IssueCategory
    severity: Severity
    summary: str
    plan_evidence: list[str]
    recommendation: str
    recommendation_sql: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    insufficient_context: bool


class GeneratedExplanation(StrictModel):
    summary_sentence_id: str = Field(min_length=1, max_length=80)
    recommendation_sentence_id: str = Field(min_length=1, max_length=80)


class AnalysisResponse(AnalysisReport):
    analysis_id: str
    latency_ms: int = Field(ge=0)
    report_source: Literal["deterministic"]
    enrichment_available: bool
    raw_plan: dict[str, Any] | list[Any]


class EnrichmentResponse(AnalysisReport):
    analysis_id: str
    latency_ms: int = Field(ge=0)
    report_source: Literal["deterministic_fallback", "foundry_local"]
    repair_attempted: bool
    generation_latency_ms: int = Field(ge=0)


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: Literal["querypilot-local"]
    version: str


class WorkloadQuery(StrictModel):
    rank: int = Field(ge=1)
    query_id: str
    normalized_sql: str
    calls: int = Field(ge=0)
    total_exec_time_ms: float = Field(ge=0)
    mean_exec_time_ms: float = Field(ge=0)
    result_rows: int = Field(ge=0)
    shared_blocks_read: int = Field(ge=0)
    temp_blocks_written: int = Field(ge=0)
    ranking_reason: str
    requires_representative_sql: bool


class WorkloadQueryListResponse(StrictModel):
    captured_at: datetime
    ranking_basis: Literal["total_exec_time_ms"]
    recommendations_generated: Literal[False]
    queries: list[WorkloadQuery]


class BaselineCreateRequest(StrictModel):
    analysis_ids: list[str] = Field(min_length=1, max_length=9)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("analysis_ids")
    @classmethod
    def validate_analysis_ids(cls, value: list[str]) -> list[str]:
        if any(len(analysis_id) != 32 for analysis_id in value):
            raise ValueError("Every analysis ID must be 32 characters.")
        if len(set(value)) != len(value):
            raise ValueError("Analysis IDs must be unique.")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Baseline name cannot be blank.")
        return stripped


class PlanBaselineResponse(StrictModel):
    baseline_id: str
    name: str
    query_fingerprint: str
    normalized_sql: str
    created_at: datetime
    execution_time_ms: float = Field(ge=0)
    root_total_cost: float = Field(ge=0)
    node_count: int = Field(ge=1)
    sample_count: int = Field(ge=1, le=9)


class PlanBaselineListResponse(StrictModel):
    baselines: list[PlanBaselineResponse]


class BaselineComparisonRequest(StrictModel):
    analysis_ids: list[str] = Field(min_length=1, max_length=9)

    @field_validator("analysis_ids")
    @classmethod
    def validate_analysis_ids(cls, value: list[str]) -> list[str]:
        if any(len(analysis_id) != 32 for analysis_id in value):
            raise ValueError("Every analysis ID must be 32 characters.")
        if len(set(value)) != len(value):
            raise ValueError("Analysis IDs must be unique.")
        return value


class PlanNodeChangeResponse(StrictModel):
    path: str
    change_type: Literal[
        "added",
        "removed",
        "node_type_changed",
        "index_changed",
    ]
    before_node_type: str | None
    after_node_type: str | None
    before_index_name: str | None = None
    after_index_name: str | None = None


class PlanComparisonResponse(StrictModel):
    baseline_id: str
    current_analysis_ids: list[str]
    query_fingerprint: str
    baseline_sample_count: int = Field(ge=1, le=9)
    current_sample_count: int = Field(ge=1, le=9)
    baseline_execution_time_ms: float = Field(ge=0)
    current_execution_time_ms: float = Field(ge=0)
    execution_time_delta_ms: float
    execution_time_change_percent: float | None
    baseline_root_cost: float = Field(ge=0)
    current_root_cost: float = Field(ge=0)
    root_cost_delta: float
    root_cost_change_percent: float | None
    baseline_node_count: int = Field(ge=1)
    current_node_count: int = Field(ge=1)
    node_count_delta: int
    node_changes: list[PlanNodeChangeResponse]
    regression_detected: bool
    regression_reasons: list[str]
    recommendations_generated: Literal[False]
