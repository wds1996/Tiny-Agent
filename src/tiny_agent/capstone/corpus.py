from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..retrieval import DocumentChunk, HashEmbeddingModel, InMemoryVectorRetriever, chunk_text
from .models import Evidence


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    id: str
    title: str
    text: str
    source_url: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("document id must be non-empty")
        if not self.title.strip():
            raise ValueError("document title must be non-empty")
        if not self.text.strip():
            raise ValueError("document text must be non-empty")


class LocalResearchCorpus:
    """Local full-text KB built on Stage 04's inspectable retrieval primitives."""

    def __init__(
        self,
        documents: Sequence[CorpusDocument],
        *,
        chunk_size: int = 180,
        overlap: int = 30,
        embedding_dimension: int = 384,
    ) -> None:
        if not documents:
            raise ValueError("at least one corpus document is required")
        self.documents = tuple(documents)
        chunks: list[DocumentChunk] = []
        for document in self.documents:
            metadata = {
                "document_id": document.id,
                "title": document.title,
                "source_url": document.source_url,
                "authors": list(document.authors),
                "year": document.year,
                **dict(document.metadata),
            }
            chunks.extend(
                chunk_text(
                    document.text,
                    document_id=document.id,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    metadata=metadata,
                )
            )
        self.retriever = InMemoryVectorRetriever(
            chunks,
            HashEmbeddingModel(dimension=embedding_dimension),
        )

    def search(self, query: str, *, top_k: int = 4) -> list[Evidence]:
        if not query.strip():
            raise ValueError("query must be non-empty")
        results = self.retriever.retrieve(query, top_k=top_k)
        evidence: list[Evidence] = []
        for index, result in enumerate(results, start=1):
            meta = dict(result.chunk.metadata)
            source_url = meta.get("source_url")
            evidence.append(
                Evidence(
                    id=f"L{index}-{result.chunk.id}",
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


def load_corpus_jsonl(path: str | Path) -> list[CorpusDocument]:
    source = Path(path)
    documents: list[CorpusDocument] = []
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number} of {source}") from exc
            documents.append(
                CorpusDocument(
                    id=str(item["id"]),
                    title=str(item["title"]),
                    text=str(item["text"]),
                    source_url=item.get("source_url"),
                    authors=tuple(str(value) for value in item.get("authors", [])),
                    year=int(item["year"]) if item.get("year") is not None else None,
                    metadata=dict(item.get("metadata", {})),
                )
            )
    if not documents:
        raise ValueError(f"corpus file contains no documents: {source}")
    return documents


def write_corpus_jsonl(path: str | Path, documents: Iterable[CorpusDocument]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(
                json.dumps(
                    {
                        "id": document.id,
                        "title": document.title,
                        "text": document.text,
                        "source_url": document.source_url,
                        "authors": list(document.authors),
                        "year": document.year,
                        "metadata": dict(document.metadata),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def extract_pdf_text(path: str | Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PDF ingestion requires Stage 15 dependencies: python -m pip install -e '.[stage15]'"
        ) from exc
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    result = "\n\n".join(page for page in pages if page).strip()
    if not result:
        raise ValueError(f"no extractable text found in PDF: {path}")
    return result
