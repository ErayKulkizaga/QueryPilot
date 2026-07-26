import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.llm.foundry_client import FoundryLocalClient
from app.rag.chunker import chunk_knowledge_base
from app.rag.embedder import FoundryEmbedder
from app.rag.index import VectorIndex

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local QueryPilot vector index.")
    parser.add_argument("--knowledge", type=Path, default=ROOT / "knowledge")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "index")
    args = parser.parse_args()

    chunks = chunk_knowledge_base(args.knowledge)
    settings = get_settings()
    with FoundryLocalClient(
        app_name=settings.foundry_app_name,
        chat_model_alias=settings.foundry_chat_model,
        embedding_model_alias=settings.foundry_embedding_model,
    ) as client:
        vectors = FoundryEmbedder(client).embed_documents(
            [chunk.text for chunk in chunks]
        )

    index = VectorIndex(vectors=vectors, chunks=chunks)
    vectors_path = args.output / "querypilot_embeddings.npz"
    metadata_path = args.output / "querypilot_chunks.json"
    index.save(vectors_path=vectors_path, metadata_path=metadata_path)
    print(
        json.dumps(
            {
                "documents": len({chunk.document_id for chunk in chunks}),
                "chunks": index.size,
                "dimensions": index.dimensions,
                "vectors_path": str(vectors_path),
                "metadata_path": str(metadata_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

