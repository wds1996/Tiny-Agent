"""Stage 03 example 1: explicit graph orchestration without LangGraph.

Run from the repository root:

    python stages/03-stateful-orchestration/code/handwritten_state_graph.py

The example intentionally uses deterministic rules. The lesson is state and
control flow, not model quality.
"""

from tiny_agent.state_graph import END, START, TinyStateGraph


def classify(state):
    text = state["request"].lower()
    if any(word in text for word in ("refund", "charge", "invoice")):
        route = "billing"
    else:
        route = "technical"
    return {"route": route}


def billing(state):
    return {
        "answer": (
            "Billing workflow received the request: " + state["request"]
        )
    }


def technical(state):
    return {
        "answer": (
            "Technical workflow received the request: " + state["request"]
        )
    }


builder = TinyStateGraph()
builder.add_node("classify", classify)
builder.add_node("billing", billing)
builder.add_node("technical", technical)

builder.add_edge(START, "classify")
builder.add_conditional_edges(
    "classify",
    lambda state: state["route"],
    {
        "billing": "billing",
        "technical": "technical",
    },
)
builder.add_edge("billing", END)
builder.add_edge("technical", END)

graph = builder.compile()


if __name__ == "__main__":
    result = graph.invoke(
        {"request": "I was charged twice after renewing my subscription."}
    )

    print("Final state:")
    print(result.state)
    print("\nExecuted nodes:")
    print(" -> ".join(result.trace))
