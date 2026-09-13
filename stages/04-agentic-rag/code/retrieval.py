"""Visible policy sources, section-aware chunks, and a lexical vector baseline."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Protocol, Sequence

DATA_DIRECTORY = Path(__file__).with_name("data")
HEADING = re.compile(r"^## ([a-z0-9-]+) \| (.+)$", re.MULTILINE)
WORDS = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]+", re.IGNORECASE)
STOP_WORDS = frozenset("a an the is are of in on for to and or can i my it this that be as with".split())


def positive_int(value: int, name: str) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Source:
    id: str
    file: str
    title: str
    tenant: str
    version: str
    status: str
    language: str


@dataclass(frozen=True)
class Document:
    source: Source
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    source: Source
    topic: str
    heading: str
    text: str
    start: int
    end: int
    complete_section: bool

    @property
    def digest(self) -> str:
        return sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Scope:
    tenant: str = "acme"
    language: str = "zh-CN"

    def __post_init__(self) -> None:
        if not self.tenant.strip() or self.language not in {"zh-CN", "en"}:
            raise ValueError("Invalid retrieval scope")

    def accepts(self, chunk: Chunk) -> bool:
        source = chunk.source
        return (source.tenant == self.tenant and source.language == self.language
                and source.status == "published")


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float


def load_demo_documents(directory: Path = DATA_DIRECTORY) -> list[Document]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    documents: list[Document] = []
    seen: set[str] = set()
    for entry in manifest:
        source = Source(**entry)
        if source.id in seen or Path(source.file).name != source.file:
            raise ValueError("Duplicate source ID or invalid source filename")
        if source.status not in {"published", "archived"}:
            raise ValueError("Unknown publication status")
        Scope(source.tenant, source.language)
        text = (directory / source.file).read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError("Empty source document")
        seen.add(source.id)
        documents.append(Document(source, text))
    return documents


def chunk_document(document: Document, *, max_chars: int = 1200,
                   overlap: int = 80) -> list[Chunk]:
    """Keep short sections whole; window only long sections, with character offsets."""
    positive_int(max_chars, "max_chars")
    if type(overlap) is not int or not 0 <= overlap < max_chars:
        raise ValueError("Require 0 <= overlap < max_chars")
    headings = list(HEADING.finditer(document.text))
    if not headings:
        raise ValueError("Document needs '## topic | heading' sections")
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for index, heading in enumerate(headings):
        topic, title = heading.groups()
        if topic in seen:
            raise ValueError("Duplicate section topic within one document")
        seen.add(topic)
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(document.text)
        while start < end and document.text[start].isspace():
            start += 1
        while end > start and document.text[end - 1].isspace():
            end -= 1
        if start == end:
            raise ValueError("Empty policy section")
        for part, left in enumerate(range(start, end, max_chars - overlap)):
            right = min(left + max_chars, end)
            chunks.append(Chunk(
                f"{document.source.id}:{topic}:{part}", document.source, topic, title,
                document.text[left:right], left, right, end - start <= max_chars,
            ))
            if right == end:
                break
    return chunks


def make_demo_corpus(*, max_chars: int = 1200, overlap: int = 80) -> list[Chunk]:
    return [chunk for doc in load_demo_documents()
            for chunk in chunk_document(doc, max_chars=max_chars, overlap=overlap)]


def tokenize(text: str) -> list[str]:
    """English terms and Chinese character bigrams; not a model tokenizer."""
    tokens: list[str] = []
    for word in WORDS.findall(text.lower()):
        if "\u3400" <= word[0] <= "\u9fff":
            tokens.extend(word[i:i + 2] for i in range(max(1, len(word) - 1)))
        elif word not in STOP_WORDS:
            tokens.append(word)
    return tokens


def normalize(vector: Sequence[float]) -> list[float]:
    if not vector or any(not math.isfinite(x) for x in vector):
        raise ValueError("Vector must be nonempty and finite")
    norm = math.hypot(*vector)
    return [x / norm for x in vector] if norm else [0.0] * len(vector)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vector dimensions differ")
    return sum(a * b for a, b in zip(normalize(left), normalize(right)))


class EmbeddingModel(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class TfidfEmbeddingModel:
    """Fitted lexical vectors, not trained semantic embeddings."""
    def __init__(self, texts: Sequence[str]) -> None:
        if not texts:
            raise ValueError("Fit on a nonempty corpus")
        document_frequency: Counter[str] = Counter()
        for text in texts:
            document_frequency.update(set(tokenize(text)))
        if not document_frequency:
            raise ValueError("Corpus has no indexable terms")
        self.vocabulary = tuple(sorted(document_frequency))
        self.dimension = len(self.vocabulary)
        self.idf = [1 + math.log((1 + len(texts)) / (1 + document_frequency[t]))
                    for t in self.vocabulary]

    def embed_query(self, text: str) -> list[float]:
        counts = Counter(tokenize(text))
        vector = [counts[term] * weight for term, weight in zip(self.vocabulary, self.idf)]
        return normalize(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


def searchable_text(chunk: Chunk) -> str:
    return f"{chunk.heading}\n{chunk.text}"


class InMemoryVectorRetriever:
    def __init__(self, chunks: Sequence[Chunk], embedding: EmbeddingModel | None = None) -> None:
        self.chunks = tuple(chunks)
        if len({chunk.id for chunk in chunks}) != len(chunks):
            raise ValueError("Chunk IDs must be unique")
        self.by_id = {chunk.id: chunk for chunk in chunks}
        texts = [searchable_text(chunk) for chunk in chunks]
        self.embedding = embedding or TfidfEmbeddingModel(texts)
        self.vectors = self.embedding.embed_documents(texts)
        if len(self.vectors) != len(chunks):
            raise ValueError("Embedding count differs from chunk count")
        dimensions = {len(vector) for vector in self.vectors}
        if len(dimensions) > 1:
            raise ValueError("Document vector dimensions differ")
        self.vectors = [normalize(vector) for vector in self.vectors]

    def retrieve(self, query: str, *, scope: Scope, top_k: int = 4) -> list[SearchResult]:
        positive_int(top_k, "top_k")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must not be blank")
        vector = self.embedding.embed_query(query)
        ranked: list[SearchResult] = []
        for chunk, stored in zip(self.chunks, self.vectors):
            if not scope.accepts(chunk):
                continue
            score = cosine_similarity(vector, stored)
            if score > 0.0:
                ranked.append(SearchResult(chunk, score))
        return sorted(ranked, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]

    def verify(self, results: Sequence[SearchResult], scope: Scope) -> None:
        for hit in results:
            if self.by_id.get(hit.chunk.id) != hit.chunk or not scope.accepts(hit.chunk):
                raise ValueError("Evidence is not from this scoped corpus snapshot")
            if not math.isfinite(hit.score) or hit.score <= 0:
                raise ValueError("Invalid evidence score")


def lexical_rerank(query: str, candidates: Sequence[SearchResult], *, top_k: int) -> list[SearchResult]:
    positive_int(top_k, "top_k")
    query_terms = set(tokenize(query))
    def key(hit: SearchResult) -> tuple[float, float, str]:
        coverage = len(query_terms & set(tokenize(searchable_text(hit.chunk)))) / max(1, len(query_terms))
        return (-coverage, -hit.score, hit.chunk.id)
    return sorted(candidates, key=key)[:top_k]


def format_evidence(results: Sequence[SearchResult]) -> str:
    return "\n\n".join(
        f"[{hit.chunk.id}] {hit.chunk.source.title} / {hit.chunk.heading}\n"
        f"file={hit.chunk.source.file}; version={hit.chunk.source.version}; score={hit.score:.4f}\n"
        f"{hit.chunk.text}" for hit in results
    ) or "[no evidence]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Search fictional, versioned policy sections.")
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--query", default=None)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--max-chars", type=int, default=1200)
    args = parser.parse_args()
    chunks = make_demo_corpus(max_chars=args.max_chars, overlap=min(80, args.max_chars - 1))
    index = InMemoryVectorRetriever(chunks)
    query = args.query or ("新订单 原路退款 申请期限" if args.language == "zh-CN"
                           else "new orders original-payment refund window")
    print("documents:", len(load_demo_documents()), "chunks:", len(chunks))
    print("embedding: lexical TF-IDF; no neural model; no API request")
    hits = index.retrieve(query, scope=Scope(language=args.language), top_k=args.top_k)
    print(format_evidence(hits))


if __name__ == "__main__":
    main()
