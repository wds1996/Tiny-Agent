from operator import add
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


def test_langgraph_default_reducer_overwrites_latest_value():
    class State(TypedDict, total=False):
        value: int

    def first(state: State):
        return {"value": 1}

    def second(state: State):
        return {"value": 2}

    builder = StateGraph(State)
    builder.add_node("first", first)
    builder.add_node("second", second)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)

    result = builder.compile().invoke({})

    assert result["value"] == 2


def test_langgraph_custom_reducer_accumulates_partial_updates():
    class State(TypedDict, total=False):
        events: Annotated[list[str], add]

    def first(state: State):
        return {"events": ["one"]}

    def second(state: State):
        return {"events": ["two"]}

    builder = StateGraph(State)
    builder.add_node("first", first)
    builder.add_node("second", second)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)

    result = builder.compile().invoke({"events": []})

    assert result["events"] == ["one", "two"]


def test_langgraph_conditional_edge_and_stream_updates():
    class State(TypedDict, total=False):
        value: int
        route: str
        answer: str

    def classify(state: State):
        return {"route": "large" if state["value"] >= 10 else "small"}

    def choose(state: State) -> Literal["large", "small"]:
        return "large" if state["route"] == "large" else "small"

    def handle_large(state: State):
        return {"answer": "large"}

    def handle_small(state: State):
        return {"answer": "small"}

    builder = StateGraph(State)
    builder.add_node("classify", classify)
    builder.add_node("large", handle_large)
    builder.add_node("small", handle_small)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        choose,
        {"large": "large", "small": "small"},
    )
    builder.add_edge("large", END)
    builder.add_edge("small", END)
    graph = builder.compile()

    updates = list(graph.stream({"value": 12}, stream_mode="updates"))
    result = graph.invoke({"value": 12})

    assert result["answer"] == "large"
    assert any("classify" in update for update in updates)
    assert any("large" in update for update in updates)
