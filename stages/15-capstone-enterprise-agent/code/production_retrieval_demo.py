import os

from openai import OpenAI
from qdrant_client import QdrantClient

from tiny_agent.capstone import CorpusDocument
from tiny_agent.capstone.production_corpus import qdrant_research_corpus_from_documents
from tiny_agent.integrations.openai_embeddings import OpenAIEmbeddingModel


if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("Set OPENAI_API_KEY to run the real semantic retrieval demo.")

documents = [
    CorpusDocument(
        id="react",
        title="ReAct note",
        text="ReAct interleaves reasoning, actions, tool calls, and observations in an Agent trajectory.",
    ),
    CorpusDocument(
        id="rag",
        title="RAG note",
        text="Retrieval-augmented generation retrieves external evidence before grounded generation.",
    ),
]

embedding = OpenAIEmbeddingModel(OpenAI(), model="text-embedding-3-small", dimension=1536)
corpus = qdrant_research_corpus_from_documents(
    documents,
    embedding_model=embedding,
    client=QdrantClient(":memory:"),
    collection_name="openscholar-demo",
)

for item in corpus.search("How does retrieval differ from Agent tool use?", top_k=2):
    print(item.title, item.score, item.text)
