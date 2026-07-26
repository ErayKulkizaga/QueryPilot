import json
from pathlib import Path

from app.analysis.plan_parser import parse_explain
from app.analysis.rule_engine import analyze_plan
from app.config import get_settings
from app.llm.foundry_client import FoundryLocalClient
from app.llm.generator import GroundedReportGenerator
from app.rag.embedder import FoundryEmbedder
from app.rag.index import VectorIndex
from app.rag.retriever import Retriever

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    raw_plan = [
        {
            "Plan": {
                "Node Type": "Seq Scan",
                "Relation Name": "customers",
                "Plan Rows": 1,
                "Actual Rows": 1,
                "Actual Loops": 1,
                "Rows Removed by Filter": 24_999,
                "Filter": "(email = 'demo@example.com'::text)",
                "Actual Total Time": 3.65,
            },
            "Planning Time": 1.70,
            "Execution Time": 3.70,
        }
    ]
    analysis = analyze_plan(parse_explain(raw_plan))
    index_root = ROOT / "data" / "index"
    index = VectorIndex.load(
        vectors_path=index_root / "querypilot_embeddings.npz",
        metadata_path=index_root / "querypilot_chunks.json",
    )
    settings = get_settings()

    with FoundryLocalClient(
        app_name=settings.foundry_app_name,
        chat_model_alias=settings.foundry_chat_model,
        embedding_model_alias=settings.foundry_embedding_model,
    ) as client:
        retriever = Retriever(index=index, embedder=FoundryEmbedder(client))
        sources = retriever.retrieve(
            "Selective sequential scan removed almost every row; review index evidence.",
            top_k=3,
        )
        result = GroundedReportGenerator(client).generate(
            analysis=analysis,
            sources=sources,
        )

    output = {
        "source": result.source,
        "repair_attempted": result.repair_attempted,
        "generation_latency_ms": result.generation_latency_ms,
        "validation_errors": result.validation_errors,
        "retrieved_document_ids": [source.document_id for source in sources],
        "report": result.report.model_dump(mode="json"),
    }
    print(json.dumps(output, indent=2))
    results_path = ROOT / "evaluation" / "generation_smoke_result.json"
    results_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
