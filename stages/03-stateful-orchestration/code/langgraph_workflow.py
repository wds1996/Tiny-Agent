from __future__ import annotations

from operator import add
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class SupportState(TypedDict, total=False):
    request: str
    category: str
    draft: str
    review: str
    revisions: int
    events: Annotated[list[str], add]
    answer: str


def classify(state: SupportState) -> dict:
    request = state["request"].lower()
    if "refund" in request or "charged" in request:
        category = "billing"
    elif "password" in request or "login" in request:
        category = "technical"
    else:
        category = "general"

    return {
        "category": category,
        "events": [f"classified as {category}"],
    }


def draft(state: SupportState) -> dict:
    response = {
        "billing": "I can help review the billing issue.",
        "technical": "I can help troubleshoot the access issue.",
        "general": "I can help with that request.",
    }[state["category"]]

    return {
        "draft": response,
        "events": ["drafted first response"],
    }


def review(state: SupportState) -> dict:
    needs_revision = state.get("revisions", 0) == 0
    return {
        "review": "revise" if needs_revision else "accept",
        "events": [
            "review requested one revision"
            if needs_revision
            else "review accepted response"
        ],
    }


def route_after_review(state: SupportState) -> Literal["revise", "accept"]:
    return "revise" if state["review"] == "revise" else "accept"


def revise(state: SupportState) -> dict:
    return {
        "draft": state["draft"] + " I will keep the next step specific.",
        "revisions": state.get("revisions", 0) + 1,
        "events": ["revised response"],
    }


def finish(state: SupportState) -> dict:
    return {
        "answer": state["draft"],
        "events": ["finished workflow"],
    }


def build_graph():
    builder = StateGraph(SupportState)

    builder.add_node("classify", classify)
    builder.add_node("draft", draft)
    builder.add_node("review", review)
    builder.add_node("revise", revise)
    builder.add_node("finish", finish)

    builder.add_edge(START, "classify")
    builder.add_edge("classify", "draft")
    builder.add_edge("draft", "review")
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {
            "revise": "revise",
            "accept": "finish",
        },
    )
    builder.add_edge("revise", "review")
    builder.add_edge("finish", END)

    return builder.compile()


def initial_state() -> SupportState:
    return {
        "request": "I was charged twice and need a refund.",
        "revisions": 0,
        "events": [],
    }


def main() -> None:
    graph = build_graph()

    print("=== node updates ===")
    for update in graph.stream(
        initial_state(),
        stream_mode="updates",
        config={"recursion_limit": 20},
    ):
        print(update)

    print("\n=== final state ===")
    result = graph.invoke(
        initial_state(),
        config={"recursion_limit": 20},
    )
    print("answer:", result["answer"])
    print("events:")
    for event in result["events"]:
        print("-", event)


if __name__ == "__main__":
    main()
