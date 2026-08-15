import pytest

from tiny_agent.state_graph import END, START, TinyStateGraph


def test_tiny_state_graph_runs_fixed_and_conditional_edges():
    builder = TinyStateGraph()

    def classify(state):
        return {"kind": "large" if state["value"] >= 10 else "small"}

    def handle_large(state):
        return {"answer": state["value"] * 2}

    def handle_small(state):
        return {"answer": state["value"] + 1}

    builder.add_node("classify", classify)
    builder.add_node("large", handle_large)
    builder.add_node("small", handle_small)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        lambda state: state["kind"],
        {"large": "large", "small": "small"},
    )
    builder.add_edge("large", END)
    builder.add_edge("small", END)

    graph = builder.compile()
    result = graph.invoke({"value": 12})

    assert result.state == {"value": 12, "kind": "large", "answer": 24}
    assert result.trace == ("classify", "large")
    assert result.steps == 2


def test_tiny_state_graph_rejects_unknown_conditional_route():
    builder = TinyStateGraph()
    builder.add_node("route", lambda state: {"route": "missing"})
    builder.add_edge(START, "route")
    builder.add_conditional_edges(
        "route",
        lambda state: state["route"],
        {"known": END},
    )
    graph = builder.compile()

    with pytest.raises(RuntimeError, match="unknown route"):
        graph.invoke({})


def test_tiny_state_graph_enforces_step_budget_on_cycles():
    builder = TinyStateGraph()
    builder.add_node("tick", lambda state: {"count": state.get("count", 0) + 1})
    builder.add_edge(START, "tick")
    builder.add_edge("tick", "tick")
    graph = builder.compile()

    with pytest.raises(RuntimeError, match="max_steps=3"):
        graph.invoke({}, max_steps=3)


def test_tiny_state_graph_validates_topology_before_execution():
    builder = TinyStateGraph()
    builder.add_node("orphan", lambda state: {})

    with pytest.raises(ValueError, match="edge out of START"):
        builder.compile()


def test_node_must_return_mapping_or_none():
    builder = TinyStateGraph()
    builder.add_node("bad", lambda state: "not-an-update")
    builder.add_edge(START, "bad")
    builder.add_edge("bad", END)
    graph = builder.compile()

    with pytest.raises(TypeError, match="mapping or None"):
        graph.invoke({})
