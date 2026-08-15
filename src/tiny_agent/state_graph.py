from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

START = "__start__"
END = "__end__"

State = dict[str, Any]
Node = Callable[[State], Mapping[str, Any] | None]
Router = Callable[[State], str]


@dataclass(frozen=True, slots=True)
class GraphRunResult:
    """Result of one TinyStateGraph execution.

    ``trace`` stores the node names that actually executed. START and END are
    structural sentinels, so they are not included in the trace.
    """

    state: State
    trace: tuple[str, ...]
    steps: int


@dataclass(frozen=True, slots=True)
class _ConditionalEdge:
    router: Router
    destinations: dict[str, str]


class TinyStateGraph:
    """A deliberately small state-graph builder used for teaching.

    It models four ideas that later map directly to LangGraph:

    - shared state;
    - nodes that return partial state updates;
    - fixed edges;
    - conditional edges chosen from application-owned destinations.

    It intentionally does *not* implement reducers, parallel branches,
    persistence, streaming, interrupts, subgraphs, retries, or async execution.
    Those omissions are part of the lesson: a framework becomes useful when the
    orchestration requirements grow beyond this inspectable core.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, str] = {}
        self._conditional_edges: dict[str, _ConditionalEdge] = {}

    def add_node(self, name: str, node: Node) -> "TinyStateGraph":
        if not name or name in {START, END}:
            raise ValueError(f"Invalid node name: {name!r}")
        if name in self._nodes:
            raise ValueError(f"Duplicate node: {name!r}")
        self._nodes[name] = node
        return self

    def add_edge(self, source: str, destination: str) -> "TinyStateGraph":
        self._assert_no_outgoing_edge(source)
        self._edges[source] = destination
        return self

    def add_conditional_edges(
        self,
        source: str,
        router: Router,
        destinations: Mapping[str, str],
    ) -> "TinyStateGraph":
        self._assert_no_outgoing_edge(source)
        if not destinations:
            raise ValueError("Conditional edges require at least one destination")
        self._conditional_edges[source] = _ConditionalEdge(
            router=router,
            destinations=dict(destinations),
        )
        return self

    def compile(self) -> "CompiledTinyStateGraph":
        self._validate()
        return CompiledTinyStateGraph(
            nodes=dict(self._nodes),
            edges=dict(self._edges),
            conditional_edges=dict(self._conditional_edges),
        )

    def _assert_no_outgoing_edge(self, source: str) -> None:
        if source == END:
            raise ValueError("END cannot have outgoing edges")
        if source in self._edges or source in self._conditional_edges:
            raise ValueError(f"Node {source!r} already has an outgoing edge")

    def _validate(self) -> None:
        if START not in self._edges and START not in self._conditional_edges:
            raise ValueError("Graph requires an edge out of START")

        valid_sources = {START, *self._nodes}
        valid_destinations = {END, *self._nodes}

        for source, destination in self._edges.items():
            if source not in valid_sources:
                raise ValueError(f"Unknown edge source: {source!r}")
            if destination not in valid_destinations:
                raise ValueError(f"Unknown edge destination: {destination!r}")

        for source, branch in self._conditional_edges.items():
            if source not in valid_sources:
                raise ValueError(f"Unknown conditional source: {source!r}")
            for destination in branch.destinations.values():
                if destination not in valid_destinations:
                    raise ValueError(
                        f"Unknown conditional destination: {destination!r}"
                    )


class CompiledTinyStateGraph:
    """Executable form of ``TinyStateGraph``."""

    def __init__(
        self,
        *,
        nodes: dict[str, Node],
        edges: dict[str, str],
        conditional_edges: dict[str, _ConditionalEdge],
    ) -> None:
        self._nodes = nodes
        self._edges = edges
        self._conditional_edges = conditional_edges

    def invoke(self, initial_state: Mapping[str, Any], *, max_steps: int = 50) -> GraphRunResult:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")

        state: State = dict(initial_state)
        trace: list[str] = []
        current = self._next_node(START, state)

        while current != END:
            if len(trace) >= max_steps:
                raise RuntimeError(f"Graph exceeded max_steps={max_steps}")

            node = self._nodes[current]
            updates = node(dict(state))
            if updates is not None:
                if not isinstance(updates, Mapping):
                    raise TypeError(
                        f"Node {current!r} must return a mapping or None, "
                        f"got {type(updates).__name__}"
                    )
                state.update(updates)

            trace.append(current)
            current = self._next_node(current, state)

        return GraphRunResult(
            state=state,
            trace=tuple(trace),
            steps=len(trace),
        )

    def _next_node(self, source: str, state: State) -> str:
        branch = self._conditional_edges.get(source)
        if branch is not None:
            route = branch.router(dict(state))
            try:
                return branch.destinations[route]
            except KeyError as exc:
                allowed = sorted(branch.destinations)
                raise RuntimeError(
                    f"Router from {source!r} returned unknown route {route!r}; "
                    f"allowed routes: {allowed}"
                ) from exc

        try:
            return self._edges[source]
        except KeyError as exc:
            raise RuntimeError(f"Node {source!r} has no outgoing edge") from exc
