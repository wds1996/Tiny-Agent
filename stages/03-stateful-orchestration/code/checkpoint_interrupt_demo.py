"""Stage 03 example 4: checkpointing + human approval with LangGraph.

This is a local teaching demo. ``InMemorySaver`` is intentionally used only for
learning/testing; production persistence should use a durable checkpointer.

Run:

    pip install -e ".[stage03]"
    python stages/03-stateful-orchestration/code/checkpoint_interrupt_demo.py
"""

from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ApprovalState(TypedDict, total=False):
    action: str
    approved: bool
    status: Literal["pending", "approved", "rejected"]


def approval_node(state: ApprovalState):
    # LangGraph can persist the graph state before pausing. The payload must be
    # JSON-serializable because it is surfaced outside the graph.
    decision = interrupt(
        {
            "question": "Approve this action?",
            "action": state["action"],
        }
    )
    return {"approved": bool(decision)}


def route_after_approval(
    state: ApprovalState,
) -> Literal["execute", "cancel"]:
    return "execute" if state["approved"] else "cancel"


def execute_node(state: ApprovalState):
    # This example does not perform a real side effect. Real side effects must
    # be designed carefully because an interrupted node can restart on resume.
    return {"status": "approved"}


def cancel_node(state: ApprovalState):
    return {"status": "rejected"}


builder = StateGraph(ApprovalState)
builder.add_node("approval", approval_node)
builder.add_node("execute", execute_node)
builder.add_node("cancel", cancel_node)
builder.add_edge(START, "approval")
builder.add_conditional_edges(
    "approval",
    route_after_approval,
    {
        "execute": "execute",
        "cancel": "cancel",
    },
)
builder.add_edge("execute", END)
builder.add_edge("cancel", END)

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "approval-demo-1"}}

    paused = graph.invoke(
        {
            "action": "Deploy release candidate to production",
            "status": "pending",
        },
        config=config,
    )

    print("Paused graph output:")
    print(paused)
    print("\nInterrupt payload:")
    print(paused["__interrupt__"][0].value)

    resumed = graph.invoke(Command(resume=True), config=config)

    print("\nResumed graph output:")
    print(resumed)
    print("\nFinal status:")
    print(resumed["status"])
