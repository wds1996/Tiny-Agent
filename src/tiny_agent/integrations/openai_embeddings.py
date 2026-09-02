from __future__ import annotations

from typing import Any, Sequence


class OpenAIEmbeddingModel:
    """Tiny-Agent EmbeddingModel adapter for OpenAI embeddings.

    The client is injected so tests remain offline and applications control
    credentials, retries, transport, and organization/project configuration.
    """

    def __init__(
        self,
        client: Any,
        *,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        if not model.strip() or dimension <= 0:
            raise ValueError("embedding model and dimension must be valid")
        self.client = client
        self.model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedding inputs must be non-empty strings")
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self._dimension,
        )
        data = sorted(response.data, key=lambda item: int(getattr(item, "index", 0)))
        vectors = [list(map(float, item.embedding)) for item in data]
        if len(vectors) != len(texts):
            raise ValueError("embedding provider returned an unexpected vector count")
        if any(len(vector) != self._dimension for vector in vectors):
            raise ValueError("embedding provider returned an unexpected vector dimension")
        return vectors
