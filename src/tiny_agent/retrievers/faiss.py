"""FAISS-backed retriever for Stage 04.

FAISS is used here as a local dense-vector index.  The adapter deliberately
keeps document metadata outside the FAISS index so learners can see the
separation between vector search and document storage/metadata policy.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import faiss
import numpy as np

from ..retrieval import DocumentChunk, EmbeddingModel, SearchResult


class FaissRetriever:
    """Exact cosine-similarity search using ``IndexFlatIP`` on normalized vectors."""

    def __init__(
        self,
        chunks: Sequence[DocumentChunk],
        embedding_model: EmbeddingModel,
    ) -> None:
        self._chunks = list(chunks)
        self._embedding_model = embedding_model
        self._index = faiss.IndexFlatIP(embedding_model.dimension)

        if not self._chunks:
            return

        matrix = np.asarray(
            embedding_model.embed_documents([chunk.text for chunk in self._chunks]),
            dtype="float32",
        )
        if matrix.ndim != 2 or matrix.shape != (
            len(self._chunks),
            embedding_model.dimension,
        ):
            raise ValueError("embedding model returned an unexpected matrix shape")

        faiss.normalize_L2(matrix)
        self._index.add(matrix)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if metadata_filter:
            raise NotImplementedError(
                "This teaching FAISS adapter does not implement native metadata filtering. "
                "Use Qdrant or add an application-owned filtering strategy."
            )
        if not self._chunks:
            return []

        query_vector = np.asarray(
            [self._embedding_model.embed_query(query)],
            dtype="float32",
        )
        if query_vector.shape != (1, self._embedding_model.dimension):
            raise ValueError("embedding model returned an unexpected query dimension")
        faiss.normalize_L2(query_vector)

        k = min(top_k, len(self._chunks))
        scores, indices = self._index.search(query_vector, k)

        return [
            SearchResult(chunk=self._chunks[int(index)], score=float(score))
            for score, index in zip(scores[0], indices[0])
            if int(index) >= 0
        ]
