from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from support_data import (
    SUPPORT_GUIDES,
    create_support_case as create_case_record,
    get_invoice_summary as invoice_record,
    get_order_summary as order_record,
    get_shipment_status as shipment_record,
    read_support_guide,
)


mcp = MCPServer(
    "Tiny-Agent Acme Support",
    instructions=(
        "Teaching MCP server for one fictional support system. "
        "Discovery does not grant authorization; the host decides what to expose."
    ),
)


def _tool_call(operation, *args):
    try:
        return operation(*args)
    except (LookupError, ValueError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def get_order_summary(order_id: str) -> dict[str, object]:
    """Read the teaching order's date, status, item type, and paid amount."""
    return _tool_call(order_record, order_id)


@mcp.tool()
def get_shipment_status(order_id: str) -> dict[str, str]:
    """Read the teaching shipment status and tracking number for an order."""
    return _tool_call(shipment_record, order_id)


@mcp.tool()
def get_invoice_summary(order_id: str) -> dict[str, object]:
    """Read the teaching invoice number and paid amount for an order."""
    return _tool_call(invoice_record, order_id)


@mcp.tool()
def create_support_case(order_id: str, reason: str) -> dict[str, str]:
    """Create a teaching support case. This changes server-side business state."""
    return _tool_call(create_case_record, order_id, reason)


@mcp.resource("acme-support://about")
def about() -> str:
    """Describe the fictional support service."""
    return (
        "Acme Support is a fictional Stage 05 service exposing teaching order, "
        "shipment, invoice, and support-case capabilities."
    )


@mcp.resource("acme-support://guide/{topic}")
def support_guide(topic: str) -> str:
    """Read one support guide by URI."""
    try:
        return read_support_guide(topic)
    except LookupError as exc:
        raise ValueError(str(exc)) from exc


@mcp.prompt()
def prepare_case_summary(order_id: str, audience: str = "customer") -> str:
    """Return a reusable prompt for summarizing a support case."""
    return (
        f"Summarize support evidence for order {order_id} for a {audience}. "
        "Separate verified system facts from policy interpretation, and do not "
        "claim that a refund or support action already happened unless a tool result proves it."
    )


if __name__ == "__main__":
    mcp.run()
