import numpy as np

from app.rag.chunker import KnowledgeChunk
from app.rag.index import VectorIndex
from app.rag.retriever import Retriever


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        if "sort" in text:
            return [0.0, 1.0]
        return [1.0, 0.0]


def make_chunk(document_id: str, text: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=f"{document_id}:section:01",
        document_id=document_id,
        title=document_id,
        section="Section",
        text=text,
        source_path=f"{document_id}.md",
        source_url=f"https://example.test/{document_id}",
    )


def test_retriever_maps_search_results_to_citation_metadata() -> None:
    index = VectorIndex(
        vectors=np.array([[1.0, 0.0], [0.0, 1.0]]),
        chunks=[
            make_chunk("pg-indexes-01", "Selective predicates"),
            make_chunk("pg-sorting-01", "Disk sort"),
        ],
    )
    retriever = Retriever(index=index, embedder=FakeEmbedder())

    result = retriever.retrieve("external sort uses disk", top_k=1)[0]

    assert result.document_id == "pg-sorting-01"
    assert result.section == "Section"
    assert result.source_url.endswith("/pg-sorting-01")

