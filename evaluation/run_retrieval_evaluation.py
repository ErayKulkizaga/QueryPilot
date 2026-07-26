import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from app.config import get_settings
from app.llm.foundry_client import FoundryLocalClient
from app.rag.embedder import FoundryEmbedder
from app.rag.index import VectorIndex
from app.rag.retriever import Retriever

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cases_path = ROOT / "evaluation" / "retrieval_cases.json"
    results_path = ROOT / "evaluation" / "retrieval_results.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    index_root = ROOT / "data" / "index"
    index = VectorIndex.load(
        vectors_path=index_root / "querypilot_embeddings.npz",
        metadata_path=index_root / "querypilot_chunks.json",
    )
    settings = get_settings()
    results: list[dict[str, object]] = []

    with FoundryLocalClient(
        app_name=settings.foundry_app_name,
        chat_model_alias=settings.foundry_chat_model,
        embedding_model_alias=settings.foundry_embedding_model,
    ) as client:
        retriever = Retriever(index=index, embedder=FoundryEmbedder(client))
        for case in cases:
            started = perf_counter()
            retrieved = retriever.retrieve(case["query"], top_k=3)
            latency_ms = round((perf_counter() - started) * 1000)
            document_ids = [item.document_id for item in retrieved]
            expected = case["expected_document_id"]
            results.append(
                {
                    "case_id": case["case_id"],
                    "expected_document_id": expected,
                    "retrieved_document_ids": document_ids,
                    "top1_hit": document_ids[0] == expected,
                    "hit_at_3": expected in document_ids,
                    "latency_ms": latency_ms,
                }
            )

    total = len(results)
    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "embedding_model": settings.foundry_embedding_model,
        "index": {"chunks": index.size, "dimensions": index.dimensions},
        "metrics": {
            "cases": total,
            "top1_accuracy": sum(bool(item["top1_hit"]) for item in results) / total,
            "hit_at_3": sum(bool(item["hit_at_3"]) for item in results) / total,
            "average_query_latency_ms": round(
                sum(int(item["latency_ms"]) for item in results) / total
            ),
        },
        "results": results,
    }
    results_path.write_text(
        json.dumps(output, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

