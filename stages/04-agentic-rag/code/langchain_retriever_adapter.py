"""Stage 04 example 4: expose Tiny-Agent retrieval through LangChain BaseRetriever."""

from tiny_agent import HashEmbeddingModel, InMemoryVectorRetriever
from tiny_agent.retrievers.langchain_adapter import TinyAgentLangChainRetriever

from _demo_support import DEMO_CHUNKS


base = InMemoryVectorRetriever(
    DEMO_CHUNKS,
    HashEmbeddingModel(dimension=256),
)
retriever = TinyAgentLangChainRetriever(retriever=base, top_k=2)

for document in retriever.invoke("retriever vector store"):
    print(document.metadata)
    print(document.page_content)
    print()

print(
    "Tiny-Agent still owns retrieval mechanics; LangChain standardizes the "
    "query -> Document interface for ecosystem composition."
)
