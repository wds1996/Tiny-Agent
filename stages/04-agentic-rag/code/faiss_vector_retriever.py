"""Stage 04 example 2: use FAISS as a local dense-vector index."""

from tiny_agent import HashEmbeddingModel
from tiny_agent.retrievers.faiss import FaissRetriever

from _demo_support import DEMO_CHUNKS


retriever = FaissRetriever(
    DEMO_CHUNKS,
    HashEmbeddingModel(dimension=256),
)

for result in retriever.retrieve("local dense vector similarity index", top_k=3):
    print(f"{result.score: .4f}  {result.chunk.id}: {result.chunk.text}")

print(
    "\nFAISS returned vector positions; Tiny-Agent mapped those positions back "
    "to DocumentChunk objects."
)
