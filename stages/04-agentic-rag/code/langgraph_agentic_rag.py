from __future__ import annotations

from dataclasses import dataclass
from operator import add
from typing import Annotated, Literal, Protocol, Sequence

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from basic_rag import EvidenceBoundAnswerer
from retrieval import (
    HashEmbeddingModel,
    InMemoryVectorRetriever,
    SearchResult,
    make_demo_corpus,
)


@dataclass(frozen=True, slots=True)
class RetrievalDecision:
    retrieve: bool
    query: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    sufficient: bool
    rewritten_query: str = ""


class DecisionPolicy(Protocol):
    """Provide structured decisions; the graph retains control of transitions."""

    def decide_retrieval(self, question: str) -> RetrievalDecision:
        ...

    def assess_evidence(
        self,
        *,
        question: str,
        query: str,
        evidence: Sequence[SearchResult],
    ) -> EvidenceDecision:
        ...


class ScriptedPolicy:
    """Deterministic stand-in for model-generated structured decisions."""

    def __init__(
        self,
        *,
        retrieval_decision: RetrievalDecision,
        evidence_decisions: Sequence[EvidenceDecision],
    ) -> None:
        self._retrieval_decision = retrieval_decision
        self._evidence_decisions = list(evidence_decisions)

    def decide_retrieval(self, question: str) -> RetrievalDecision:
        del question
        return self._retrieval_decision

    def assess_evidence(
        self,
        *,
        question: str,
        query: str,
        evidence: Sequence[SearchResult],
    ) -> EvidenceDecision:
        del question, query, evidence
        if not self._evidence_decisions:
            raise RuntimeError("No scripted evidence decision remains.")
        return self._evidence_decisions.pop(0)


class RAGGraphState(TypedDict, total=False):
    question: str
    current_query: str
    query_history: Annotated[list[str], add]
    evidence: list[SearchResult]
    rewrites: int
    status: str
    answer: str | None


def build_graph(
    *,
    policy: DecisionPolicy,
    retriever: InMemoryVectorRetriever,
    max_rewrites: int = 1,
    top_k: int = 2,
):
    """Build the same bounded retrieval loop as agentic_rag.py using LangGraph."""

    if max_rewrites < 0:
        raise ValueError("max_rewrites must be >= 0")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    answerer = EvidenceBoundAnswerer()

    def decide_retrieval(state: RAGGraphState) -> dict:
        decision = policy.decide_retrieval(state["question"])
        if not decision.retrieve:
            return {
                "status": "direct_answer",
                "answer": "This request does not require the external corpus.",
            }
        return {"current_query": decision.query.strip() or state["question"].strip()}

    def route_after_decision(state: RAGGraphState) -> Literal["retrieve", "end"]:
        return "end" if state.get("status") == "direct_answer" else "retrieve"

    def retrieve(state: RAGGraphState) -> dict:
        query = state["current_query"]
        if query in state.get("query_history", []):
            return {
                "status": "insufficient_evidence",
                "answer": "Repeated retrieval query; stopping without a grounded answer.",
            }
        return {
            "query_history": [query],
            "evidence": retriever.retrieve(query, top_k=top_k),
        }

    def route_after_retrieval(state: RAGGraphState) -> Literal["assess", "end"]:
        return "end" if state.get("status") == "insufficient_evidence" else "assess"

    def assess_evidence(state: RAGGraphState) -> dict:
        evidence = state.get("evidence", [])
        assessment = policy.assess_evidence(
            question=state["question"],
            query=state["current_query"],
            evidence=evidence,
        )
        if assessment.sufficient and evidence:
            return {
                "status": "grounded_answer",
                "answer": answerer.answer(
                    question=state["question"],
                    evidence=evidence,
                ),
            }

        rewritten = assessment.rewritten_query.strip()
        if state.get("rewrites", 0) >= max_rewrites or not rewritten:
            return {
                "status": "insufficient_evidence",
                "answer": "Not enough retrieved evidence to answer reliably.",
            }
        return {
            "current_query": rewritten,
            "rewrites": state.get("rewrites", 0) + 1,
        }

    def route_after_assessment(state: RAGGraphState) -> Literal["retrieve", "end"]:
        return "end" if state.get("status") in {
            "grounded_answer",
            "insufficient_evidence",
        } else "retrieve"

    builder = StateGraph(RAGGraphState)
    builder.add_node("decide_retrieval", decide_retrieval)
    builder.add_node("retrieve", retrieve)
    builder.add_node("assess_evidence", assess_evidence)
    builder.add_edge(START, "decide_retrieval")
    builder.add_conditional_edges(
        "decide_retrieval",
        route_after_decision,
        {"retrieve": "retrieve", "end": END},
    )
    builder.add_conditional_edges(
        "retrieve",
        route_after_retrieval,
        {"assess": "assess_evidence", "end": END},
    )
    builder.add_conditional_edges(
        "assess_evidence",
        route_after_assessment,
        {"retrieve": "retrieve", "end": END},
    )
    return builder.compile()


def initial_state(question: str) -> RAGGraphState:
    return {
        "question": question,
        "query_history": [],
        "rewrites": 0,
        "status": "created",
        "answer": None,
    }


def make_demo_graph():
    policy = ScriptedPolicy(
        retrieval_decision=RetrievalDecision(True, "database backend"),
        evidence_decisions=[
            EvidenceDecision(False, "qdrant payload metadata filtering"),
            EvidenceDecision(True),
        ],
    )
    return build_graph(
        policy=policy,
        retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
        max_rewrites=1,
    )


def main() -> None:
    question = "Which backend supports payload metadata filtering?"

    print("=== node updates ===")
    for update in make_demo_graph().stream(
        initial_state(question),
        stream_mode="updates",
        config={"recursion_limit": 10},
    ):
        print(update)

    result = make_demo_graph().invoke(
        initial_state(question),
        config={"recursion_limit": 10},
    )
    print("\n=== final state ===")
    print("status:", result["status"])
    print("queries:", result["query_history"])
    print("rewrites:", result["rewrites"])
    print("answer:", result["answer"])


if __name__ == "__main__":
    main()
