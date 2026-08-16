"""Stage 04 example 7: retrieval decision -> weak evidence -> one query rewrite."""

from tiny_agent import AgenticRAGWorkflow, HashEmbeddingModel, InMemoryVectorRetriever

from _demo_support import DEMO_CHUNKS, EvidenceEchoAnswerer, ScriptedDecisionModel


retriever = InMemoryVectorRetriever(
    DEMO_CHUNKS,
    HashEmbeddingModel(dimension=256),
)

decisions = ScriptedDecisionModel(
    [
        {"retrieve": True, "query": "vector storage"},
        {"sufficient": False, "rewritten_query": "qdrant payload filtering"},
        {"sufficient": True, "rewritten_query": ""},
    ]
)

workflow = AgenticRAGWorkflow(
    decision_model=decisions,
    retriever=retriever,
    answer_generator=EvidenceEchoAnswerer(),
    max_rewrites=1,
)

result = workflow.run("Which backend supports payload filtering?", top_k=1)

print("status:", result.status)
print("query history:", result.query_history)
print("evidence:", [item.chunk.id for item in result.evidence])
print("answer:", result.answer)
