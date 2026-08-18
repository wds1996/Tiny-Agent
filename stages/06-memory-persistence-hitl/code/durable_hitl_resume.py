"""Stage 06 example 6: pause, recreate runtime objects, then resume.

Run:
    python -m pip install -e ".[stage06]"
    python stages/06-memory-persistence-hitl/code/durable_hitl_resume.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from tiny_agent import ApprovalDecision, ApprovalRequest, resolve_approval


class State(TypedDict, total=False):
    action: str
    arguments: dict[str, Any]
    approved_arguments: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "executed"]


def build_graph(checkpointer):
    def review(state: State):
        request = ApprovalRequest(
            action=state["action"],
            arguments=state["arguments"],
            reason="Production deployment needs a human review gate.",
            risk="critical",
        )
        raw = interrupt(request.to_interrupt_payload())
        resolution = resolve_approval(request, ApprovalDecision.from_payload(raw))
        if not resolution.approved:
            return {"status": "rejected"}
        return {
            "status": "approved",
            "approved_arguments": resolution.arguments,
        }

    def route(state: State) -> Literal["execute", "stop"]:
        return "execute" if state["status"] == "approved" else "stop"

    def execute(state: State):
        # No real deployment here. The example demonstrates the durable boundary.
        return {"status": "executed"}

    builder = StateGraph(State)
    builder.add_node("review", review)
    builder.add_node("execute", execute)
    builder.add_edge(START, "review")
    builder.add_conditional_edges(
        "review",
        route,
        {"execute": "execute", "stop": END},
    )
    builder.add_edge("execute", END)
    return builder.compile(checkpointer=checkpointer)


with TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "durable-hitl.sqlite"
    config = {"configurable": {"thread_id": "release-2026-08"}}

    print("runtime A: run until the human-review interrupt")
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_graph(saver)
        paused = graph.invoke(
            {
                "action": "deploy_release",
                "arguments": {"release": "v0.6.0", "environment": "production"},
                "status": "pending",
            },
            config=config,
        )
        print(paused["__interrupt__"][0].value)

    print("\nruntime A is gone. SQLite still owns the checkpoint.")

    print("\nruntime B: recreate graph + saver and resume the same thread")
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_graph(saver)
        resumed = graph.invoke(
            Command(resume={"outcome": "approve", "feedback": "Reviewed by operator."}),
            config=config,
        )
        print("final status:", resumed["status"])
