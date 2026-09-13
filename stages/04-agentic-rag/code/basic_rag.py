"""One search, explicit evidence checks, then an extractive or model answer."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Protocol, Sequence

from retrieval import (InMemoryVectorRetriever, Scope, SearchResult, format_evidence,
                       lexical_rerank, make_demo_corpus, positive_int)

TOPIC_QUERIES = {
    "window-new": ("新订单 原路退款 申请期限", "new orders original-payment refund window"),
    "window-old": ("较早订单 过渡 30 期限", "earlier orders transition window"),
    "approval": ("提交材料 退款审核手续 授权人员", "evidence submission refund approval procedure authorized reviewer"),
    "delivery": ("普通配送 发货 工作日", "standard delivery after dispatch business days"),
    "warranty": ("量子设备 保修条件", "quantum device warranty conditions"),
}


@dataclass(frozen=True)
class RAGTask:
    question: str
    scope: Scope
    required_topics: tuple[str, ...]
    facts: tuple[tuple[str, str], ...] = ()
    greeting: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.question, str) or not self.question.strip() or len(self.question) > 1500:
            raise ValueError("Question must contain 1..1500 characters")
        if (not isinstance(self.facts, tuple) or any(
                not isinstance(pair, tuple) or len(pair) != 2
                or any(not isinstance(value, str) or not value.strip() for value in pair)
                for pair in self.facts)):
            raise ValueError("Facts must be named, nonempty strings")
        if len({key for key, _ in self.facts}) != len(self.facts):
            raise ValueError("Duplicate fact keys")
        if type(self.greeting) is not bool or not isinstance(self.scope, Scope):
            raise ValueError("Invalid task scope or greeting flag")
        if (not isinstance(self.required_topics, tuple)
                or len(set(self.required_topics)) != len(self.required_topics)
                or any(topic not in TOPIC_QUERIES for topic in self.required_topics)):
            raise ValueError("Invalid product evidence checklist")
        if bool(self.required_topics) == self.greeting:
            raise ValueError("Only the explicit greeting task may skip the checklist")


def sample_task(case: str = "current", language: str = "zh-CN") -> RAGTask:
    """Product fixtures: the checklist is configured by the app, not inferred from text."""
    scope = Scope(language=language)
    zh = language == "zh-CN"
    if case in {"current", "earlier"}:
        ordered = "2026-08-03" if case == "current" else "2026-07-20"
        topic = "window-new" if case == "current" else "window-old"
        question = (
            f"我在 {ordered} 下单的普通商品已付款、完好未使用，现在是第 38 天。"
            "还能申请原路退款吗？办理审核手续需要哪些材料？"
            if zh else
            f"My ordinary-goods order from {ordered} is paid, unused and intact, and now on day 38. "
            "Can I request an original-payment refund? What evidence is needed for approval?"
        )
        facts = (("order_date", ordered), ("age_days", "38"), ("category", "ordinary goods"),
                 ("payment", "paid"), ("condition", "unused and intact"))
        return RAGTask(question, scope, (topic, "approval"), facts)
    if case == "delivery":
        return RAGTask("普通配送从发货开始通常要几个工作日？" if zh else
                       "How many business days does standard delivery normally take after dispatch?",
                       scope, ("delivery",))
    if case == "unknown":
        return RAGTask("量子设备损坏后的保修条件是什么？" if zh else
                       "What are the warranty conditions for a broken quantum device?",
                       scope, ("warranty",))
    if case == "greeting":
        return RAGTask("你好" if zh else "Hello", scope, (), greeting=True)
    raise ValueError("Unknown demo case")


@dataclass(frozen=True)
class EvidenceDecision:
    sufficient: bool
    evidence_ids: tuple[str, ...]
    reason: str
    rewritten_query: str = ""

    def __post_init__(self) -> None:
        if type(self.sufficient) is not bool:
            raise ValueError("sufficient must be a boolean")
        if (not isinstance(self.evidence_ids, tuple) or len(self.evidence_ids) > 8
                or any(not isinstance(key, str) or not key for key in self.evidence_ids)
                or len(set(self.evidence_ids)) != len(self.evidence_ids)):
            raise ValueError("Invalid evidence IDs")
        if not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 800:
            raise ValueError("Decision needs a short reason")
        if not isinstance(self.rewritten_query, str) or len(self.rewritten_query) > 500:
            raise ValueError("Invalid rewritten query")
        if self.sufficient and (not self.evidence_ids or self.rewritten_query):
            raise ValueError("A sufficient decision needs IDs and must not request a rewrite")
        if not self.sufficient and self.evidence_ids:
            raise ValueError("An insufficient decision must not approve evidence")


class DecisionPolicy(Protocol):
    def assess(self, task: RAGTask, query: str, evidence: Sequence[SearchResult]) -> EvidenceDecision: ...


class ChecklistPolicy:
    """Offline, topic-based test double; does not determine semantic entailment."""
    def assess(self, task: RAGTask, query: str, evidence: Sequence[SearchResult]) -> EvidenceDecision:
        complete = {hit.chunk.topic: hit for hit in evidence if hit.chunk.complete_section}
        missing = [topic for topic in task.required_topics if topic not in complete]
        if missing:
            query = TOPIC_QUERIES[missing[0]][task.scope.language == "en"]
            return EvidenceDecision(False, (), f"Missing complete section: {missing[0]}", query)
        ids = tuple(complete[topic].chunk.id for topic in task.required_topics)
        return EvidenceDecision(True, ids, "All configured section topics are present; not a semantic proof")


def approved_evidence(task: RAGTask, decision: EvidenceDecision,
                      evidence: Sequence[SearchResult]) -> tuple[SearchResult, ...]:
    """Necessary source/checklist checks, not a general answer-quality oracle."""
    if not isinstance(decision, EvidenceDecision) or not decision.sufficient:
        raise ValueError("No affirmative evidence decision")
    by_id = {hit.chunk.id: hit for hit in evidence}
    if not set(decision.evidence_ids).issubset(by_id):
        raise ValueError("Assessment cited unseen evidence")
    selected = tuple(by_id[key] for key in decision.evidence_ids)
    if any(not task.scope.accepts(hit.chunk) or not hit.chunk.complete_section for hit in selected):
        raise ValueError("Assessment approved ineligible or fragmented evidence")
    covered = {hit.chunk.topic for hit in selected}
    if not set(task.required_topics).issubset(covered):
        raise ValueError("Assessment omitted a required section topic")
    return selected


@dataclass(frozen=True)
class Citation:
    evidence_id: str
    quote: str


@dataclass(frozen=True)
class AnswerDraft:
    text: str
    citations: tuple[Citation, ...]


def validate_answer(answer: AnswerDraft, evidence: Sequence[SearchResult]) -> None:
    if not isinstance(answer, AnswerDraft) or not isinstance(answer.text, str) or not answer.text.strip():
        raise ValueError("Answer must contain text")
    if len(answer.text) > 8000 or not isinstance(answer.citations, tuple):
        raise ValueError("Invalid answer contract")
    by_id = {hit.chunk.id: hit.chunk for hit in evidence}
    ids: list[str] = []
    for citation in answer.citations:
        if not isinstance(citation, Citation) or citation.evidence_id not in by_id:
            raise ValueError("Answer cited evidence that was not supplied")
        quote = citation.quote
        if not isinstance(quote, str) or not quote.strip() or quote not in by_id[citation.evidence_id].text:
            raise ValueError("Citation quote is absent from its cited passage")
        ids.append(citation.evidence_id)
    if len(ids) != len(set(ids)) or set(ids) != set(by_id):
        raise ValueError("Citations must identify each selected evidence passage exactly once")


class AnswerGenerator(Protocol):
    kind: str
    def answer(self, task: RAGTask, evidence: Sequence[SearchResult]) -> AnswerDraft: ...


class ExtractiveAnswerer:
    """Return the selected source text verbatim; no LLM and no inferred eligibility."""
    kind = "extractive"
    def answer(self, task: RAGTask, evidence: Sequence[SearchResult]) -> AnswerDraft:
        text = "\n\n".join(f"[{hit.chunk.id}] {hit.chunk.text}" for hit in evidence)
        return AnswerDraft(text, tuple(Citation(hit.chunk.id, hit.chunk.text) for hit in evidence))


def evidence_payload(evidence: Sequence[SearchResult]) -> list[dict[str, str]]:
    """Scores rank candidates; they are not supplied as answer confidence."""
    return [dict(id=hit.chunk.id, title=hit.chunk.source.title, heading=hit.chunk.heading,
                 version=hit.chunk.source.version, text=hit.chunk.text) for hit in evidence]


@dataclass(frozen=True)
class RAGResult:
    status: str
    answer: AnswerDraft | None
    evidence: tuple[SearchResult, ...]
    reason: str
    answer_kind: str = "none"


def pack_evidence(results: Sequence[SearchResult], *, max_chars: int = 6000,
                  max_items: int = 8) -> tuple[SearchResult, ...]:
    """Keep whole passages in first-seen order, deduplicated by immutable chunk ID."""
    positive_int(max_chars, "max_chars")
    positive_int(max_items, "max_items")
    kept: list[SearchResult] = []
    seen: set[str] = set()
    used = 0
    for hit in results:
        if hit.chunk.id in seen:
            continue
        if len(kept) >= max_items or used + len(hit.chunk.text) > max_chars:
            continue
        kept.append(hit)
        seen.add(hit.chunk.id)
        used += len(hit.chunk.text)
    return tuple(kept)


class BasicRAG:
    def __init__(self, retriever: InMemoryVectorRetriever, *,
                 policy: DecisionPolicy | None = None, answerer: AnswerGenerator | None = None,
                 max_evidence_chars: int = 6000) -> None:
        positive_int(max_evidence_chars, "max_evidence_chars")
        self.max_evidence_chars = max_evidence_chars
        self.retriever = retriever
        self.policy = policy or ChecklistPolicy()
        self.answerer = answerer or ExtractiveAnswerer()

    def run(self, task: RAGTask, *, top_k: int = 3, candidate_k: int = 6) -> RAGResult:
        positive_int(top_k, "top_k")
        positive_int(candidate_k, "candidate_k")
        if top_k > candidate_k:
            raise ValueError("top_k cannot exceed candidate_k")
        if task.greeting:
            return RAGResult("direct", None, (), "你好，请告诉我想查的政策。" if
                             task.scope.language == "zh-CN" else "Hello. Which policy would you like to check?")
        evidence: tuple[SearchResult, ...] = ()
        try:
            candidates = self.retriever.retrieve(task.question, scope=task.scope, top_k=candidate_k)
            evidence = pack_evidence(lexical_rerank(task.question, candidates, top_k=top_k),
                                     max_chars=self.max_evidence_chars)
            self.retriever.verify(evidence, task.scope)
            decision = self.policy.assess(task, task.question, evidence)
            if not isinstance(decision, EvidenceDecision):
                raise ValueError("Policy did not return EvidenceDecision")
            if not decision.sufficient:
                return RAGResult("insufficient_evidence", None, evidence, decision.reason)
            selected = approved_evidence(task, decision, evidence)
            answer = self.answerer.answer(task, selected)
            validate_answer(answer, selected)
            return RAGResult("answered", answer, selected, "Citation contract checked", self.answerer.kind)
        except Exception as exc:
            return RAGResult("failed", None, evidence, f"Stopped: {type(exc).__name__}")


def demo_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--case", choices=("current", "earlier", "delivery", "unknown", "greeting"), default="current")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--show-evidence", action="store_true")
    return parser


def main() -> None:
    args = demo_parser("A fixed RAG path; offline excerpts, not model-written answers.").parse_args()
    task = sample_task(args.case, args.language)
    result = BasicRAG(InMemoryVectorRetriever(make_demo_corpus())).run(task, top_k=args.top_k)
    print("mode: offline checklist + source excerpts; model calls: 0")
    print("question:", task.question)
    print("status:", result.status, "answer_kind:", result.answer_kind)
    print(result.answer.text if result.answer else result.reason)
    if args.show_evidence:
        print(format_evidence(result.evidence))
    if result.status == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
