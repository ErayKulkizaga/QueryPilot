import json

from app.analysis.rule_engine import Finding, RuleAnalysis
from app.llm.generator import GroundedReportGenerator
from app.rag.retriever import RetrievedChunk
from app.schemas import IssueCategory, Severity


class FakeChatClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.messages: list[list[dict[str, str]]] = []

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, object]] | None = None,
    ) -> str:
        self.messages.append(messages)
        assert tools is not None
        assert tools[0]["function"]["name"] == "submit_grounded_report"
        return next(self._responses)


class FailingChatClient:
    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, object]] | None = None,
    ) -> str:
        raise TimeoutError("local model timed out")


class SequenceClock:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


def missing_index_analysis() -> RuleAnalysis:
    finding = Finding(
        category=IssueCategory.POTENTIAL_MISSING_INDEX,
        severity=Severity.HIGH,
        confidence=0.95,
        summary="A sequential scan discarded most examined rows.",
        evidence=(
            "Seq Scan on customers",
            "Rows Removed by Filter: 24,999",
            "Filter selectivity: 0.00%",
        ),
        recommendation="Review an index that matches the selective filter.",
        recommendation_sql="CREATE INDEX idx_customers_email ON customers (email);",
    )
    return RuleAnalysis(primary=finding, findings=(finding,))


def no_clear_issue_analysis() -> RuleAnalysis:
    finding = Finding(
        category=IssueCategory.NO_CLEAR_ISSUE,
        severity=Severity.LOW,
        confidence=0.80,
        summary="No configured rule found a sufficiently strong signal.",
        evidence=("Execution Time: 0.30 ms", "Plan nodes inspected: 1"),
        recommendation="Capture representative workload evidence.",
    )
    return RuleAnalysis(primary=finding, findings=(finding,))


def index_source() -> RetrievedChunk:
    return RetrievedChunk(
        score=0.82,
        chunk_id="pg-indexes-01:selective-predicates:01",
        document_id="pg-indexes-01",
        title="PostgreSQL Indexes and Selective Predicates",
        section="Selective predicates",
        text="An index is useful when its leading key narrows the candidate set.",
        source_url="https://www.postgresql.org/docs/current/indexes.html",
    )


def sorting_source() -> RetrievedChunk:
    return RetrievedChunk(
        score=0.79,
        chunk_id="pg-sorting-01:ordered-index:01",
        document_id="pg-sorting-01",
        title="PostgreSQL Sorting and Temporary Disk Use",
        section="Ordered index access",
        text="Ordered index access can sometimes avoid a separate sort.",
        source_url="https://www.postgresql.org/docs/current/indexes-ordering.html",
    )


def valid_payload() -> dict[str, object]:
    return {
        "summary": (
            "The sequential scan discarded most examined rows, so the "
            "selective filter deserves index review."
        ),
        "recommendation": (
            "Review an index aligned with the filter, then compare the "
            "resulting plan and write overhead before making a decision."
        ),
        "evidence_ids": ["evidence-1", "evidence-2", "evidence-3"],
        "citation_ids": ["pg-indexes-01:selective-predicates:01"],
    }


def test_assembles_deterministic_fields_around_valid_explanation() -> None:
    client = FakeChatClient([json.dumps(valid_payload())])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "foundry_local"
    assert result.repair_attempted is False
    assert result.report.issue_category == IssueCategory.POTENTIAL_MISSING_INDEX
    assert result.report.plan_evidence[1] == "Rows Removed by Filter: 24,999"
    assert result.report.recommendation_sql == (
        "CREATE INDEX idx_customers_email ON customers (email);"
    )
    assert result.report.summary == (
        "The sequential scan discarded most examined rows, so the selective "
        "filter deserves index review."
    )
    assert result.report.citations[0].document_id == "pg-indexes-01"
    assert result.report.insufficient_context is False
    assert len(client.messages) == 1


def test_unknown_citation_is_repaired_to_retrieved_chunk() -> None:
    invalid = valid_payload()
    invalid["citation_ids"] = ["invented-source-99"]
    client = FakeChatClient([json.dumps(invalid), json.dumps(valid_payload())])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "foundry_local"
    assert result.repair_attempted is True
    assert result.report.citations[0].document_id == "pg-indexes-01"
    assert len(client.messages) == 2
    assert "unknown citation IDs" in client.messages[1][-1]["content"]


def test_unknown_evidence_id_falls_back_after_fast_repair() -> None:
    invalid = valid_payload()
    invalid["evidence_ids"] = ["evidence-invented"]
    client = FakeChatClient([json.dumps(invalid), json.dumps(invalid)])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "deterministic_fallback"
    assert result.repair_attempted is True
    assert result.report.insufficient_context is False
    assert result.report.citations[0].document_id == "pg-indexes-01"
    assert any("unknown evidence IDs" in error for error in result.validation_errors)
    assert len(client.messages) == 2


