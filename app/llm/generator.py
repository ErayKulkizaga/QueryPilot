import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol

from pydantic import ValidationError

from app.analysis.rule_engine import RuleAnalysis, build_fallback_report
from app.llm.prompts import (
    GENERATION_TOOLS,
    build_generation_messages,
    build_repair_messages,
)
from app.rag.retriever import RetrievedChunk
from app.schemas import (
    AnalysisReport,
    Citation,
    GeneratedExplanation,
    IssueCategory,
)

_PRIMARY_SOURCE_BY_CATEGORY = {
    IssueCategory.POTENTIAL_MISSING_INDEX: "pg-indexes-01",
    IssueCategory.EXPENSIVE_NESTED_LOOP: "pg-joins-01",
    IssueCategory.DISK_BASED_SORT: "pg-sorting-01",
    IssueCategory.CARDINALITY_MISESTIMATION: "pg-statistics-01",
}
_NUMBER_PATTERN = re.compile(r"(?<![\w.-])\d+(?:[.,]\d+)?%?")
_CODE_TOKEN_PATTERN = re.compile(r"`([^`]+)`")
_SQL_ACTION_PATTERN = re.compile(
    r"\b(?:ALTER|CREATE|DELETE|DROP|INSERT|MERGE|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)


class ChatCompleter(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, object]] | None = None,
    ) -> str: ...


@dataclass(frozen=True, slots=True)
class GenerationResult:
    report: AnalysisReport
    source: Literal["foundry_local", "deterministic_fallback"]
    repair_attempted: bool
    generation_latency_ms: int
    validation_errors: tuple[str, ...] = ()


