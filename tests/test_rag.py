from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from tiny_agent import (
    AgenticRAGWorkflow,
    BasicRAG,
    DocumentChunk,
    HashEmbeddingModel,
    InMemoryVectorRetriever,
    SearchResult,
)


@dataclass
class RecordingAnswerer:
    calls: list[tuple[str, tuple[str, ...]]]

    def answer(self, *, question: str, evidence: Sequence[SearchResult]) -> str:
        ids = tuple(item.chunk.id for item in evidence)
        self.calls.append((question, ids))
        if evidence:
            return f"grounded:{','.join(ids)}"
        return "direct"


class ScriptedDecisionModel:
    def __init__(self, decisions: list[dict[str, Any]]) -> None:
        self._decisions = list(decisions)
        self.calls: list[str] = []

    def decide(
        self,
        *,
        prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        instructions: str | None = None,
    ) -> dict[str, Any]:
        del schema, instructions
        self.calls.append(schema_name)
        if not self._decisions:
            raise AssertionError("unexpected structured-decision call")
        return self._decisions.pop(0)


def make_retriever() -> InMemoryVectorRetriever:
    chunks = [
        DocumentChunk("faiss", "faiss local dense vector similarity index"),
        DocumentChunk("qdrant", "qdrant payload metadata filtering vector database"),
        DocumentChunk("langgraph", "langgraph state nodes edges orchestration"),
    ]
    return InMemoryVectorRetriever(chunks, HashEmbeddingModel(dimension=512))


def test_basic_rag_always_retrieves_before_answering():
    answerer = RecordingAnswerer([])
    rag = BasicRAG(make_retriever(), answerer)

    result = rag.run("qdrant filtering", top_k=1)

    assert result.status == "grounded_answer"
    assert result.evidence[0].chunk.id == "qdrant"
    assert answerer.calls == [("qdrant filtering", ("qdrant",))]


def test_agentic_rag_can_skip_retrieval_for_simple_conversation():
    decision_model = ScriptedDecisionModel(
        [{"retrieve": False, "query": ""}]
    )
    answerer = RecordingAnswerer([])
    workflow = AgenticRAGWorkflow(
        decision_model=decision_model,
        retriever=make_retriever(),
        answer_generator=answerer,
    )

    result = workflow.run("Say hello")

    assert result.status == "direct_answer"
    assert result.query_history == ()
    assert decision_model.calls == ["retrieval_decision"]
    assert answerer.calls == [("Say hello", ())]


def test_agentic_rag_rewrites_once_then_answers_from_new_evidence():
    decision_model = ScriptedDecisionModel(
        [
            {"retrieve": True, "query": "vector store"},
            {"sufficient": False, "rewritten_query": "qdrant payload filtering"},
            {"sufficient": True, "rewritten_query": ""},
        ]
    )
    answerer = RecordingAnswerer([])
    workflow = AgenticRAGWorkflow(
        decision_model=decision_model,
        retriever=make_retriever(),
        answer_generator=answerer,
        max_rewrites=1,
    )

    result = workflow.run("Which backend supports payload filtering?", top_k=1)

    assert result.status == "grounded_answer"
    assert result.query_history == ("vector store", "qdrant payload filtering")
    assert result.evidence[0].chunk.id == "qdrant"
    assert answerer.calls[-1][1] == ("qdrant",)


def test_agentic_rag_abstains_when_evidence_stays_insufficient():
    decision_model = ScriptedDecisionModel(
        [
            {"retrieve": True, "query": "unknown topic"},
            {"sufficient": False, "rewritten_query": "still unknown"},
            {"sufficient": False, "rewritten_query": "third try is not allowed"},
        ]
    )
    answerer = RecordingAnswerer([])
    workflow = AgenticRAGWorkflow(
        decision_model=decision_model,
        retriever=make_retriever(),
        answer_generator=answerer,
        max_rewrites=1,
    )

    result = workflow.run("What is absent from this corpus?", top_k=1)

    assert result.status == "insufficient_evidence"
    assert result.query_history == ("unknown topic", "still unknown")
    assert "not have enough retrieved evidence" in result.answer
    assert answerer.calls == []


def test_agentic_rag_rejects_malformed_control_decisions():
    decision_model = ScriptedDecisionModel(
        [{"retrieve": "yes", "query": "qdrant"}]
    )
    workflow = AgenticRAGWorkflow(
        decision_model=decision_model,
        retriever=make_retriever(),
        answer_generator=RecordingAnswerer([]),
    )

    try:
        workflow.run("Need retrieval")
    except ValueError as exc:
        assert str(exc) == "invalid retrieval decision"
    else:
        raise AssertionError("expected malformed decision to be rejected")
