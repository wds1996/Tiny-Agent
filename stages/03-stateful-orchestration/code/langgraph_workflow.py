"""The same report nodes and routes, executed by LangGraph."""
from __future__ import annotations

from operator import add
from typing import Annotated, Any
from typing_extensions import TypedDict

from workflow import ReportNodes, connect_report, initial_state, parse_args, show_result


class ReportState(TypedDict):
    cities: list[str]
    include_fahrenheit: bool
    language: str
    readings: list[dict[str, Any]]
    draft: dict[str, Any] | None
    review: dict[str, Any] | None
    revisions: int
    events: Annotated[list[str], add]
    answer: str | None
    status: str


def state_graph_type():
    try:
        from langgraph.graph import StateGraph
    except ImportError as exc:
        raise RuntimeError("Install stages/03-stateful-orchestration/code/requirements.txt first") from exc
    return StateGraph


def build_graph(**options: Any):
    builder = state_graph_type()(ReportState)
    connect_report(builder, ReportNodes(**options))
    return builder.compile()


def run_stream(graph: Any, state: dict[str, Any], *, show_updates: bool = False,
               recursion_limit: int = 30) -> dict[str, Any]:
    """Consume one run, including its final values; never invoke it a second time."""
    if type(recursion_limit) is not int or recursion_limit < 1:
        raise ValueError("recursion_limit must be a positive integer")
    final = None
    for mode, payload in graph.stream(state, stream_mode=["updates", "values"],
                                       config={"recursion_limit": recursion_limit}):
        if mode == "updates" and show_updates:
            for node, update in payload.items():
                print(node, "updated:", sorted(update) if isinstance(update, dict) else [])
        elif mode == "values":
            final = payload
    if final is None:
        raise RuntimeError("Graph produced no state values")
    return final


def main() -> None:
    args = parse_args()
    graph = build_graph(draft_style=args.draft_style, max_revisions=args.max_revisions)
    state = run_stream(graph, initial_state(args.cities, not args.celsius_only, args.language),
                       show_updates=args.show_updates, recursion_limit=args.max_steps)
    show_result(state)
    if state["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
