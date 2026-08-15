"""Stage 03 example 2: the same routing workflow implemented with LangGraph.

Install Stage 03 dependencies first:

    pip install -e ".[stage03]"

Then run:

    python stages/03-stateful-orchestration/code/langgraph_state_graph.py
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class SupportState(TypedDict, total=False):
    request: str
    route: Literal["billing", "technical"]
    answer: str


def classify(state: SupportState):
    text = state["request"].lower()
    if any(word in text for word in ("refund", "charge", "invoice")):
        return {"route": "billing"}
    return {"route": "technical"}


def route_after_classification(
    state: SupportState,
) -> Literal["billing", "technical"]:
    return state["route"]


def billing(state: SupportState):
    return {
        "answer": "Billing workflow received the request: " + state["request"]
    }


def technical(state: SupportState):
    return {
        "answer": "Technical workflow received the request: " + state["request"]
    }


builder = StateGraph(SupportState)
builder.add_node("classify", classify)
builder.add_node("billing", billing)
builder.add_node("technical", technical)

builder.add_edge(START, "classify")
builder.add_conditional_edges(
    "classify",
    route_after_classification,
    {
        "billing": "billing",
        "technical": "technical",
    },
)
builder.add_edge("billing", END)
builder.add_edge("technical", END)

graph = builder.compile()


if __name__ == "__main__":
    initial = {
        "request": "I was charged twice after renewing my subscription."
    }

    print("Final state:")
    print(graph.invoke(initial))

    print("\nState updates:")
    for update in graph.stream(initial, stream_mode="updates"):
        print(update)
