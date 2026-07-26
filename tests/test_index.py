from pathlib import Path

import numpy as np
import pytest

from app.rag.chunker import KnowledgeChunk
from app.rag.index import VectorIndex, VectorIndexError


def chunk(chunk_id: str, document_id: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        title=document_id,
        section="Test",
        text=f"Text for {document_id}",
        source_path=f"{document_id}.md",
        source_url=f"https://example.test/{document_id}",
    )


def test_cosine_search_returns_highest_similarity_first() -> None:
    index = VectorIndex(
        vectors=np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]),
        chunks=[chunk("a:01", "a"), chunk("b:01", "b"), chunk("c:01", "c")],
    )

    results = index.search([0.9, 0.1], top_k=2)

    assert [result.chunk.document_id for result in results] == ["a", "b"]
    assert results[0].score > results[1].score


def test_round_trips_npz_and_json_metadata(tmp_path: Path) -> None:
    index = VectorIndex(
        vectors=np.array([[3.0, 4.0], [4.0, 3.0]]),
        chunks=[chunk("a:01", "a"), chunk("b:01", "b")],
    )
    vectors_path = tmp_path / "index.npz"
    metadata_path = tmp_path / "metadata.json"

    index.save(vectors_path=vectors_path, metadata_path=metadata_path)
    loaded = VectorIndex.load(
        vectors_path=vectors_path,
        metadata_path=metadata_path,
    )

    assert loaded.size == 2
    assert loaded.dimensions == 2
    assert loaded.search([1.0, 0.0], top_k=1)[0].chunk.document_id == "b"


def test_rejects_zero_vector() -> None:
    with pytest.raises(VectorIndexError):
        VectorIndex(
            vectors=np.array([[0.0, 0.0]]),
            chunks=[chunk("a:01", "a")],
        )