def _extract_json(raw: str) -> dict[str, object]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end < start:
        raise ValueError("Model output does not contain a JSON object.")
    parsed = json.loads(candidate[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Model output JSON must be an object.")
    return parsed


def _validate_explanation(
    explanation: GeneratedExplanation,
    *,
    analysis: RuleAnalysis,
    sources: list[RetrievedChunk],
) -> list[str]:
    errors: list[str] = []
    allowed_evidence_ids = {
        f"evidence-{index}"
        for index, _ in enumerate(analysis.primary.evidence, 1)
    }
    allowed_citation_ids = {source.chunk_id for source in sources}
    grounding_text = "\n".join(
        [
            analysis.primary.summary,
            analysis.primary.recommendation,
            analysis.primary.recommendation_sql or "",
            *analysis.primary.evidence,
            *(source.text for source in sources),
        ]
    )
    allowed_numbers = set(_NUMBER_PATTERN.findall(grounding_text))

    unknown_evidence = set(explanation.evidence_ids) - allowed_evidence_ids
    if unknown_evidence:
        errors.append(
            "explanation uses unknown evidence IDs: "
            + ", ".join(sorted(unknown_evidence))
        )
    unknown_citations = set(explanation.citation_ids) - allowed_citation_ids
    if unknown_citations:
        errors.append(
            "explanation uses unknown citation IDs: "
            + ", ".join(sorted(unknown_citations))
        )
    if len(set(explanation.evidence_ids)) != len(explanation.evidence_ids):
        errors.append("explanation repeats evidence IDs")
    if len(set(explanation.citation_ids)) != len(explanation.citation_ids):
        errors.append("explanation repeats citation IDs")

    for field_name in ("summary", "recommendation"):
        text = getattr(explanation, field_name)
        novel_numbers = set(_NUMBER_PATTERN.findall(text)) - allowed_numbers
        if novel_numbers:
            errors.append(
                f"{field_name} invents numeric values: "
                + ", ".join(sorted(novel_numbers))
            )
        if _SQL_ACTION_PATTERN.search(text):
            errors.append(
                f"{field_name} contains SQL-like change instructions"
            )
        if "http://" in text.lower() or "https://" in text.lower():
            errors.append(f"{field_name} contains an untrusted URL")
        unknown_code_tokens = {
            token
            for token in _CODE_TOKEN_PATTERN.findall(text)
            if token.casefold() not in grounding_text.casefold()
        }
        if unknown_code_tokens:
            errors.append(
                f"{field_name} invents code identifiers: "
                + ", ".join(sorted(unknown_code_tokens))
            )
    return errors


def _parse_and_validate(
    raw: str,
    *,
    analysis: RuleAnalysis,
    sources: list[RetrievedChunk],
) -> tuple[GeneratedExplanation | None, list[str]]:
    try:
        payload = _extract_json(raw)
        explanation = GeneratedExplanation.model_validate(payload)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        return None, [f"structured output validation failed: {exc}"]
    errors = _validate_explanation(
        explanation,
        analysis=analysis,
        sources=sources,
    )
    return (explanation if not errors else None), errors


def _deterministic_citations(
    sources: list[RetrievedChunk],
    *,
    selected_chunk_ids: set[str] | None = None,
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        if (
            selected_chunk_ids is not None
            and source.chunk_id not in selected_chunk_ids
        ):
            continue
        key = (source.document_id, source.title, source.section)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document_id=source.document_id,
                title=source.title,
                section=source.section,
            )
        )
    return citations


def _category_supporting_sources(
    category: IssueCategory,
    sources: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    required_document_id = _PRIMARY_SOURCE_BY_CATEGORY.get(category)
    if required_document_id is None:
        return []
    return [
        source
        for source in sources
        if source.document_id == required_document_id
    ]


def _assemble_report(
    *,
    analysis: RuleAnalysis,
    sources: list[RetrievedChunk],
    explanation: GeneratedExplanation,
) -> AnalysisReport:
    finding = analysis.primary
    selected_chunk_ids = set(explanation.citation_ids)
    return AnalysisReport(
        issue_category=finding.category,
        severity=finding.severity,
        summary=explanation.summary,
        plan_evidence=list(finding.evidence),
        recommendation=explanation.recommendation,
        recommendation_sql=finding.recommendation_sql,
        citations=_deterministic_citations(
            sources,
            selected_chunk_ids=selected_chunk_ids,
        ),
        insufficient_context=False,
    )


def _assemble_grounded_fallback(
    *,
    analysis: RuleAnalysis,
    sources: list[RetrievedChunk],
) -> AnalysisReport:
    finding = analysis.primary
    return AnalysisReport(
        issue_category=finding.category,
        severity=finding.severity,
        summary=finding.summary,
        plan_evidence=list(finding.evidence),
        recommendation=finding.recommendation,
        recommendation_sql=finding.recommendation_sql,
        citations=_deterministic_citations(sources),
        insufficient_context=False,
    )


class GroundedReportGenerator:
    def __init__(
        self,
        client: ChatCompleter,
        *,
        repair_cutoff_seconds: float = 8.0,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._client = client
        self._repair_cutoff_seconds = repair_cutoff_seconds
        self._clock = clock

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    def _latency_ms(self, started: float) -> int:
        return round((self._clock() - started) * 1000)

    def generate(
        self,
        *,
        analysis: RuleAnalysis,
        sources: list[RetrievedChunk],
    ) -> GenerationResult:
        if analysis.primary.category == IssueCategory.NO_CLEAR_ISSUE:
            return GenerationResult(
                report=build_fallback_report(analysis),
                source="deterministic_fallback",
                repair_attempted=False,
                generation_latency_ms=0,
                validation_errors=("insufficient deterministic evidence",),
            )
        if not sources:
            return GenerationResult(
                report=build_fallback_report(analysis),
                source="deterministic_fallback",
                repair_attempted=False,
                generation_latency_ms=0,
                validation_errors=("no retrieved sources available for enrichment",),
            )

        supported_sources = _category_supporting_sources(
            analysis.primary.category,
            sources,
        )
        if not supported_sources:
            return GenerationResult(
                report=build_fallback_report(analysis),
                source="deterministic_fallback",
                repair_attempted=False,
                generation_latency_ms=0,
                validation_errors=(
                    "no category-supporting retrieved source available for enrichment",
                ),
            )

        started = self._clock()
        try:
            first_output = self._client.complete(
                build_generation_messages(analysis.primary, supported_sources),
                tools=GENERATION_TOOLS,
            )
        except Exception as exc:
            return GenerationResult(
                report=_assemble_grounded_fallback(
                    analysis=analysis,
                    sources=supported_sources,
                ),
                source="deterministic_fallback",
                repair_attempted=False,
                generation_latency_ms=self._latency_ms(started),
                validation_errors=(f"generation provider failed: {type(exc).__name__}",),
            )

        explanation, errors = _parse_and_validate(
            first_output,
            analysis=analysis,
            sources=supported_sources,
        )
        first_attempt_seconds = self._clock() - started
        if explanation is not None:
            return GenerationResult(
                report=_assemble_report(
                    analysis=analysis,
                    sources=supported_sources,
                    explanation=explanation,
                ),
                source="foundry_local",
                repair_attempted=False,
                generation_latency_ms=round(first_attempt_seconds * 1000),
            )

        if first_attempt_seconds > self._repair_cutoff_seconds:
            return GenerationResult(
                report=_assemble_grounded_fallback(
                    analysis=analysis,
                    sources=supported_sources,
                ),
                source="deterministic_fallback",
                repair_attempted=False,
                generation_latency_ms=round(first_attempt_seconds * 1000),
                validation_errors=tuple(
                    [f"initial: {error}" for error in errors]
                    + [
                        "repair skipped because initial generation exceeded "
                        f"{self._repair_cutoff_seconds:.1f} seconds"
                    ]
                ),
            )

        try:
            repaired_output = self._client.complete(
                build_repair_messages(
                    analysis.primary,
                    supported_sources,
                    invalid_output=first_output,
                    validation_errors=errors,
                ),
                tools=GENERATION_TOOLS,
            )
        except Exception as exc:
            return GenerationResult(
                report=_assemble_grounded_fallback(
                    analysis=analysis,
                    sources=supported_sources,
                ),
                source="deterministic_fallback",
                repair_attempted=True,
                generation_latency_ms=self._latency_ms(started),
                validation_errors=tuple(
                    [f"initial: {error}" for error in errors]
                    + [f"repair provider failed: {type(exc).__name__}"]
                ),
            )

        repaired_explanation, repair_errors = _parse_and_validate(
            repaired_output,
            analysis=analysis,
            sources=supported_sources,
        )
        if repaired_explanation is not None:
            return GenerationResult(
                report=_assemble_report(
                    analysis=analysis,
                    sources=supported_sources,
                    explanation=repaired_explanation,
                ),
                source="foundry_local",
                repair_attempted=True,
                generation_latency_ms=self._latency_ms(started),
            )
        return GenerationResult(
            report=_assemble_grounded_fallback(
                analysis=analysis,
                sources=supported_sources,
            ),
            source="deterministic_fallback",
            repair_attempted=True,
            generation_latency_ms=self._latency_ms(started),
            validation_errors=tuple(
                [f"initial: {error}" for error in errors]
                + [f"repair: {error}" for error in repair_errors]
            ),
        )
