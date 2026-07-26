import json
from pathlib import Path

from app.config import get_settings
from app.llm.foundry_client import FoundryLocalClient
from app.rag.embedder import FoundryEmbedder
from app.rag.index import VectorIndex
from app.rag.retriever import Retriever

ROOT = Path(__file__).resolve().parents[1]

QUERIES = {
    "potential_missing_index": (
        "A selective filter performs a sequential scan and removes almost every row."
    ),
    "expensive_nested_loop": (
        "A nested loop executes its inner index scan thousands of times."
    ),
    "disk_based_sort": (
        "Sort Method external merge and Sort Space Type Disk appear in EXPLAIN."
    ),
    "cardinality_misestimation": (
        "Actual rows are one hundred times higher than planner estimated rows."
    ),
}


def main() -> None:
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
        output = {
            category: [
                {
                    "score": round(result.score, 4),
                    "document_id": result.document_id,
                    "section": result.section,
                }
                for result in retriever.retrieve(query, top_k=3)
            ]
            for category, query in QUERIES.items()
        }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

