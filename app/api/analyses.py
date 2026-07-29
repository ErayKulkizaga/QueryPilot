import logging
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.analysis.plan_parser import PlanParseError, parse_explain
from app.analysis.rule_engine import analyze_plan, build_fallback_report
from app.analysis.sql_validator import SQLValidationError, validate_read_only_sql
from app.analysis_store import AnalysisNotFoundError, get_analysis_store
from app.config import Settings, get_settings
from app.database.explain_runner import ExplainRunner, ExplainRunnerError
from app.reporting import get_reporting_service
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    EnrichmentResponse,
    IssueCategory,
)

router = APIRouter(prefix="/api/v1/analyses", tags=["analyses"])
logger = logging.getLogger(__name__)

SCENARIOS = {
    "missing_customer_email_index": (
        "SELECT id, email, full_name FROM customers "
        "WHERE email = 'demo@example.com'"
    ),
    "customer_order_history": (
        "SELECT c.email, o.created_at, o.total_amount "
        "FROM customers c JOIN orders o ON o.customer_id = c.id "
        "WHERE c.id BETWEEN 100 AND 120 ORDER BY o.created_at DESC"
    ),
    "recent_support_events": (
        "SELECT event_type, count(*) FROM support_events "
        "WHERE created_at >= now() - interval '7 days' GROUP BY event_type"
    ),
}


@router.post("", response_model=AnalysisResponse)
def create_analysis(
    request: AnalysisRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisResponse:
    started = perf_counter()

    if request.scenario_id:
        sql = SCENARIOS.get(request.scenario_id)
        if sql is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown scenario_id: {request.scenario_id}",
            )
    else:
        sql = request.sql or ""

    try:
        normalized_sql = validate_read_only_sql(sql)
    except SQLValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    try:
        raw_plan = ExplainRunner(
            dsn=settings.database_url,
            statement_timeout_ms=settings.statement_timeout_ms,
        ).run(normalized_sql)
        normalized_plan = parse_explain(raw_plan)
    except (ExplainRunnerError, PlanParseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The local PostgreSQL plan analyzer is unavailable.",
        ) from exc

    analysis = analyze_plan(normalized_plan)
    report = build_fallback_report(analysis)
    analysis_id = get_analysis_store(settings.analysis_ttl_seconds).put(
        analysis,
        normalized_plan=normalized_plan,
        normalized_sql=normalized_sql,
    )
    latency_ms = round((perf_counter() - started) * 1000)

    return AnalysisResponse(
        **report.model_dump(),
        analysis_id=analysis_id,
        latency_ms=latency_ms,
        report_source="deterministic",
        enrichment_available=(
            analysis.primary.category != IssueCategory.NO_CLEAR_ISSUE
        ),
        raw_plan=raw_plan,
    )


@router.post("/{analysis_id}/enrichment", response_model=EnrichmentResponse)
def enrich_analysis(
    analysis_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnrichmentResponse:
    started = perf_counter()
    try:
        analysis = get_analysis_store(settings.analysis_ttl_seconds).get(analysis_id)
    except AnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis ID was not found or has expired.",
        ) from exc

    try:
        generated = get_reporting_service(settings).generate(analysis)
        report = generated.report
        report_source = generated.source
        repair_attempted = generated.repair_attempted
        generation_latency_ms = generated.generation_latency_ms
    except Exception:
        logger.exception("Grounded report generation failed; using deterministic fallback.")
        report = build_fallback_report(analysis)
        report_source = "deterministic_fallback"
        repair_attempted = False
        generation_latency_ms = 0

    return EnrichmentResponse(
        **report.model_dump(),
        analysis_id=analysis_id,
        latency_ms=round((perf_counter() - started) * 1000),
        report_source=report_source,
        repair_attempted=repair_attempted,
        generation_latency_ms=generation_latency_ms,
    )
