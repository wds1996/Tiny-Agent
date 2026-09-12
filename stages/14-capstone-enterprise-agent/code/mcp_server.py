"""Run as a separate process. Business data is real local SQLite; every record is fictional."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
from business import Commerce
from domain import profile


def build_server(root: Path, profile_name: str):
    from mcp.server import MCPServer
    server=MCPServer('Qinghe demonstration commerce')
    commerce=Commerce(root,profile(profile_name))

    @server.tool()
    def list_orders() -> dict[str, Any]:
        """List only orders accessible to the customer bound to this server process."""
        return commerce.list_orders()

    @server.tool()
    def get_order(order_id: str) -> dict[str, Any]:
        """Read authoritative order, delivery date, paid cents and warehouse return receipt."""
        return commerce.get_order(order_id)

    @server.tool()
    def get_shipment(order_id: str) -> dict[str, Any]:
        """Read fictional shipment events for an accessible order; never promise an arrival."""
        return commerce.get_shipment(order_id)

    @server.tool()
    def get_invoice(order_id: str) -> dict[str, Any]:
        """Read the accessible order's simulated original invoice, not refundable balance."""
        return commerce.get_invoice(order_id)

    @server.tool()
    def get_product(sku: str) -> dict[str, Any]:
        """Read the public demonstration catalog, including category and warranty duration."""
        return commerce.get_product(sku)

    @server.tool()
    def get_ticket(ticket_id: str) -> dict[str, Any]:
        """Read a service ticket owned by this customer."""
        return commerce.get_ticket(ticket_id)

    @server.tool()
    def create_ticket(order_id: str, summary: str, idempotency_key: str) -> dict[str, Any]:
        """Create a simulated service ticket. A Host-only write, not a model-exposed tool."""
        return commerce.create_ticket(order_id,summary,idempotency_key)

    @server.tool()
    def execute_refund(approval_id: str) -> dict[str, Any]:
        """Execute ONLY an existing approved exact action; returns a SIMULATED receipt."""
        return commerce.execute_refund(approval_id)

    @server.resource('qinghe://service-scope')
    def scope() -> str:
        return 'Fictional commerce. Identity is fixed by Host launch configuration. No real payment gateway.'
    return server


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-dir',type=Path,required=True)
    parser.add_argument('--profile',required=True)
    args=parser.parse_args()
    build_server(args.state_dir,args.profile).run()


if __name__=='__main__': main()
