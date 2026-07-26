import json

from app.analysis.rule_engine import Finding
from app.rag.retriever import RetrievedChunk
from app.schemas import IssueCategory

SYSTEM_PROMPT = """You are the explanation selection layer of QueryPilot Local.
The application supplies approved sentences derived from deterministic rules.
Retrieved sources are supporting context only.

Return exactly one JSON object and no Markdown.
Rules:
- Return only summary_sentence_id and recommendation_sentence_id.
- Copy each ID exactly from the corresponding approved sentence list.
- Never write, rewrite, paraphrase, or add explanatory text.
- Do not output SQL, citations, facts, issue categories, severity, or plan evidence.
"""


def build_approved_sentences(finding: Finding) -> dict[str, dict[str, str]]:
    category_sentences = {
        IssueCategory.POTENTIAL_MISSING_INDEX: {
            "summary_context": (
                "The selective filter makes the sequential scan a candidate "
                "for index review."
            ),
            "recommendation_context": (
                "Review whether an index aligned with the filter reduces scanned "
                "rows, then compare the new plan and write overhead."
            ),
        },
        IssueCategory.EXPENSIVE_NESTED_LOOP: {
            "summary_context": (
                "Repeated execution of the inner plan can multiply the cost "
                "of the nested loop."
            ),
            "recommendation_context": (
                "Review join-key indexes, selectivity, and statistics, then compare "
                "alternative plans without forcing a join type."
            ),
        },
        IssueCategory.DISK_BASED_SORT: {
            "summary_context": (
                "Temporary disk use shows that the sort exceeded available working "
                "memory for this operation."
            ),
            "recommendation_context": (
                "First reduce the rows entering the sort and review ordered index "
                "access; consider session-level memory tuning only after plan comparison."
            ),
        },
        IssueCategory.CARDINALITY_MISESTIMATION: {
            "summary_context": (
                "The gap between estimated and observed rows can lead the planner "
                "to choose an inefficient plan."
            ),
            "recommendation_context": (
                "Refresh statistics and inspect skew or correlation before considering "
                "higher statistics targets or extended statistics."
            ),
        },
    }
    contextual = category_sentences.get(finding.category, {})
    summary_sentences = {"summary_finding": finding.summary}
    recommendation_sentences = {
        "recommendation_finding": finding.recommendation
    }
    if contextual:
        summary_sentences["summary_context"] = contextual["summary_context"]
        recommendation_sentences["recommendation_context"] = contextual[
            "recommendation_context"
        ]
    return {
        "summary": summary_sentences,
        "recommendation": recommendation_sentences,
    }


def _generation_payload(
    finding: Finding,
    sources: list[RetrievedChunk],
) -> dict[str, object]:
    approved_sentences = build_approved_sentences(finding)
    return {
        "deterministic_finding": {
            "issue_category": finding.category.value,
            "severity": finding.severity.value,
            "summary": finding.summary,
            "plan_evidence": list(finding.evidence),
            "recommendation": finding.recommendation,
            "recommendation_sql": finding.recommendation_sql,
        },
        "retrieved_sources": [
            {
                "document_id": source.document_id,
                "title": source.title,
                "section": source.section,
            }
            for source in sources
        ],
        "approved_sentences": approved_sentences,
        "selection_task": {
            "allowed_summary_sentence_ids": list(
                approved_sentences["summary"]
            ),
            "allowed_recommendation_sentence_ids": list(
                approved_sentences["recommendation"]
            ),
        },
        "required_output_example": {
            "summary_sentence_id": "summary_context",
            "recommendation_sentence_id": "recommendation_context",
        },
    }


def build_generation_messages(
    finding: Finding,
    sources: list[RetrievedChunk],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                _generation_payload(finding, sources),
                ensure_ascii=False,
                indent=2,
            ),
        },
    ]


def build_repair_messages(
    finding: Finding,
    sources: list[RetrievedChunk],
    *,
    invalid_output: str,
    validation_errors: list[str],
) -> list[dict[str, str]]:
    messages = build_generation_messages(finding, sources)
    messages.extend(
        [
            {"role": "assistant", "content": invalid_output[:6_000]},
            {
                "role": "user",
                "content": (
                    "Your previous output was rejected for these reasons:\n- "
                    + "\n- ".join(validation_errors)
                    + "\nReturn one corrected JSON object containing only exact IDs "
                    "from the approved sentence lists."
                ),
            },
        ]
    )
    return messages
