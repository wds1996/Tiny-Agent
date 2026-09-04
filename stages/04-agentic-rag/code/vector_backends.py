from __future__ import annotations

import uuid

import numpy as np

from retrieval import HashEmbeddingModel, make_demo_corpus


def faiss_demo() -> None:
    try:
        import faiss
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 04 dependencies first:\n"
            "python -m pip install -r "
            "stages/04-agentic-rag/code/requirements.txt"
        ) from exc

    chunks = make_demo_corpus()
    embedding = HashEmbeddingModel()
    matrix = np.asarray(
        embedding.embed_documents([chunk.text for chunk in chunks]),
        dtype="float32",
    )
    faiss.normalize_L2(matrix)

    index = faiss.IndexFlatIP(embedding.dimension)
    index.add(matrix)

    query = np.asarray(
        [embedding.embed_query("faiss vector similarity index")],
        dtype="float32",
    )
    faiss.normalize_L2(query)
    scores, indices = index.search(query, 2)

    print("=== FAISS ===")
    for score, position in zip(scores[0], indices[0]):
        chunk = chunks[int(position)]
        print(f"{chunk.id:12} score={float(score):.4f}")


def qdrant_demo() -> None:
    try:
        from qdrant_client import QdrantClient, models
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 04 dependencies first:\n"
            "python -m pip install -r "
            "stages/04-agentic-rag/code/requirements.txt"
        ) from exc

    chunks = make_demo_corpus()
    embedding = HashEmbeddingModel()
    client = QdrantClient(":memory:")
    collection = "tiny_agent_stage04"

    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(
            size=embedding.dimension,
            distance=models.Distance.COSINE,
        ),
    )

    vectors = embedding.embed_documents([chunk.text for chunk in chunks])
    client.upsert(
        collection_name=collection,
        points=[
            models.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"stage04:{chunk.id}")),
                vector=vector,
                payload={
                    "chunk_id": chunk.id,
                    "text": chunk.text,
                    **dict(chunk.metadata),
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ],
    )

    response = client.query_points(
        collection_name=collection,
        query=embedding.embed_query("payload metadata filtering"),
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="kind",
                    match=models.MatchValue(value="vector-database"),
                )
            ]
        ),
        with_payload=True,
        limit=2,
    )

    print("\n=== Qdrant with payload filter ===")
    for point in response.points:
        payload = dict(point.payload or {})
        print(f"{payload['chunk_id']:12} score={float(point.score):.4f}")


def main() -> None:
    faiss_demo()
    qdrant_demo()


if __name__ == "__main__":
    main()
