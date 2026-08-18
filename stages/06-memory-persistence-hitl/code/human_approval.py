"""Stage 06 example 5: approve / edit / reject with LangGraph interrupt.

Run:
    python -m pip install -e ".[stage06]"
    python stages/06-memory-persistence-hitl/code/human_approval.py
"""

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from tiny_agent import ApprovalDecision, ApprovalRequest, resolve_approval


class State(TypedDict, total=False):
    action: str
    arguments: dict[str, Any]
    approved_arguments: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "executed"]


def review(state: State):
    request = ApprovalRequest(
        action=state["action"],
        arguments=state["arguments"],
        reason="This action has an external side effect.",
        risk="high",
    )

    raw_decision = interrupt(request.to_interrupt_payload())
    decision = ApprovalDecision.from_payload(raw_decision)
    resolution = resolve_approval(request, decision)

    if not resolution.approved:
        return {"status": "rejected"}

    return {
        "status": "approved",
        "approved_arguments": resolution.arguments,
    }


def route(state: State) -> Literal["execute", "stop"]:
    return "execute" if state["status"] == "approved" else "stop"


def execute(state: State):
    # Teaching only: print instead of performing a real side effect.
    print("executing with reviewed arguments:", state["approved_arguments"])
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

graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "approval-demo"}}

paused = graph.invoke(
    {
        "action": "send_email",
        "arguments": {
            "to": "alice@example.com",
            "subject": "Unreviewed subject",
        },
        "status": "pending",
    },
    config=config,
)

print("review request:")
print(paused["__interrupt__"][0].value)

# Pretend a reviewer edits the arguments before approving execution.
resumed = graph.invoke(
    Command(
        resume={
            "outcome": "edit",
            "edited_arguments": {
                "to": "alice@example.com",
                "subject": "Reviewed subject",
            },
            "feedback": "Subject was corrected before sending.",
        }
    ),
    config=config,
)

print("final status:", resumed["status"])
