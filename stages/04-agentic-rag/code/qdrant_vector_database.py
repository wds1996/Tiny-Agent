"""Stage 04 example 3: Qdrant local mode with payload filtering."""

from qdrant_client import QdrantClient

from tiny_agent import HashEmbeddingModel
from tiny_agent.retrievers.qdrant import QdrantRetriever

from _demo_support import DEMO_CHUNKS


client = QdrantClient(":memory:")
retriever = QdrantRetriever.from_chunks(
    DEMO_CHUNKS,
    client=client,
    collection_name="tiny_agent_demo",
    embedding_model=HashEmbeddingModel(dimension=256),
)

print("Only kind=database is allowed by the application filter:\n")
for result in retriever.retrieve(
    "vector payload filtering",
    top_k=4,
    metadata_filter={"kind": "database"},
):
    print(result.chunk.id, result.chunk.metadata, f"score={result.score:.4f}")
