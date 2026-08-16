"""Stage 04 example 1: inspect embeddings and cosine similarity without a framework."""

from tiny_agent import HashEmbeddingModel, cosine_similarity


model = HashEmbeddingModel(dimension=64)

query = "qdrant payload filtering"
texts = [
    "qdrant vector database payload filtering",
    "langgraph state nodes edges",
    "faiss local vector index",
]

query_vector = model.embed_query(query)
document_vectors = model.embed_documents(texts)

print(f"query vector dimension: {len(query_vector)}")
print("\nCosine similarities:")
for text, vector in zip(texts, document_vectors):
    print(f"{cosine_similarity(query_vector, vector): .4f}  {text}")

print(
    "\nNote: HashEmbeddingModel is a deterministic lexical teaching model, "
    "not a neural semantic embedding model."
)
