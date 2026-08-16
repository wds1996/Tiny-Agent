import pytest
from qdrant_client import QdrantClient

from tiny_agent import DocumentChunk, HashEmbeddingModel, InMemoryVectorRetriever
from tiny_agent.retrievers.faiss import FaissRetriever
from tiny_agent.retrievers.langchain_adapter import TinyAgentLangChainRetriever
from tiny_agent.retrievers.qdrant import QdrantRetriever


@pytest.fixture
def chunks():
    return [
        DocumentChunk("faiss", "faiss dense vector local index", {"kind": "local"}),
        DocumentChunk(
            "qdrant",
            "qdrant vector database payload filtering",
            {"kind": "database"},
        ),
        DocumentChunk("graph", "langgraph nodes state edges", {"kind": "orchestration"}),
    ]


@pytest.fixture
def embedding_model():
    return HashEmbeddingModel(dimension=512)


def test_faiss_retriever_returns_expected_nearest_chunk(chunks, embedding_model):
    retriever = FaissRetriever(chunks, embedding_model)

    result = retriever.retrieve("faiss local index", top_k=1)

    assert result[0].chunk.id == "faiss"


def test_faiss_teaching_adapter_does_not_fake_native_metadata_filtering(
    chunks,
    embedding_model,
):
    retriever = FaissRetriever(chunks, embedding_model)

    with pytest.raises(NotImplementedError):
        retriever.retrieve("vector", metadata_filter={"kind": "local"})


def test_qdrant_local_mode_supports_vector_search_and_payload_filter(
    chunks,
    embedding_model,
):
    client = QdrantClient(":memory:")
    retriever = QdrantRetriever.from_chunks(
        chunks,
        client=client,
        collection_name="tiny_agent_test",
        embedding_model=embedding_model,
    )

    result = retriever.retrieve(
        "vector",
        top_k=3,
        metadata_filter={"kind": "database"},
    )

    assert [item.chunk.id for item in result] == ["qdrant"]
    assert result[0].chunk.metadata["kind"] == "database"


def test_langchain_adapter_exposes_tiny_agent_results_as_documents(
    chunks,
    embedding_model,
):
    base = InMemoryVectorRetriever(chunks, embedding_model)
    retriever = TinyAgentLangChainRetriever(retriever=base, top_k=1)

    documents = retriever.invoke("qdrant filtering")

    assert documents[0].metadata["chunk_id"] == "qdrant"
    assert "retrieval_score" in documents[0].metadata
    assert "qdrant" in documents[0].page_content
