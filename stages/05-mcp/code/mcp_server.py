from __future__ import annotations

from mcp.server import MCPServer


HANDBOOK = {
    "refunds": (
        "Orders may be refunded to the original payment method within 30 days. "
        "After 30 days, support may offer store credit after review."
    ),
    "shipping": (
        "Standard shipping normally takes 3-5 business days after dispatch."
    ),
}

mcp = MCPServer(
    "Tiny-Agent Stage 05",
    instructions=(
        "Teaching server for MCP Tools, Resources, and Prompts. "
        "The host remains responsible for deciding which capabilities are trusted and exposed."
    ),
)


@mcp.tool()
def add(a: int, b: int) -> dict[str, int]:
    """Add two integers and return structured data."""
    return {"result": a + b}


@mcp.tool()
def lookup_policy(topic: str) -> dict[str, str]:
    """Return one handbook policy by topic."""
    normalized = topic.strip().lower()
    if normalized not in HANDBOOK:
        raise ValueError(f"unknown policy topic: {topic}")
    return {"topic": normalized, "policy": HANDBOOK[normalized]}


@mcp.resource("tiny-agent://about")
def about() -> str:
    """Describe the teaching server."""
    return "Tiny-Agent Stage 05 demonstrates MCP interoperability boundaries."


@mcp.resource("tiny-agent://handbook/{topic}")
def handbook(topic: str) -> str:
    """Read a handbook entry by URI."""
    normalized = topic.strip().lower()
    if normalized not in HANDBOOK:
        raise ValueError(f"unknown handbook topic: {topic}")
    return HANDBOOK[normalized]


@mcp.prompt()
def explain_mcp(topic: str, audience: str = "beginner") -> str:
    """Create a reusable model-facing instruction about MCP."""
    return (
        f"Explain {topic} to a {audience}. "
        "Start from the concrete problem, then give one MCP example and one non-example."
    )


if __name__ == "__main__":
    mcp.run()
