import pytest

from tiny_agent import (
    DocumentChunk,
    HashEmbeddingModel,
    InMemoryVectorRetriever,
    chunk_text,
    cosine_similarity,
)


def test_chunk_text_preserves_overlap_and_metadata():
    chunks = chunk_text(
        "one two three four five six seven",
        document_id="doc",
        chunk_size=4,
        overlap=2,
        metadata={"source": "notes"},
    )

    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "three four five six",
        "five six seven",
    ]
    assert chunks[1].metadata["source"] == "notes"
    assert chunks[1].metadata["start_token"] == 2


def test_chunk_text_rejects_invalid_overlap():
    with pytest.raises(ValueError):
        chunk_text("hello", document_id="doc", chunk_size=4, overlap=4)


def test_cosine_similarity_has_expected_extremes():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_hash_embedding_is_deterministic_and_normalized():
    model = HashEmbeddingModel(dimension=256)
    left = model.embed_query("agent retrieval agent")
    right = model.embed_query("agent retrieval agent")

    assert left == right
    assert sum(value * value for value in left) == pytest.approx(1.0)


def test_in_memory_retriever_ranks_shared_terms_first():
    chunks = [
        DocumentChunk("a", "langgraph state nodes edges", {"topic": "agent"}),
        DocumentChunk("b", "qdrant vector payload filtering", {"topic": "rag"}),
        DocumentChunk("c", "docker container deployment", {"topic": "ops"}),
    ]
    retriever = InMemoryVectorRetriever(chunks, HashEmbeddingModel(dimension=512))

    result = retriever.retrieve("qdrant payload", top_k=1)

    assert result[0].chunk.id == "b"


def test_in_memory_retriever_applies_metadata_filter_before_ranking():
    chunks = [
        DocumentChunk("a", "vector search qdrant", {"language": "en"}),
        DocumentChunk("b", "vector search qdrant", {"language": "zh"}),
    ]
    retriever = InMemoryVectorRetriever(chunks, HashEmbeddingModel(dimension=512))

    result = retriever.retrieve(
        "vector search",
        top_k=5,
        metadata_filter={"language": "zh"},
    )

    assert [item.chunk.id for item in result] == ["b"]
