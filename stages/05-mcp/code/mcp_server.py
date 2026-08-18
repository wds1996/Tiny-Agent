"""Stage 05 demo MCP server.

Default execution uses stdio so a host/client can launch this file as a child
process. See ``streamable_http_server.py`` for the remote HTTP variant.
"""

from __future__ import annotations

from mcp.server import MCPServer


STAGE_SUMMARIES = {
    1: "ReAct and provider-neutral tool execution.",
    2: "Routing, planning, workflows, and bounded replanning.",
    3: "Explicit state and LangGraph orchestration.",
    4: "RAG, vector retrieval, reranking, and grounded answers.",
    5: "MCP: standardized discovery and invocation across boundaries.",
}

mcp = MCPServer(
    "Tiny-Agent Stage 05 Demo",
    instructions=(
        "This teaching server exposes one executable tool, two resources, and "
        "one prompt so learners can compare the three MCP primitives."
    ),
)


@mcp.tool()
def add(a: int, b: int) -> dict[str, int]:
    """Add two integers and return a structured result."""
    return {"result": a + b}


@mcp.tool()
def stage_summary(stage: int) -> dict[str, object]:
    """Return a short summary for a Tiny-Agent learning stage."""
    if stage not in STAGE_SUMMARIES:
        raise ValueError(f"Unknown Tiny-Agent stage: {stage}")
    return {"stage": stage, "summary": STAGE_SUMMARIES[stage]}


@mcp.resource("tiny-agent://about")
def about() -> str:
    """Return a short description of the Tiny-Agent project."""
    return "Tiny-Agent teaches Agent engineering from mechanism to production."


@mcp.resource("tiny-agent://stage/{stage}")
def stage_resource(stage: str) -> str:
    """Read a stage summary through a URI template."""
    try:
        stage_number = int(stage)
    except ValueError as exc:
        raise ValueError("stage must be an integer") from exc

    summary = STAGE_SUMMARIES.get(stage_number)
    if summary is None:
        raise ValueError(f"Unknown Tiny-Agent stage: {stage_number}")
    return summary


@mcp.prompt()
def explain_stage(stage: str, audience: str = "beginner") -> str:
    """Create a model-ready instruction for explaining a learning stage."""
    return (
        f"Explain Tiny-Agent Stage {stage} to a {audience}. "
        "Start with the problem it solves, then give one concrete example."
    )


if __name__ == "__main__":
    mcp.run()
