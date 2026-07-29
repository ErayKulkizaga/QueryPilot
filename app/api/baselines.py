from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.analysis.plan_comparator import (
    PlanAggregationError,
    PlanSnapshot,
    aggregate_plan_snapshots,
    compare_plan_snapshots,
    query_fingerprint,
    snapshot_plan,
)
from app.analysis_store import (
    AnalysisNotFoundError,
    StoredAnalysis,
    get_analysis_store,
)
from app.baseline_store import (
    BaselineNotFoundError,
    BaselineStoreError,
    PlanBaseline,
    get_baseline_store,
)
from app.config import Settings, get_settings
from app.schemas import (
    BaselineComparisonRequest,
    BaselineCreateRequest,
    PlanBaselineListResponse,
    PlanBaselineResponse,
    PlanComparisonResponse,
    PlanNodeChangeResponse,
)

router = APIRouter(prefix="/api/v1/baselines", tags=["baselines"])


def _baseline_response(baseline: PlanBaseline) -> PlanBaselineResponse:
    return PlanBaselineResponse(
        baseline_id=baseline.baseline_id,
        name=baseline.name,
        query_fingerprint=baseline.query_fingerprint,
        normalized_sql=baseline.normalized_sql,
        created_at=baseline.created_at,
        execution_time_ms=baseline.plan.execution_time_ms,
        root_total_cost=baseline.plan.root_total_cost,
        node_count=len(baseline.plan.nodes),
        sample_count=baseline.sample_count,
    )


def _get_analysis_samples(
    analysis_ids: list[str],
    settings: Settings,
) -> tuple[str, str, PlanSnapshot]:
    store = get_analysis_store(settings.analysis_ttl_seconds)
    try:
        samples: list[StoredAnalysis] = [
            store.get_snapshot(analysis_id) for analysis_id in analysis_ids
        ]
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more analysis IDs were not found or have expired.",
        ) from exc

    normalized_sql = samples[0].normalized_sql
    fingerprint = query_fingerprint(normalized_sql)
    if any(
        query_fingerprint(sample.normalized_sql) != fingerprint
        for sample in samples[1:]
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="All plan samples must use the same normalized SQL.",
        )
    try:
        plan = aggregate_plan_snapshots(
            [snapshot_plan(sample.normalized_plan) for sample in samples]
        )
    except PlanAggregationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return normalized_sql, fingerprint, plan


@router.post(
    "",
    response_model=PlanBaselineResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_baseline(
    request: BaselineCreateRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanBaselineResponse:
    normalized_sql, fingerprint, plan = _get_analysis_samples(
        request.analysis_ids,
        settings,
    )

    try:
        baseline = get_baseline_store(
            settings.baseline_database_path,
            settings.baseline_max_items,
        ).create(
            name=request.name,
            query_fingerprint=fingerprint,
            normalized_sql=normalized_sql,
            plan=plan,
            sample_count=len(request.analysis_ids),
        )
    except BaselineStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local plan baseline store is unavailable.",
        ) from exc
    return _baseline_response(baseline)


@router.get("", response_model=PlanBaselineListResponse)
def list_baselines(
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PlanBaselineListResponse:
    try:
        baselines = get_baseline_store(
            settings.baseline_database_path,
            settings.baseline_max_items,
        ).list(limit=limit)
    except BaselineStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local plan baseline store is unavailable.",
        ) from exc
    return PlanBaselineListResponse(
        baselines=[_baseline_response(baseline) for baseline in baselines]
    )


@router.post(
    "/{baseline_id}/comparisons",
    response_model=PlanComparisonResponse,
)
def compare_baseline(
    baseline_id: str,
    request: BaselineComparisonRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanComparisonResponse:
    _, current_fingerprint, current_plan = _get_analysis_samples(
        request.analysis_ids,
        settings,
    )

    try:
        baseline = get_baseline_store(
            settings.baseline_database_path,
            settings.baseline_max_items,
        ).get(baseline_id)
    except BaselineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan baseline was not found.",
        ) from exc
    except BaselineStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local plan baseline store is unavailable.",
        ) from exc

    if current_fingerprint != baseline.query_fingerprint:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The current analysis does not match the baseline query. "
                "Compare plans only for the same normalized SQL."
            ),
        )

    comparison = compare_plan_snapshots(
        baseline.plan,
        current_plan,
        execution_ratio_threshold=settings.regression_execution_ratio,
        execution_delta_threshold_ms=settings.regression_execution_delta_ms,
        cost_ratio_threshold=settings.regression_cost_ratio,
    )
    return PlanComparisonResponse(
        baseline_id=baseline.baseline_id,
        current_analysis_ids=request.analysis_ids,
        query_fingerprint=current_fingerprint,
        baseline_sample_count=baseline.sample_count,
        current_sample_count=len(request.analysis_ids),
        baseline_execution_time_ms=baseline.plan.execution_time_ms,
        current_execution_time_ms=current_plan.execution_time_ms,
        execution_time_delta_ms=comparison.execution_time_delta_ms,
        execution_time_change_percent=comparison.execution_time_change_percent,
        baseline_root_cost=baseline.plan.root_total_cost,
        current_root_cost=current_plan.root_total_cost,
        root_cost_delta=comparison.root_cost_delta,
        root_cost_change_percent=comparison.root_cost_change_percent,
        baseline_node_count=len(baseline.plan.nodes),
        current_node_count=len(current_plan.nodes),
        node_count_delta=comparison.node_count_delta,
        node_changes=[
            PlanNodeChangeResponse(**asdict(change))
            for change in comparison.node_changes
        ],
        regression_detected=comparison.regression_detected,
        regression_reasons=list(comparison.regression_reasons),
        recommendations_generated=False,
    )


@router.delete(
    "/{baseline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_baseline(
    baseline_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    try:
        get_baseline_store(
            settings.baseline_database_path,
            settings.baseline_max_items,
        ).delete(baseline_id)
    except BaselineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan baseline was not found.",
        ) from exc
    except BaselineStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local plan baseline store is unavailable.",
        ) from exc
