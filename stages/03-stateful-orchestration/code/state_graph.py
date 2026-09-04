from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

START = "__start__"
END = "__end__"

State = dict[str, Any]
Node = Callable[[State], Mapping[str, Any] | None]
Router = Callable[[State], str]
Reducer = Callable[[Any, Any], Any]


@dataclass(frozen=True, slots=True)
class RunResult:
    state: State
    trace: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConditionalEdge:
    router: Router
    destinations: dict[str, str]


class MiniStateGraph:
    """A tiny state-graph runtime for learning graph semantics."""

    def __init__(self, *, reducers: Mapping[str, Reducer] | None = None) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, ConditionalEdge] = {}
        self._reducers = dict(reducers or {})

    def add_node(self, name: str, node: Node) -> None:
        if not name or name in {START, END}:
            raise ValueError(f"invalid node name: {name!r}")
        if name in self._nodes:
            raise ValueError(f"duplicate node: {name!r}")
        self._nodes[name] = node

    def add_edge(self, source: str, destination: str) -> None:
        self._ensure_no_outgoing_edge(source)
        self._edges[source] = destination

    def add_conditional_edges(
        self,
        source: str,
        router: Router,
        destinations: Mapping[str, str],
    ) -> None:
        self._ensure_no_outgoing_edge(source)
        if not destinations:
            raise ValueError("conditional edges need at least one destination")
        self._conditional_edges[source] = ConditionalEdge(
            router=router,
            destinations=dict(destinations),
        )

    def compile(self) -> "CompiledMiniStateGraph":
        self._validate_topology()
        return CompiledMiniStateGraph(
            nodes=dict(self._nodes),
            edges=dict(self._edges),
            conditional_edges=dict(self._conditional_edges),
            reducers=dict(self._reducers),
        )

    def _ensure_no_outgoing_edge(self, source: str) -> None:
        if source == END:
            raise ValueError("END cannot have an outgoing edge")
        if source in self._edges or source in self._conditional_edges:
            raise ValueError(f"{source!r} already has an outgoing edge")

    def _validate_topology(self) -> None:
        if START not in self._edges and START not in self._conditional_edges:
            raise ValueError("graph needs an edge out of START")

        valid_sources = {START, *self._nodes}
        valid_destinations = {END, *self._nodes}

        for source, destination in self._edges.items():
            if source not in valid_sources:
                raise ValueError(f"unknown edge source: {source!r}")
            if destination not in valid_destinations:
                raise ValueError(f"unknown edge destination: {destination!r}")

        for source, branch in self._conditional_edges.items():
            if source not in valid_sources:
                raise ValueError(f"unknown conditional source: {source!r}")
            for destination in branch.destinations.values():
                if destination not in valid_destinations:
                    raise ValueError(
                        f"unknown conditional destination: {destination!r}"
                    )

        for name in self._nodes:
            if name not in self._edges and name not in self._conditional_edges:
                raise ValueError(f"node {name!r} has no outgoing edge")


class CompiledMiniStateGraph:
    def __init__(
        self,
        *,
        nodes: dict[str, Node],
        edges: dict[str, str],
        conditional_edges: dict[str, ConditionalEdge],
        reducers: dict[str, Reducer],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._conditional_edges = conditional_edges
        self._reducers = reducers

    def invoke(
        self,
        initial_state: Mapping[str, Any],
        *,
        max_steps: int = 30,
    ) -> RunResult:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")

        state = dict(initial_state)
        trace: list[str] = []
        current = self._next_node(START, state)

        while current != END:
            if len(trace) >= max_steps:
                raise RuntimeError(f"graph exceeded max_steps={max_steps}")

            update = self._nodes[current](dict(state))
            if update is not None:
                if not isinstance(update, Mapping):
                    raise TypeError(
                        f"node {current!r} must return a mapping or None"
                    )
                self._apply_update(state, update)

            trace.append(current)
            current = self._next_node(current, state)

        return RunResult(state=state, trace=tuple(trace))

    def _apply_update(self, state: State, update: Mapping[str, Any]) -> None:
        for key, right in update.items():
            reducer = self._reducers.get(key)
            if reducer is None or key not in state:
                state[key] = right
            else:
                state[key] = reducer(state[key], right)

    def _next_node(self, source: str, state: State) -> str:
        branch = self._conditional_edges.get(source)
        if branch is not None:
            route = branch.router(dict(state))
            try:
                return branch.destinations[route]
            except KeyError as exc:
                allowed = ", ".join(sorted(branch.destinations))
                raise RuntimeError(
                    f"router from {source!r} returned {route!r}; "
                    f"allowed routes: {allowed}"
                ) from exc

        try:
            return self._edges[source]
        except KeyError as exc:
            raise RuntimeError(f"{source!r} has no outgoing edge") from exc


def append_events(left: list[str], right: list[str]) -> list[str]:
    return [*left, *right]


def classify(state: State) -> dict[str, Any]:
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


def draft(state: State) -> dict[str, Any]:
    category = state["category"]
    response = {
        "billing": "I can help review the billing issue.",
        "technical": "I can help troubleshoot the access issue.",
        "general": "I can help with that request.",
    }[category]
    return {
        "draft": response,
        "events": ["drafted first response"],
    }


def review(state: State) -> dict[str, Any]:
    needs_revision = state.get("revisions", 0) == 0
    return {
        "review": "revise" if needs_revision else "accept",
        "events": [
            "review requested one revision"
            if needs_revision
            else "review accepted response"
        ],
    }


def revise(state: State) -> dict[str, Any]:
    return {
        "draft": state["draft"] + " I will keep the next step specific.",
        "revisions": state.get("revisions", 0) + 1,
        "events": ["revised response"],
    }


def finish(state: State) -> dict[str, Any]:
    return {
        "answer": state["draft"],
        "events": ["finished workflow"],
    }


def route_after_review(state: State) -> str:
    return state["review"]


def build_support_graph() -> CompiledMiniStateGraph:
    builder = MiniStateGraph(reducers={"events": append_events})
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


def main() -> None:
    graph = build_support_graph()
    result = graph.invoke(
        {
            "request": "I was charged twice and need a refund.",
            "revisions": 0,
            "events": [],
        }
    )

    print("trace:", " -> ".join(result.trace))
    print("answer:", result.state["answer"])
    print("events:")
    for event in result.state["events"]:
        print("-", event)


if __name__ == "__main__":
    main()
