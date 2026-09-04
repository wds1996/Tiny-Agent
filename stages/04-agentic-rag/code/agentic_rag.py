from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

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


@dataclass(slots=True)
class RAGState:
    question: str
    current_query: str = ""
    query_history: list[str] = field(default_factory=list)
    evidence: list[SearchResult] = field(default_factory=list)
    rewrites: int = 0
    status: str = "created"
    answer: str | None = None


class AgenticRAG:
    def __init__(
        self,
        *,
        policy: DecisionPolicy,
        retriever: InMemoryVectorRetriever,
        max_rewrites: int = 1,
    ) -> None:
        if max_rewrites < 0:
            raise ValueError("max_rewrites must be >= 0")
        self._policy = policy
        self._retriever = retriever
        self._max_rewrites = max_rewrites
        self._answerer = EvidenceBoundAnswerer()

    def run(self, question: str, *, top_k: int = 2) -> RAGState:
        state = RAGState(question=question)
        first = self._policy.decide_retrieval(question)

        if not first.retrieve:
            state.status = "direct_answer"
            state.answer = "This request does not require the external corpus."
            return state

        state.current_query = first.query.strip() or question.strip()

        while True:
            if state.current_query in state.query_history:
                state.status = "insufficient_evidence"
                state.answer = "Repeated retrieval query; stopping without a grounded answer."
                return state

            state.query_history.append(state.current_query)
            state.evidence = self._retriever.retrieve(
                state.current_query,
                top_k=top_k,
            )

            assessment = self._policy.assess_evidence(
                question=state.question,
                query=state.current_query,
                evidence=state.evidence,
            )

            if assessment.sufficient and state.evidence:
                state.status = "grounded_answer"
                state.answer = self._answerer.answer(
                    question=state.question,
                    evidence=state.evidence,
                )
                return state

            rewritten = assessment.rewritten_query.strip()
            if state.rewrites >= self._max_rewrites or not rewritten:
                state.status = "insufficient_evidence"
                state.answer = "Not enough retrieved evidence to answer reliably."
                return state

            state.rewrites += 1
            state.current_query = rewritten


def main() -> None:
    policy = ScriptedPolicy(
        retrieval_decision=RetrievalDecision(
            retrieve=True,
            query="database backend",
        ),
        evidence_decisions=[
            EvidenceDecision(
                sufficient=False,
                rewritten_query="qdrant payload metadata filtering",
            ),
            EvidenceDecision(sufficient=True),
        ],
    )

    workflow = AgenticRAG(
        policy=policy,
        retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
        max_rewrites=1,
    )
    state = workflow.run("Which backend supports payload metadata filtering?")

    print("status:", state.status)
    print("queries:", state.query_history)
    print("rewrites:", state.rewrites)
    print("answer:", state.answer)


if __name__ == "__main__":
    main()
