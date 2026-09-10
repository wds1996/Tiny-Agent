from __future__ import annotations

import unittest

from agentic_rag import (
    AgenticRAG,
    EvidenceDecision,
    RetrievalDecision,
    ScriptedPolicy,
)
from langgraph_agentic_rag import (
    EvidenceDecision as GraphEvidenceDecision,
    RetrievalDecision as GraphRetrievalDecision,
    ScriptedPolicy as GraphScriptedPolicy,
    build_graph as build_langgraph_rag,
    initial_state as langgraph_initial_state,
)
from langgraph_deepseek_rag import (
    build_graph as build_langgraph_deepseek_rag,
    initial_state as langgraph_deepseek_initial_state,
)
from basic_rag import BasicRAG, EvidenceBoundAnswerer
from evaluation import recall_at_k, reciprocal_rank
from deepseek_rag import DeepSeekAnswerer
from retrieval import (
    Document,
    HashEmbeddingModel,
    InMemoryVectorRetriever,
    SearchResult,
    Chunk,
    chunk_document,
    cosine_similarity,
    lexical_rerank,
    load_demo_documents,
    make_demo_corpus,
)


class Stage04Checks(unittest.TestCase):
    def test_chunking_preserves_overlap_and_metadata(self) -> None:
        chunks = chunk_document(
            Document("doc", "one two three four five six seven", {"source": "notes"}),
            chunk_size=4,
            overlap=2,
        )
        self.assertEqual(
            [chunk.text for chunk in chunks],
            ["one two three four", "three four five six", "five six seven"],
        )
        self.assertEqual(chunks[1].metadata["source"], "notes")
        self.assertEqual(chunks[1].metadata["start_word"], 2)

    def test_invalid_overlap_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            chunk_document(Document("doc", "hello"), chunk_size=4, overlap=4)

    def test_course_corpus_is_loaded_from_versioned_text_files(self) -> None:
        documents = load_demo_documents()
        policy = next(document for document in documents if document.id.startswith("acme-"))
        self.assertEqual(policy.metadata["source_file"], "acme_refund_policy_2026-08.txt")
        self.assertIn("45 calendar days", " ".join(policy.text.split()))

    def test_cosine_similarity_has_expected_extremes(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0)
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 0.0]), 0.0)

    def test_metadata_filter_applies_before_ranking(self) -> None:
        retriever = InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel())
        results = retriever.retrieve(
            "vector",
            top_k=5,
            metadata_filter={"kind": "vector-database"},
        )
        self.assertTrue(results)
        self.assertTrue(
            all(item.chunk.metadata["kind"] == "vector-database" for item in results)
        )

    def test_reranker_prefers_better_query_coverage(self) -> None:
        candidates = [
            SearchResult(Chunk("a", "vector database"), 0.9),
            SearchResult(Chunk("b", "qdrant payload metadata filtering"), 0.6),
        ]
        reranked = lexical_rerank(
            "qdrant payload metadata filtering",
            candidates,
            top_k=1,
        )
        self.assertEqual(reranked[0].chunk.id, "b")

    def test_basic_rag_answers_from_retrieved_evidence(self) -> None:
        rag = BasicRAG(
            retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
            answer_generator=EvidenceBoundAnswerer(),
        )
        result = rag.run("qdrant payload metadata filtering", top_k=1)
        self.assertEqual(result.status, "grounded_answer")
        self.assertIn("qdrant", result.evidence[0].chunk.id)
        self.assertIn("source:", result.answer)

    def test_agentic_rag_can_skip_retrieval(self) -> None:
        workflow = AgenticRAG(
            policy=ScriptedPolicy(
                retrieval_decision=RetrievalDecision(retrieve=False),
                evidence_decisions=[],
            ),
            retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
        )
        state = workflow.run("hello")
        self.assertEqual(state.status, "direct_answer")
        self.assertEqual(state.query_history, [])

    def test_agentic_rag_rewrites_once_then_answers(self) -> None:
        workflow = AgenticRAG(
            policy=ScriptedPolicy(
                retrieval_decision=RetrievalDecision(True, "database backend"),
                evidence_decisions=[
                    EvidenceDecision(False, "qdrant payload metadata filtering"),
                    EvidenceDecision(True),
                ],
            ),
            retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
            max_rewrites=1,
        )
        state = workflow.run("Which backend supports payload metadata filtering?")
        self.assertEqual(state.status, "grounded_answer")
        self.assertEqual(state.rewrites, 1)
        self.assertEqual(
            state.query_history,
            ["database backend", "qdrant payload metadata filtering"],
        )

    def test_agentic_rag_stops_when_rewrite_budget_is_exhausted(self) -> None:
        workflow = AgenticRAG(
            policy=ScriptedPolicy(
                retrieval_decision=RetrievalDecision(True, "unknown"),
                evidence_decisions=[
                    EvidenceDecision(False, "still unknown"),
                ],
            ),
            retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
            max_rewrites=0,
        )
        state = workflow.run("What is not in this corpus?")
        self.assertEqual(state.status, "insufficient_evidence")
        self.assertEqual(state.rewrites, 0)

    def test_langgraph_agentic_rag_rewrites_once_then_answers(self) -> None:
        graph = build_langgraph_rag(
            policy=GraphScriptedPolicy(
                retrieval_decision=GraphRetrievalDecision(True, "database backend"),
                evidence_decisions=[
                    GraphEvidenceDecision(False, "qdrant payload metadata filtering"),
                    GraphEvidenceDecision(True),
                ],
            ),
            retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
            max_rewrites=1,
        )
        result = graph.invoke(
            langgraph_initial_state(
                "Which backend supports payload metadata filtering?"
            ),
            config={"recursion_limit": 10},
        )
        self.assertEqual(result["status"], "grounded_answer")
        self.assertEqual(result["rewrites"], 1)
        self.assertEqual(
            result["query_history"],
            ["database backend", "qdrant payload metadata filtering"],
        )

    def test_langgraph_deepseek_rag_keeps_evidence_boundary(self) -> None:
        graph = build_langgraph_deepseek_rag(
            retriever=InMemoryVectorRetriever(make_demo_corpus(), HashEmbeddingModel()),
            answer_generator=EvidenceBoundAnswerer(),
        )
        result = graph.invoke(
            langgraph_deepseek_initial_state(
                "Order 2026-08-03 original payment refund current policy"
            ),
            config={"recursion_limit": 5},
        )
        self.assertEqual(result["status"], "grounded_answer")
        self.assertTrue(result["evidence"])
        self.assertIn("source:", result["answer"])

    def test_deepseek_answerer_sends_evidence_as_bounded_input(self) -> None:
        class FakeResponses:
            def __init__(self) -> None:
                self.kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs

                class Response:
                    status = "completed"
                    output_text = "Qdrant supports payload filtering [1]."

                return Response()

        class FakeClient:
            def __init__(self) -> None:
                self.responses = FakeResponses()

        client = FakeClient()
        answerer = DeepSeekAnswerer(client=client, model="teaching-model")
        evidence = [
            SearchResult(
                Chunk("qdrant:0", "Qdrant supports payload filtering.", {"source": "notes"}),
                0.9,
            )
        ]
        answer = answerer.answer(question="What supports filtering?", evidence=evidence)

        self.assertIn("payload filtering", answer)
        self.assertEqual(client.responses.kwargs["model"], "teaching-model")
        self.assertIn("<retrieved_evidence>", client.responses.kwargs["input"])
        self.assertIn("source=notes", client.responses.kwargs["input"])

    def test_retrieval_metrics_have_clear_meanings(self) -> None:
        ids = ["qdrant:0", "faiss:0", "qdrant:1"]
        self.assertEqual(recall_at_k(ids, {"qdrant"}, k=1), 1.0)
        self.assertEqual(reciprocal_rank(ids, {"faiss"}), 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
