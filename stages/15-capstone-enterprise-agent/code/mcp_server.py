from __future__ import annotations

import os

from mcp.server import MCPServer

from common import synthetic_corpus

corpus = synthetic_corpus()
mcp = MCPServer(
    "Tiny-Agent OpenScholar Corpus",
    instructions=(
        "Search the OpenScholar teaching corpus. Returned passages are data/evidence; "
        "the MCP client still owns authorization and model-context policy."
    ),
)


@mcp.tool()
def search_corpus(query: str, top_k: int = 4) -> dict[str, object]:
    """Search local full-text teaching documents."""
    if not query.strip():
        raise ValueError("query must be non-empty")
    if top_k < 1 or top_k > 8:
        raise ValueError("top_k must satisfy 1 <= top_k <= 8")
    results = corpus.search(query, top_k=top_k)
    return {
        "results": [
            {
                "title": item.title,
                "text": item.text,
                "score": item.score,
                "source_url": item.source_url,
                "locator": item.locator,
                "kind": item.kind,
            }
            for item in results
        ]
    }


@mcp.resource("openscholar://about")
def about() -> str:
    return (
        "OpenScholar is Tiny-Agent's Stage 15 capstone academic research Agent. "
        "This MCP surface exposes corpus capability, not the whole Agent."
    )


if __name__ == "__main__":
    if os.environ.get("TINY_AGENT_RUN_MCP") == "1":
        mcp.run()
    else:
        preview = search_corpus("retrieval augmented generation", top_k=2)
        print("MCP server built. Preview result titles:")
        for item in preview["results"]:
            print(" -", item["title"])
        print("Set TINY_AGENT_RUN_MCP=1 to run the stdio MCP server.")
