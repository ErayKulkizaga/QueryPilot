from dataclasses import dataclass
from typing import Protocol

from app.rag.index import VectorIndex


class QueryEmbedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    score: float
    chunk_id: str
    document_id: str
    title: str
    section: str
    text: str
    source_url: str


class Retriever:
    def __init__(self, *, index: VectorIndex, embedder: QueryEmbedder) -> None:
        self._index = index
        self._embedder = embedder

    def retrieve(self, query: str, *, top_k: int = 3) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError("Retrieval query must not be empty.")
        results = self._index.search(self._embedder.embed_query(query), top_k=top_k)
        return [
            RetrievedChunk(
                score=result.score,
                chunk_id=result.chunk.chunk_id,
                document_id=result.chunk.document_id,
                title=result.chunk.title,
                section=result.chunk.section,
                text=result.chunk.text,
                source_url=result.chunk.source_url,
            )
            for result in results
        ]

