"""Stage 04 example 9: tiny deterministic Recall@k / MRR evaluation."""

from tiny_agent import HashEmbeddingModel, InMemoryVectorRetriever

from _demo_support import DEMO_CHUNKS


def recall_at_k(retrieved_ids, relevant_ids, k):
    relevant = set(relevant_ids)
    if not relevant:
        return 1.0
    retrieved = set(retrieved_ids[:k])
    return len(retrieved & relevant) / len(relevant)


def reciprocal_rank(retrieved_ids, relevant_ids):
    relevant = set(relevant_ids)
    for rank, chunk_id in enumerate(retrieved_ids, start=1):
        if chunk_id in relevant:
            return 1.0 / rank
    return 0.0


cases = [
    ("qdrant payload filtering", {"qdrant"}),
    ("langgraph state nodes", {"langgraph"}),
    ("faiss dense vector index", {"faiss"}),
]

retriever = InMemoryVectorRetriever(
    DEMO_CHUNKS,
    HashEmbeddingModel(dimension=256),
)

recalls = []
rrs = []
for query, relevant in cases:
    results = retriever.retrieve(query, top_k=3)
    ids = [item.chunk.id for item in results]
    recalls.append(recall_at_k(ids, relevant, 3))
    rrs.append(reciprocal_rank(ids, relevant))
    print(query, "->", ids)

print(f"Recall@3 = {sum(recalls) / len(recalls):.3f}")
print(f"MRR      = {sum(rrs) / len(rrs):.3f}")
