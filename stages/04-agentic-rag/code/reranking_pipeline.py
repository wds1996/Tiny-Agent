"""Stage 04 example 5: retrieve broadly, then apply a transparent reranker."""

from tiny_agent import HashEmbeddingModel, InMemoryVectorRetriever, tokenize

from _demo_support import DEMO_CHUNKS


def lexical_overlap(query: str, text: str) -> int:
    return len(set(tokenize(query)) & set(tokenize(text)))


query = "qdrant metadata payload filtering"
retriever = InMemoryVectorRetriever(
    DEMO_CHUNKS,
    HashEmbeddingModel(dimension=256),
)

candidates = retriever.retrieve(query, top_k=4)

print("Initial vector ranking:")
for item in candidates:
    print(f"{item.score: .4f}  {item.chunk.id}")

reranked = sorted(
    candidates,
    key=lambda item: (
        -lexical_overlap(query, item.chunk.text),
        -item.score,
        item.chunk.id,
    ),
)

print("\nAfter transparent lexical reranking:")
for item in reranked:
    print(
        f"overlap={lexical_overlap(query, item.chunk.text)} "
        f"vector={item.score:.4f}  {item.chunk.id}"
    )

print("\nToy reranker only: production rerankers should be evaluated on your task.")
