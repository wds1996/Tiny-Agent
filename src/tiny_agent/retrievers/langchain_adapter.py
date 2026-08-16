"""LangChain Retriever adapter for Tiny-Agent's provider-neutral Retriever."""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field


class TinyAgentLangChainRetriever(BaseRetriever):
    """Expose a Tiny-Agent retriever through LangChain's Retriever interface.

    ``BaseRetriever`` is a Pydantic model. Tiny-Agent's ``Retriever`` is a
    structural ``Protocol`` intended for static/duck-typed boundaries, not a
    runtime ``isinstance`` target. The field is therefore stored as ``Any`` at
    the Pydantic boundary while the expected runtime contract remains
    ``obj.retrieve(query, top_k=..., metadata_filter=...)``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    retriever: Any
    top_k: int = Field(default=4, gt=0)
    metadata_filter: dict[str, Any] | None = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        del run_manager  # Tiny-Agent's minimal retriever has no callback surface yet.
        retrieve = getattr(self.retriever, "retrieve", None)
        if not callable(retrieve):
            raise TypeError("retriever must provide a callable retrieve(...) method")

        results = retrieve(
            query,
            top_k=self.top_k,
            metadata_filter=self.metadata_filter,
        )
        return [
            Document(
                page_content=result.chunk.text,
                metadata={
                    **dict(result.chunk.metadata),
                    "chunk_id": result.chunk.id,
                    "retrieval_score": result.score,
                },
            )
            for result in results
        ]
