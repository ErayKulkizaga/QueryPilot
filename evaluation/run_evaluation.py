import argparse
import json
from pathlib import Path
from statistics import mean

from app.analysis.plan_parser import parse_explain
from app.analysis.rule_engine import analyze_plan, build_fallback_report
from app.config import get_settings
from app.llm.foundry_client import FoundryLocalClient
from app.llm.generator import GroundedReportGenerator
from app.rag.embedder import FoundryEmbedder
from app.rag.index import VectorIndex
from app.rag.retriever import RetrievedChunk, Retriever

ROOT = Path(__file__).resolve().parents[1]


def _load_scenarios(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _rate(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _p95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, round(0.95 * len(ordered) + 0.5) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run QueryPilot fixture evaluation.")
    parser.add_argument("--with-retrieval", action="store_true")
    parser.add_argument("--with-generation", action="store_true")
    parser.add_argument("--generation-limit", type=int, default=4)
    parser.add_argument(
        "--chat-model",
        help="Override the configured Foundry Local chat model alias.",
    )
    parser.add_argument(
        "--output",
        default="evaluation/results.json",
        help="Result path, relative to the project root unless absolute.",
    )
    args = parser.parse_args()

    scenarios = _load_scenarios(ROOT / "evaluation" / "scenarios.jsonl")
    settings = get_settings()
    chat_model_alias = args.chat_model or settings.foundry_chat_model
    analyses = {
        str(scenario["scenario_id"]): analyze_plan(parse_explain(scenario["plan"]))
        for scenario in scenarios
    }
    retrieval_by_id: dict[str, list[RetrievedChunk]] = {}
    generation_by_id: dict[str, object] = {}

    needs_foundry = args.with_retrieval or args.with_generation
    if needs_foundry:
        index_root = ROOT / "data" / "index"
        index = VectorIndex.load(
            vectors_path=index_root / "querypilot_embeddings.npz",
            metadata_path=index_root / "querypilot_chunks.json",
        )
        with FoundryLocalClient(
            app_name=settings.foundry_app_name,
            chat_model_alias=chat_model_alias,
            embedding_model_alias=settings.foundry_embedding_model,
        ) as client:
            retriever = Retriever(index=index, embedder=FoundryEmbedder(client))
            for scenario in scenarios:
                scenario_id = str(scenario["scenario_id"])
                query = scenario.get("retrieval_query")
                if query:
                    retrieval_by_id[scenario_id] = retriever.retrieve(
                        str(query),
                        top_k=3,
                    )

            if args.with_generation:
                generator = GroundedReportGenerator(
                    client,
                    repair_cutoff_seconds=settings.generation_repair_cutoff_seconds,
                )
                candidates = [
                    scenario
                    for scenario in scenarios
                    if scenario.get("evaluate_generation")
                ][: args.generation_limit]
                for scenario in candidates:
                    scenario_id = str(scenario["scenario_id"])
                    generation_by_id[scenario_id] = generator.generate(
                        analysis=analyses[scenario_id],
                        sources=retrieval_by_id.get(scenario_id, []),
                    )

    results: list[dict[str, object]] = []
    for scenario in scenarios:
        scenario_id = str(scenario["scenario_id"])
        analysis = analyses[scenario_id]
        deterministic_report = build_fallback_report(analysis)
        retrieved = retrieval_by_id.get(scenario_id, [])
        expected_document_id = scenario.get("expected_document_id")
        retrieved_document_ids = [item.document_id for item in retrieved]
        generation = generation_by_id.get(scenario_id)
        if args.with_retrieval and expected_document_id:
            retrieval_hit_at_3 = expected_document_id in retrieved_document_ids
        else:
            retrieval_hit_at_3 = None
        results.append(
            {
                "scenario_id": scenario_id,
                "expected_category": scenario["expected_category"],
                "actual_category": analysis.primary.category.value,
                "diagnosis_correct": (
                    analysis.primary.category.value == scenario["expected_category"]
                ),
                "expected_insufficient_context": scenario[
                    "expected_insufficient_context"
                ],
                "actual_insufficient_context": (
                    deterministic_report.insufficient_context
                ),
                "no_answer_correct": (
                    deterministic_report.insufficient_context
                    == scenario["expected_insufficient_context"]
                ),
                "expected_document_id": expected_document_id,
                "retrieved_document_ids": retrieved_document_ids,
                "retrieval_hit_at_3": retrieval_hit_at_3,
                "generation_source": (
                    generation.source if generation is not None else None
                ),
                "generation_latency_ms": (
                    generation.generation_latency_ms
                    if generation is not None
                    else None
                ),
                "generation_validation_errors": (
                    list(generation.validation_errors)
                    if generation is not None
                    else None
                ),
                "response_citations_valid": (
                    all(
                        citation.document_id in retrieved_document_ids
                        for citation in generation.report.citations
                    )
                    if generation is not None
                    else None
                ),
            }
        )

    retrieval_values = [
        bool(result["retrieval_hit_at_3"])
        for result in results
        if result["retrieval_hit_at_3"] is not None
    ]
    generation_results = [
        result for result in results if result["generation_source"] is not None
    ]
    generation_latencies = [
        int(result["generation_latency_ms"])
        for result in generation_results
        if result["generation_latency_ms"] is not None
    ]
    output = {
        "scenario_count": len(results),
        "models": {
            "embedding": settings.foundry_embedding_model,
            "chat": chat_model_alias,
        },
        "metrics": {
            "rule_diagnosis_accuracy": _rate(
                [bool(result["diagnosis_correct"]) for result in results]
            ),
            "no_answer_accuracy": _rate(
                [bool(result["no_answer_correct"]) for result in results]
            ),
            "retrieval_hit_at_3": _rate(retrieval_values),
            "generation_sample_count": len(generation_results),
            "accepted_generation_rate": _rate(
                [
                    result["generation_source"] == "foundry_local"
                    for result in generation_results
                ]
            ),
            "response_citation_valid_rate": _rate(
                [
                    bool(result["response_citations_valid"])
                    for result in generation_results
                ]
            ),
            "generation_average_latency_ms": (
                round(mean(generation_latencies)) if generation_latencies else None
            ),
            "generation_p95_latency_ms": _p95(generation_latencies),
        },
        "results": results,
    }
    results_path = Path(args.output)
    if not results_path.is_absolute():
        results_path = ROOT / results_path
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
