import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.rag.chunker import KnowledgeChunk


class VectorIndexError(ValueError):
    """Raised when vector data and chunk metadata are inconsistent."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    score: float
    chunk: KnowledgeChunk


class VectorIndex:
    def __init__(
        self,
        *,
        vectors: NDArray[np.floating],
        chunks: list[KnowledgeChunk],
    ) -> None:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
            raise VectorIndexError("Vector matrix must be non-empty and two-dimensional.")
        if matrix.shape[0] != len(chunks):
            raise VectorIndexError("Vector count must match chunk metadata count.")
        if not np.isfinite(matrix).all():
            raise VectorIndexError("Vector matrix contains non-finite values.")

        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise VectorIndexError("Zero-length embeddings are not indexable.")
        self._vectors = matrix / norms
        self._chunks = tuple(chunks)

    @property
    def dimensions(self) -> int:
        return int(self._vectors.shape[1])

    @property
    def size(self) -> int:
        return len(self._chunks)

    def search(self, query_vector: list[float], *, top_k: int = 3) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be at least one.")
        query = np.asarray(query_vector, dtype=np.float32)
        if query.ndim != 1 or query.shape[0] != self.dimensions:
            raise VectorIndexError(
                f"Query embedding must have exactly {self.dimensions} dimensions."
            )
        norm = np.linalg.norm(query)
        if not np.isfinite(query).all() or norm == 0:
            raise VectorIndexError("Query embedding must be finite and non-zero.")

        scores = self._vectors @ (query / norm)
        result_count = min(top_k, self.size)
        indices = np.argsort(-scores, kind="stable")[:result_count]
        return [
            SearchResult(score=float(scores[index]), chunk=self._chunks[int(index)])
            for index in indices
        ]

    def save(self, *, vectors_path: Path, metadata_path: Path) -> None:
        vectors_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(vectors_path, vectors=self._vectors)
        metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "dimensions": self.dimensions,
                    "chunks": [chunk.to_dict() for chunk in self._chunks],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, *, vectors_path: Path, metadata_path: Path) -> "VectorIndex":
        with np.load(vectors_path, allow_pickle=False) as archive:
            if "vectors" not in archive:
                raise VectorIndexError("NPZ index does not contain a vectors array.")
            vectors = archive["vectors"]
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("schema_version") != 1:
            raise VectorIndexError("Unsupported metadata schema version.")
        chunks = [KnowledgeChunk(**item) for item in metadata.get("chunks", [])]
        index = cls(vectors=vectors, chunks=chunks)
        if metadata.get("dimensions") != index.dimensions:
            raise VectorIndexError("Metadata dimension does not match vector data.")
        return index

