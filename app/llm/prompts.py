import json

from app.analysis.rule_engine import Finding
from app.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = """You are the grounded explanation layer of QueryPilot Local.
The application has already diagnosed the PostgreSQL plan with deterministic
rules. Explain that finding for a human by using only the supplied plan evidence
and retrieved source chunks.

Call the submit_grounded_report tool exactly once. Do not write normal chat
content or Markdown.
Required shape:
{
  "summary": "grounded explanation",
  "recommendation": "grounded next step",
  "evidence_ids": ["evidence-1"],
  "citation_ids": ["chunk-id"]
}

Rules:
- Write a concise, useful summary and recommendation in English.
- Include all four keys exactly once. Do not return nested objects.
- Both generated texts must be supported by the referenced evidence and sources.
- Use only evidence_ids and citation_ids supplied by the application.
- Do not invent metrics, object names, causes, citations, or SQL.
- Do not change the diagnosis, severity, plan evidence, or recommendation SQL.
- Do not claim that an index or configuration change is certainly beneficial.
- Recommend review and plan comparison, not automatic application.
"""

GENERATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_grounded_report",
            "description": (
                "Submit a concise explanation grounded in the supplied plan "
                "evidence and retrieved PostgreSQL sources."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "minLength": 20,
                        "maxLength": 1_000,
                    },
                    "recommendation": {
                        "type": "string",
                        "minLength": 20,
                        "maxLength": 1_000,
                    },
                    "evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 10,
                    },
                    "citation_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 3,
                    },
                },
                "required": [
                    "summary",
                    "recommendation",
                    "evidence_ids",
                    "citation_ids",
                ],
                "additionalProperties": False,
            },
        },
    }
]


def _generation_payload(
    finding: Finding,
    sources: list[RetrievedChunk],
) -> dict[str, object]:
    evidence = [
        {"evidence_id": f"evidence-{index}", "text": text}
        for index, text in enumerate(finding.evidence, 1)
    ]
    return {
        "deterministic_finding": {
            "issue_category": finding.category.value,
            "severity": finding.severity.value,
            "summary": finding.summary,
            "plan_evidence": evidence,
            "recommendation": finding.recommendation,
            "recommendation_sql": finding.recommendation_sql,
        },
        "retrieved_sources": [
            {
                "citation_id": source.chunk_id,
                "document_id": source.document_id,
                "title": source.title,
                "section": source.section,
                "text": source.text,
                "source_url": source.source_url,
            }
            for source in sources
        ],
        "grounding_contract": {
            "allowed_evidence_ids": [
                item["evidence_id"] for item in evidence
            ],
            "allowed_citation_ids": [source.chunk_id for source in sources],
            "deterministic_fields_are_read_only": [
                "issue_category",
                "severity",
                "plan_evidence",
                "recommendation_sql",
            ],
        },
        "required_output_example": {
            "summary": "The observed plan evidence indicates ...",
            "recommendation": (
                "Review ... and compare the resulting plan ..."
            ),
            "evidence_ids": ["evidence-1"],
            "citation_ids": [sources[0].chunk_id],
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
                    + "\nReturn one corrected JSON object. Keep the explanation "
                    "grounded and use only the supplied evidence and citation IDs."
                ),
            },
        ]
    )
    return messages