def test_model_cannot_control_evidence_or_recommendation_sql() -> None:
    invalid = valid_payload()
    invalid["plan_evidence"] = ["Changed evidence"]
    invalid["recommendation_sql"] = "CREATE INDEX made_up ON customers (full_name);"
    client = FakeChatClient([json.dumps(invalid), json.dumps(invalid)])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "deterministic_fallback"
    assert any(
        "structured output validation failed" in error
        for error in result.validation_errors
    )


def test_slow_invalid_first_attempt_skips_repair() -> None:
    invalid = valid_payload()
    invalid["citation_ids"] = ["invented-source-99"]
    client = FakeChatClient([json.dumps(invalid)])
    clock = SequenceClock([0.0, 10.0])

    result = GroundedReportGenerator(
        client,
        repair_cutoff_seconds=8.0,
        clock=clock,
    ).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "deterministic_fallback"
    assert result.repair_attempted is False
    assert result.generation_latency_ms == 10_000
    assert result.report.insufficient_context is False
    assert result.report.citations[0].document_id == "pg-indexes-01"
    assert any("repair skipped" in error for error in result.validation_errors)
    assert len(client.messages) == 1


def test_no_answer_bypasses_model_generation() -> None:
    client = FakeChatClient([])

    result = GroundedReportGenerator(client).generate(
        analysis=no_clear_issue_analysis(),
        sources=[index_source()],
    )

    assert result.source == "deterministic_fallback"
    assert result.repair_attempted is False
    assert result.generation_latency_ms == 0
    assert result.report.issue_category == IssueCategory.NO_CLEAR_ISSUE
    assert result.report.recommendation_sql is None
    assert client.messages == []


def test_missing_retrieval_context_bypasses_model_generation() -> None:
    client = FakeChatClient([])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[],
    )

    assert result.source == "deterministic_fallback"
    assert result.report.insufficient_context is False
    assert result.validation_errors == (
        "no retrieved sources available for enrichment",
    )
    assert client.messages == []


def test_provider_failure_returns_deterministic_fallback() -> None:
    result = GroundedReportGenerator(FailingChatClient()).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "deterministic_fallback"
    assert result.repair_attempted is False
    assert result.report.insufficient_context is False
    assert result.report.citations[0].document_id == "pg-indexes-01"
    assert result.validation_errors == ("generation provider failed: TimeoutError",)


def test_irrelevant_retrieved_sources_are_not_cited() -> None:
    result = GroundedReportGenerator(
        FakeChatClient([json.dumps(valid_payload())])
    ).generate(
        analysis=missing_index_analysis(),
        sources=[sorting_source(), index_source()],
    )

    assert result.source == "foundry_local"
    assert [citation.document_id for citation in result.report.citations] == [
        "pg-indexes-01"
    ]


def test_missing_category_supporting_source_bypasses_generation() -> None:
    client = FakeChatClient([])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[sorting_source()],
    )

    assert result.source == "deterministic_fallback"
    assert result.report.citations == []
    assert result.validation_errors == (
        "no category-supporting retrieved source available for enrichment",
    )
    assert client.messages == []


def test_invented_number_sql_instruction_and_identifier_are_rejected() -> None:
    invalid = valid_payload()
    invalid["summary"] = (
        "The plan will improve by 75% after this unsupported change."
    )
    invalid["recommendation"] = (
        "CREATE INDEX `invented_customer_index` immediately because the model "
        "predicts a guaranteed gain."
    )
    client = FakeChatClient([json.dumps(invalid), json.dumps(invalid)])

    result = GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "deterministic_fallback"
    assert any("invents numeric values" in error for error in result.validation_errors)
    assert any(
        "SQL-like change instructions" in error
        for error in result.validation_errors
    )
    assert any(
        "invents code identifiers" in error
        for error in result.validation_errors
    )


def test_prompt_contains_plan_evidence_and_retrieved_source_text() -> None:
    client = FakeChatClient([json.dumps(valid_payload())])

    GroundedReportGenerator(client).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    prompt = client.messages[0][1]["content"]
    assert "Rows Removed by Filter: 24,999" in prompt
    assert "An index is useful when its leading key" in prompt
    assert "pg-indexes-01:selective-predicates:01" in prompt


def test_identifier_from_deterministic_recommendation_sql_is_allowed() -> None:
    payload = valid_payload()
    payload["recommendation"] = (
        "Review `idx_customers_email` as a candidate, then compare the plan "
        "and write overhead before deciding whether to apply it."
    )

    result = GroundedReportGenerator(
        FakeChatClient([json.dumps(payload)])
    ).generate(
        analysis=missing_index_analysis(),
        sources=[index_source()],
    )

    assert result.source == "foundry_local"
    assert "`idx_customers_email`" in result.report.recommendation
