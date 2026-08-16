"""Stage 04 example 8: grounded workflow abstains when evidence stays weak."""

from tiny_agent import AgenticRAGWorkflow, HashEmbeddingModel, InMemoryVectorRetriever

from _demo_support import DEMO_CHUNKS, EvidenceEchoAnswerer, ScriptedDecisionModel


workflow = AgenticRAGWorkflow(
    decision_model=ScriptedDecisionModel(
        [
            {"retrieve": True, "query": "postgres backup policy"},
            {"sufficient": False, "rewritten_query": "database disaster recovery policy"},
            {"sufficient": False, "rewritten_query": ""},
        ]
    ),
    retriever=InMemoryVectorRetriever(
        DEMO_CHUNKS,
        HashEmbeddingModel(dimension=256),
    ),
    answer_generator=EvidenceEchoAnswerer(),
    max_rewrites=1,
)

result = workflow.run("What is our PostgreSQL disaster-recovery policy?", top_k=2)

print("status:", result.status)
print("query history:", result.query_history)
print("answer:", result.answer)

assert result.status == "insufficient_evidence"
