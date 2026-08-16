from __future__ import annotations

from typing import Any, Sequence

from tiny_agent import DocumentChunk, SearchResult


DEMO_CHUNKS = [
    DocumentChunk(
        "faiss",
        "FAISS is a library for efficient dense vector similarity search. "
        "A local IndexFlatIP can perform exact inner-product search.",
        {"source": "faiss-notes", "kind": "local"},
    ),
    DocumentChunk(
        "qdrant",
        "Qdrant is a vector database that stores vectors with JSON payloads. "
        "Payload fields can participate in metadata filtering.",
        {"source": "qdrant-notes", "kind": "database"},
    ),
    DocumentChunk(
        "langchain",
        "A LangChain Retriever accepts an unstructured query and returns Documents. "
        "A Retriever is more general than a vector store.",
        {"source": "langchain-notes", "kind": "framework"},
    ),
    DocumentChunk(
        "langgraph",
        "LangGraph is a low-level runtime for explicit stateful orchestration with "
        "nodes, edges, persistence, streaming, and interrupts.",
        {"source": "langgraph-notes", "kind": "framework"},
    ),
]


class EvidenceEchoAnswerer:
    """Deterministic demo answerer: shows exactly which evidence reached generation."""

    def answer(self, *, question: str, evidence: Sequence[SearchResult]) -> str:
        if not evidence:
            return f"Direct demo answer for: {question}"
        sources = ", ".join(item.chunk.id for item in evidence)
        return f"Answer grounded on [{sources}]: {evidence[0].chunk.text}"


class ScriptedDecisionModel:
    """Fake structured-decision model for deterministic Agentic-RAG demos."""

    def __init__(self, decisions: list[dict[str, Any]]) -> None:
        self._decisions = list(decisions)

    def decide(
        self,
        *,
        prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str | None = None,
    ) -> dict[str, Any]:
        del prompt, schema_name, schema, instructions
        if not self._decisions:
            raise RuntimeError("No scripted decision remains")
        return self._decisions.pop(0)
