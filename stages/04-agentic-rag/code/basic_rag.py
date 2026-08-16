"""Stage 04 example 6: deterministic two-step RAG."""

from tiny_agent import BasicRAG, HashEmbeddingModel, InMemoryVectorRetriever

from _demo_support import DEMO_CHUNKS, EvidenceEchoAnswerer


retriever = InMemoryVectorRetriever(
    DEMO_CHUNKS,
    HashEmbeddingModel(dimension=256),
)
rag = BasicRAG(retriever, EvidenceEchoAnswerer())

result = rag.run("Which system supports payload filtering?", top_k=2)

print("status:", result.status)
print("evidence:", [item.chunk.id for item in result.evidence])
print("answer:", result.answer)
