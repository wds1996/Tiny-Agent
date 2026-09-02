from __future__ import annotations

from collections import Counter
from typing import Protocol, Sequence

from ..retrieval import DocumentChunk, EmbeddingModel, Retriever, chunk_text
from .corpus import CorpusDocument
from .models import Evidence


class ResearchCorpus(Protocol):
    def search(self, query: str, *, top_k: int = 4) -> list[Evidence]:
        ...


class RetrieverResearchCorpus:
    """Map any Stage 04 Retriever into OpenScholar's evidence contract."""

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def search(self, query: str, *, top_k: int = 4) -> list[Evidence]:
        results = self.retriever.retrieve(query, top_k=top_k)
        evidence: list[Evidence] = []
        for index, result in enumerate(results, start=1):
            meta = dict(result.chunk.metadata)
            source_url = meta.get("source_url")
            evidence.append(
                Evidence(
                    id=f"R{index}-{result.chunk.id}",
                    kind="local_fulltext",
                    title=str(meta.get("title") or meta.get("document_id") or result.chunk.id),
                    text=result.chunk.text,
                    source_url=str(source_url) if source_url else None,
                    locator=f"chunk {meta.get('chunk_index', '?')}",
                    score=float(result.score),
                    metadata=meta,
                )
            )
        return evidence


class DiversifiedResearchCorpus:
    """Post-retrieval diversity wrapper limiting repeated chunks per document."""

    def __init__(self, base: ResearchCorpus, *, max_per_document: int = 1, candidate_multiplier: int = 4) -> None:
        if max_per_document <= 0 or candidate_multiplier <= 0:
            raise ValueError("diversity limits must be positive")
        self.base = base
        self.max_per_document = max_per_document
        self.candidate_multiplier = candidate_multiplier

    def search(self, query: str, *, top_k: int = 4) -> list[Evidence]:
        candidates = self.base.search(query, top_k=max(top_k, top_k * self.candidate_multiplier))
        counts: Counter[str] = Counter()
        selected: list[Evidence] = []
        for item in candidates:
            document_id = str(item.metadata.get("document_id") or item.title)
            if counts[document_id] >= self.max_per_document:
                continue
            counts[document_id] += 1
            selected.append(item)
            if len(selected) >= top_k:
                break
        return selected


def qdrant_research_corpus_from_documents(
    documents: Sequence[CorpusDocument],
    *,
    embedding_model: EmbeddingModel,
    client,
    collection_name: str = "openscholar",
    chunk_size: int = 180,
    overlap: int = 30,
    diversify: bool = True,
) -> ResearchCorpus:
    # Keep qdrant-client optional for learners who import only the core package.
    from ..retrievers.qdrant import QdrantRetriever

    chunks: list[DocumentChunk] = []
    for document in documents:
        chunks.extend(
            chunk_text(
                document.text,
                document_id=document.id,
                chunk_size=chunk_size,
                overlap=overlap,
                metadata={
                    "document_id": document.id,
                    "title": document.title,
                    "source_url": document.source_url,
                    "authors": list(document.authors),
                    "year": document.year,
                    **dict(document.metadata),
                },
            )
        )
    retriever = QdrantRetriever.from_chunks(
        chunks,
        client=client,
        collection_name=collection_name,
        embedding_model=embedding_model,
    )
    corpus: ResearchCorpus = RetrieverResearchCorpus(retriever)
    if diversify:
        corpus = DiversifiedResearchCorpus(corpus)
    return corpus
