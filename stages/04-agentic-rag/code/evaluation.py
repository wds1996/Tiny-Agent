"""Small, passage-level retrieval checks; no labels enter generation prompts."""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from retrieval import InMemoryVectorRetriever, Scope, lexical_rerank, make_demo_corpus, positive_int


def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    positive_int(k, "k")
    if not relevant_ids:
        raise ValueError("Recall is undefined here without relevant passages")
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    positive_int(k, "k")
    if not relevant_ids:
        raise ValueError("Reciprocal rank needs nonempty reference evidence")
    return next((1 / rank for rank, ident in enumerate(retrieved_ids[:k], 1)
                 if ident in relevant_ids), 0.0)


@dataclass(frozen=True)
class RetrievalCase:
    name: str
    query: str
    scope: Scope
    relevant_ids: frozenset[str]


def cases() -> list[RetrievalCase]:
    result = []
    for lang in ("zh-CN", "en"):
        def ids(*topics):
            doc = f"acme-refunds-v2-{lang}"
            return frozenset(f"{doc}:{topic}:0" for topic in topics)
        queries = [
            ("window", "新订单 原路退款 申请期限", "new orders original-payment refund window", ids("window-new")),
            ("approval", "提交材料 退款审核手续", "evidence submission refund approval procedure", ids("approval")),
            ("combined", "新订单原路退款期限与审核材料", "new order refund window and approval materials", ids("window-new", "approval")),
            ("paraphrase", "钱能沿着付钱的路退回来吗", "Can the money go back the way it came", ids("window-new", "approval")),
        ]
        result.extend(RetrievalCase(f"{lang}/{name}", zh if lang == "zh-CN" else en, Scope(language=lang), gold)
                      for name, zh, en, gold in queries)
    return result


def evaluate(index: InMemoryVectorRetriever, suite: Sequence[RetrievalCase], *, k: int) -> list[dict]:
    if not suite:
        raise ValueError("Evaluation suite must not be empty")
    rows = []
    for case in suite:
        candidates = index.retrieve(case.query, scope=case.scope, top_k=max(6, k))
        retrieved = [hit.chunk.id for hit in lexical_rerank(case.query, candidates, top_k=k)]
        gold = set(case.relevant_ids)
        rows.append(dict(case=case.name, ids=retrieved,
                         recall=recall_at_k(retrieved, gold, k=k),
                         rr=reciprocal_rank(retrieved, gold, k=k)))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Passage Recall@K and MRR@K on visible teaching cases.")
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()
    rows = evaluate(InMemoryVectorRetriever(make_demo_corpus()), cases(), k=args.k)
    for row in rows:
        print(f"{row['case']}: recall={row['recall']:.3f}; RR={row['rr']:.3f}; IDs={row['ids']}")
    print(f"mean Recall@{args.k}={mean(row['recall'] for row in rows):.3f}")
    print(f"MRR@{args.k}={mean(row['rr'] for row in rows):.3f}")
    print("Small development set, not held-out model-quality evaluation. Unknown-topic refusal is checked separately.")


if __name__ == "__main__":
    main()
