"""Qdrant-backed retriever for Stage 04.

The adapter can use Qdrant Client local mode (``QdrantClient(':memory:')``) for
teaching/tests or a remote client configured by the application.  Qdrant owns
vector storage, payloads, and payload filtering; Tiny-Agent still owns the
embedding model and the retrieval policy.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence
import uuid

from qdrant_client import QdrantClient, models

from ..retrieval import DocumentChunk, EmbeddingModel, SearchResult


class QdrantRetriever:
    def __init__(
        self,
        *,
        client: QdrantClient,
        collection_name: str,
        embedding_model: EmbeddingModel,
    ) -> None:
        self._client = client
        self._collection_name = collection_name
        self._embedding_model = embedding_model

    @classmethod
    def from_chunks(
        cls,
        chunks: Sequence[DocumentChunk],
        *,
        client: QdrantClient,
        collection_name: str,
        embedding_model: EmbeddingModel,
    ) -> "QdrantRetriever":
        if not client.collection_exists(collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_model.dimension,
                    distance=models.Distance.COSINE,
                ),
            )

        vectors = embedding_model.embed_documents([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise ValueError("embedding model returned an unexpected vector count")

        points: list[models.PointStruct] = []
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != embedding_model.dimension:
                raise ValueError("embedding model returned an unexpected dimension")
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"tiny-agent:{chunk.id}"))
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "_chunk_id": chunk.id,
                        "_text": chunk.text,
                        **dict(chunk.metadata),
                    },
                )
            )

        if points:
            client.upsert(collection_name=collection_name, points=points)

        return cls(
            client=client,
            collection_name=collection_name,
            embedding_model=embedding_model,
        )

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        metadata_filter: Mapping[str, Any] | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        query_filter = None
        if metadata_filter:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                    for key, value in metadata_filter.items()
                ]
            )

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=self._embedding_model.embed_query(query),
            query_filter=query_filter,
            with_payload=True,
            limit=top_k,
        )

        results: list[SearchResult] = []
        for point in response.points:
            payload = dict(point.payload or {})
            chunk_id = str(payload.pop("_chunk_id", point.id))
            text = str(payload.pop("_text", ""))
            results.append(
                SearchResult(
                    chunk=DocumentChunk(
                        id=chunk_id,
                        text=text,
                        metadata=payload,
                    ),
                    score=float(point.score),
                )
            )
        return results
