"""The same evidence nodes, executed by an optional real LangGraph runtime."""
from __future__ import annotations
from operator import add
from typing import Annotated

from agentic_rag import RAGNodes, main


def build_graph(nodes: RAGNodes):
    try:
        from langgraph.graph import END, START, StateGraph
        from typing_extensions import TypedDict
    except ImportError as exc:
        raise RuntimeError("Install code/requirements-frameworks.txt for LangGraph") from exc

    class GraphState(TypedDict):
        task: object
        query: str
        query_history: Annotated[list[str], add]
        evidence: list
        selected: tuple
        assessment: object
        searches: int
        rewrites: int
        status: str
        reason: str
        answer: object
        answer_kind: str
        events: Annotated[list[str], add]
        next_node: str

    def bind(method):
        def node(state):
            return method(state)
        return node

    builder = StateGraph(GraphState)
    for name in ("prepare", "search", "assess"):
        builder.add_node(name, bind(getattr(nodes, name)))
    builder.add_node("generate_answer", bind(nodes.answer))
    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", lambda state: state["next_node"],
                                  {"search": "search", "end": END})
    builder.add_conditional_edges("search", lambda state: state["next_node"],
                                  {"assess": "assess", "end": END})
    builder.add_conditional_edges("assess", lambda state: state["next_node"],
                                  {"search": "search", "answer": "generate_answer", "end": END})
    builder.add_edge("generate_answer", END)
    return builder.compile()


if __name__ == "__main__":
    main(engine="langgraph")
