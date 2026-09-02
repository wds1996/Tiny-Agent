import pytest

from tiny_agent.capstone import CorpusDocument
from tiny_agent.capstone.models import Evidence, ResearchMetrics, ResearchReport
from tiny_agent.capstone.production_corpus import (
    DiversifiedResearchCorpus,
    qdrant_research_corpus_from_documents,
)
from tiny_agent.capstone.semantic_evaluation import SupportDecision, evaluate_citation_support
from tiny_agent.retrieval import HashEmbeddingModel


class FakeCorpus:
    def search(self, query: str, *, top_k: int = 4):
        return [
            Evidence("a1", "local_fulltext", "A", "claim alpha", score=0.9, metadata={"document_id": "a"}),
            Evidence("a2", "local_fulltext", "A", "claim alpha second chunk", score=0.8, metadata={"document_id": "a"}),
            Evidence("b1", "local_fulltext", "B", "claim beta", score=0.7, metadata={"document_id": "b"}),
        ][:top_k]


def test_diversified_corpus_limits_repeated_document_chunks() -> None:
    corpus = DiversifiedResearchCorpus(FakeCorpus(), max_per_document=1)
    results = corpus.search("x", top_k=2)
    assert [item.metadata["document_id"] for item in results] == ["a", "b"]


def test_qdrant_research_corpus_reuses_stage04_retriever_contract() -> None:
    qdrant = pytest.importorskip("qdrant_client")
    corpus = qdrant_research_corpus_from_documents(
        [
            CorpusDocument(id="a", title="A", text="retrieval evidence alpha"),
            CorpusDocument(id="b", title="B", text="agent reasoning beta"),
        ],
        embedding_model=HashEmbeddingModel(32),
        client=qdrant.QdrantClient(":memory:"),
        collection_name="test-openscholar-v2",
    )
    results = corpus.search("retrieval evidence", top_k=2)
    assert results
    assert all(item.kind == "local_fulltext" for item in results)


class FakeJudge:
    def judge(self, *, claim, evidence):
        return SupportDecision("supported" in evidence[0].text, "fake deterministic judge")


def test_semantic_citation_support_is_separate_from_label_existence() -> None:
    evidence = Evidence("E1", "local_fulltext", "Paper", "supported fact", score=1.0)
    report = ResearchReport(
        run_id="r",
        status="completed",
        question="q",
        answer="The supported fact is true [E1].",
        evidence=(evidence,),
        citations=("[E1]",),
        metrics=ResearchMetrics(),
    )
    semantic = evaluate_citation_support(report, FakeJudge())
    assert semantic.passed
    assert semantic.support_rate == 1.0
