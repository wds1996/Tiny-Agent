"""Compare real optional backends on the SAME policy chunks, vectors and scope."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Sequence
from uuid import NAMESPACE_URL, uuid5

from retrieval import (InMemoryVectorRetriever, Scope, SearchResult, format_evidence,
                       make_demo_corpus, positive_int)


class NeuralEmbeddingModel:
    """Optional local Sentence Transformers weights; never downloads implicitly."""
    def __init__(self, model_path: str) -> None:
        if not Path(model_path).is_dir():
            raise ValueError("Provide an existing local embedding model directory")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_path, device="cpu", local_files_only=True)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self.model.encode_document(list(texts), normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode_query(text, normalize_embeddings=True).tolist()


def faiss_search(index: InMemoryVectorRetriever, query: str, scope: Scope, top_k: int) -> list[SearchResult]:
    positive_int(top_k, "top_k")
    import faiss
    import numpy as np
    eligible = [(chunk, vector) for chunk, vector in zip(index.chunks, index.vectors) if scope.accepts(chunk)]
    if not eligible:
        return []
    matrix = np.ascontiguousarray([vector for _, vector in eligible], dtype="float32")
    query_vector = np.ascontiguousarray([index.embedding.embed_query(query)], dtype="float32")
    if not query_vector.any():
        return []
    faiss.normalize_L2(matrix)
    faiss.normalize_L2(query_vector)
    backend = faiss.IndexFlatIP(matrix.shape[1])
    backend.add(matrix)
    scores, positions = backend.search(query_vector, min(top_k, len(eligible)))
    hits = [SearchResult(eligible[int(pos)][0], float(score))
            for score, pos in zip(scores[0], positions[0]) if pos >= 0 and score > 0]
    index.verify(hits, scope)
    return hits


def qdrant_search(index: InMemoryVectorRetriever, query: str, scope: Scope, top_k: int) -> list[SearchResult]:
    positive_int(top_k, "top_k")
    from qdrant_client import QdrantClient, models
    vector = index.embedding.embed_query(query)
    if not any(vector):
        return []
    client = QdrantClient(":memory:")
    try:
        client.create_collection("policies", vectors_config=models.VectorParams(
            size=len(vector), distance=models.Distance.COSINE))
        client.upsert("policies", points=[models.PointStruct(
            id=str(uuid5(NAMESPACE_URL, chunk.id)), vector=stored,
            payload={"chunk_id": chunk.id, "tenant": chunk.source.tenant,
                     "language": chunk.source.language, "status": chunk.source.status},
        ) for chunk, stored in zip(index.chunks, index.vectors)], wait=True)
        filters = models.Filter(must=[models.FieldCondition(key=key, match=models.MatchValue(value=value))
                    for key, value in {"tenant": scope.tenant, "language": scope.language, "status": "published"}.items()])
        result = client.query_points("policies", query=vector, query_filter=filters,
                                     with_payload=True, limit=top_k)
        hits = [SearchResult(index.by_id[point.payload["chunk_id"]], float(point.score))
                for point in result.points if point.score > 0]
        index.verify(hits, scope)
        return hits
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional exact-search backend comparison on policy evidence.")
    parser.add_argument("--backend", choices=("faiss", "qdrant"), required=True)
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--embedding-model", help="Existing local Sentence Transformers directory (optional)")
    args = parser.parse_args()
    model = NeuralEmbeddingModel(args.embedding_model) if args.embedding_model else None
    index = InMemoryVectorRetriever(make_demo_corpus(), model)
    query = "新订单 原路退款 申请期限" if args.language == "zh-CN" else "new orders original-payment refund window"
    search = faiss_search if args.backend == "faiss" else qdrant_search
    try:
        hits = search(index, query, Scope(language=args.language), 3)
    except ImportError as exc:
        raise SystemExit("Install code/requirements-frameworks.txt; no fallback backend was run") from exc
    print("embedding:", "local neural model" if model else "lexical TF-IDF, not neural")
    print("backend:", args.backend)
    print(format_evidence(hits))


if __name__ == "__main__":
    main()
