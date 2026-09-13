"""A bounded evidence-search loop with the same nodes used by LangGraph."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from typing import Any, Sequence, TypedDict
import unicodedata

from basic_rag import (AnswerDraft, AnswerGenerator, ChecklistPolicy, DecisionPolicy,
                       EvidenceDecision, ExtractiveAnswerer, RAGTask, approved_evidence,
                       demo_parser, pack_evidence, sample_task, validate_answer)
from retrieval import (InMemoryVectorRetriever, SearchResult, format_evidence,
                       lexical_rerank, make_demo_corpus, positive_int)


class RAGState(TypedDict):
    task: RAGTask
    query: str
    query_history: list[str]
    evidence: list[SearchResult]
    selected: tuple[SearchResult, ...]
    assessment: EvidenceDecision | None
    searches: int
    rewrites: int
    status: str
    reason: str
    answer: AnswerDraft | None
    answer_kind: str
    events: list[str]
    next_node: str


def query_key(query: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", query).casefold().split())


def initial_state(task: RAGTask, initial_query: str | None = None) -> RAGState:
    query = task.question if initial_query is None else initial_query
    if not isinstance(query, str) or not query.strip() or len(query) > 1500:
        raise ValueError("Initial query must contain 1..1500 characters")
    return dict(task=task, query=query, query_history=[], evidence=[], selected=(),
                assessment=None, searches=0, rewrites=0, status="running", reason="",
                answer=None, answer_kind="none", events=[], next_node="prepare")


def apply_update(state: RAGState, update: dict[str, Any]) -> RAGState:
    result = dict(state)
    for key, value in update.items():
        result[key] = state[key] + value if key in {"events", "query_history"} else value
    return result


class RAGNodes:
    def __init__(self, retriever: InMemoryVectorRetriever, *,
                 policy: DecisionPolicy | None = None, answerer: AnswerGenerator | None = None,
                 top_k: int = 1, candidate_k: int = 6, max_rewrites: int = 1,
                 max_evidence_chars: int = 6000) -> None:
        positive_int(top_k, "top_k")
        positive_int(candidate_k, "candidate_k")
        positive_int(max_evidence_chars, "max_evidence_chars")
        if top_k > candidate_k or type(max_rewrites) is not int or not 0 <= max_rewrites <= 5:
            raise ValueError("Invalid candidate or rewrite budget")
        self.retriever = retriever
        self.policy = policy or ChecklistPolicy()
        self.answerer = answerer or ExtractiveAnswerer()
        self.top_k, self.candidate_k = top_k, candidate_k
        self.max_rewrites, self.max_evidence_chars = max_rewrites, max_evidence_chars

    def stop(self, status: str, reason: str, **extra: Any) -> dict[str, Any]:
        return dict(status=status, reason=reason, next_node="end", answer=None,
                    answer_kind="none", events=[f"stop: {status}: {reason}"], **extra)

    def prepare(self, state: RAGState) -> dict[str, Any]:
        if state["task"].greeting:
            greeting = "你好，请告诉我想查的政策。" if state["task"].scope.language == "zh-CN" else "Hello. Which policy would you like to check?"
            return self.stop("direct", greeting)
        return dict(next_node="search", events=["prepare: policy evidence required"])

    def search(self, state: RAGState) -> dict[str, Any]:
        query = state["query"]
        if query_key(query) in {query_key(old) for old in state["query_history"]}:
            return self.stop("insufficient_evidence", "Repeated query")
        if state["searches"] >= self.max_rewrites + 1:
            return self.stop("insufficient_evidence", "Search budget exhausted")
        common = dict(searches=state["searches"] + 1, query_history=[query])
        try:
            candidates = self.retriever.retrieve(query, scope=state["task"].scope, top_k=self.candidate_k)
            self.retriever.verify(candidates, state["task"].scope)
            chosen = lexical_rerank(query, candidates, top_k=self.top_k)
            evidence = pack_evidence([*state["evidence"], *chosen],
                                     max_chars=self.max_evidence_chars, max_items=8)
            ids = ", ".join(hit.chunk.id for hit in chosen) or "none"
            return dict(**common, evidence=list(evidence), assessment=None, selected=(),
                        next_node="assess", events=[f"search: {ids}; retained={len(evidence)}"])
        except Exception as exc:
            return self.stop("failed", f"Retrieval failed: {type(exc).__name__}", **common)

    def assess(self, state: RAGState) -> dict[str, Any]:
        task = state["task"]
        try:
            self.retriever.verify(state["evidence"], task.scope)
            decision = self.policy.assess(task, state["query"], tuple(state["evidence"]))
            if not isinstance(decision, EvidenceDecision):
                raise ValueError("Policy did not return EvidenceDecision")
            if decision.sufficient:
                selected = approved_evidence(task, decision, state["evidence"])
                return dict(assessment=decision, selected=selected, next_node="answer",
                            events=["assess: selected evidence passed source/checklist checks"])
            query = decision.rewritten_query.strip()
            if state["rewrites"] >= self.max_rewrites or not query:
                return self.stop("insufficient_evidence", decision.reason, assessment=decision)
            if query_key(query) in {query_key(old) for old in state["query_history"]}:
                return self.stop("insufficient_evidence", "Repeated query", assessment=decision)
            return dict(assessment=decision, query=query, rewrites=state["rewrites"] + 1,
                        next_node="search", events=[f"rewrite: {decision.reason}"])
        except Exception as exc:
            return self.stop("failed", f"Assessment failed: {type(exc).__name__}")

    def answer(self, state: RAGState) -> dict[str, Any]:
        try:
            # Recheck the actual selected bundle at the generation boundary.
            self.retriever.verify(state["selected"], state["task"].scope)
            selected = approved_evidence(state["task"], state["assessment"], state["selected"])
            answer = self.answerer.answer(state["task"], selected)
            validate_answer(answer, selected)
            return dict(answer=answer, answer_kind=self.answerer.kind, status="answered",
                        next_node="end", reason="Citation contract checked",
                        events=["answer: generated from selected bundle; citations checked"])
        except Exception as exc:
            return self.stop("failed", f"Answer failed: {type(exc).__name__}")


class AgenticRAG:
    def __init__(self, nodes: RAGNodes) -> None:
        self.nodes = nodes

    def run(self, task: RAGTask, *, initial_query: str | None = None) -> RAGState:
        state = initial_state(task, initial_query)
        handlers = {name: getattr(self.nodes, name) for name in ("prepare", "search", "assess", "answer")}
        while state["next_node"] != "end":
            update = handlers[state["next_node"]](deepcopy(state))
            state = apply_update(state, update)
        return state


def print_result(state: RAGState, *, show_evidence: bool = False) -> None:
    print("status:", state["status"], "answer_kind:", state["answer_kind"])
    print("searches:", state["searches"], "rewrites:", state["rewrites"])
    for query in state["query_history"]:
        print("query:", query)
    for event in state["events"]:
        print(event)
    print("answer:", state["answer"].text if state["answer"] else state["reason"])
    if state["answer"]:
        print("cited IDs:", [citation.evidence_id for citation in state["answer"].citations])
    if show_evidence:
        print(format_evidence(state["evidence"]))


def main(*, engine: str = "python", live: bool = False) -> None:
    parser = demo_parser("Bounded policy evidence search: one case, two possible searches.")
    parser.set_defaults(top_k=1)
    parser.add_argument("--initial-query", default=None)
    parser.add_argument("--max-rewrites", type=int, default=1)
    parser.add_argument("--max-evidence-chars", type=int, default=6000)
    args = parser.parse_args()
    with ExitStack() as cleanup:
        task = sample_task(args.case, args.language)
        policy, answerer = ChecklistPolicy(), ExtractiveAnswerer()
        if live:
            from deepseek_rag import DeepSeekComponents, StructuredClient, create_client, required_env
            model_id = required_env("DEEPSEEK_MODEL")
            client = create_client()
            cleanup.callback(client.close)
            model = StructuredClient(client, model=model_id,
                                     max_calls=args.max_rewrites + 2)
            policy = answerer = DeepSeekComponents(model)
            print("mode: live DeepSeek; API usage applies; no fallback")
        else:
            print("mode: offline checklist + excerpts; model calls: 0")
        nodes = RAGNodes(InMemoryVectorRetriever(make_demo_corpus()), policy=policy, answerer=answerer,
                         top_k=args.top_k, max_rewrites=args.max_rewrites,
                         max_evidence_chars=args.max_evidence_chars)
        if engine == "python":
            state = AgenticRAG(nodes).run(task, initial_query=args.initial_query)
        else:
            from langgraph_agentic_rag import build_graph
            graph = build_graph(nodes)
            state = None
            # One execution, not stream followed by a second invoke.
            for state in graph.stream(initial_state(task, args.initial_query), stream_mode="values",
                                      config={"recursion_limit": 30}):
                print("graph position:", state["next_node"], "searches:", state["searches"])
            if state is None:
                raise RuntimeError("Graph produced no state")
        print_result(state, show_evidence=args.show_evidence)
        if live:
            print("model requests:", model.calls)
        if state["status"] == "failed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
