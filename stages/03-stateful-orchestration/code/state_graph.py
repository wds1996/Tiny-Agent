"""A sequential, in-memory state graph; not a replacement for LangGraph."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterator

START = "__start__"
END = "__end__"
State = dict[str, Any]
Node = Callable[[State], Mapping[str, Any]]
Router = Callable[[State], str]
Reducer = Callable[[Any, Any], Any]


def append_events(left: list, right: list) -> list:
    return [*left, *right]


def merge_update(state: Mapping[str, Any], update: Mapping[str, Any],
                 reducers: Mapping[str, Reducer]) -> State:
    """Stage a new snapshot; a failed reducer does not partially update state."""
    if not isinstance(update, Mapping) or any(not isinstance(k, str) for k in update):
        raise TypeError("A node must return a mapping with string keys")
    candidate = deepcopy(dict(state))
    for key, value in update.items():
        right = deepcopy(value)
        reducer = reducers.get(key)
        candidate[key] = reducer(candidate[key], right) if reducer and key in candidate else right
    return deepcopy(candidate)


@dataclass(frozen=True)
class StepSnapshot:
    node: str
    update: State
    state: State


@dataclass(frozen=True)
class RunResult:
    state: State
    trace: tuple[str, ...]
    steps: tuple[StepSnapshot, ...]


class GraphExecutionError(RuntimeError):
    def __init__(self, message: str, *, node: str, state: State, trace: list[str]) -> None:
        super().__init__(message)
        self.node = node
        self.state = deepcopy(state)
        self.trace = tuple(trace)


class GraphLimitError(GraphExecutionError):
    pass


class MiniStateGraph:
    def __init__(self, *, reducers: Mapping[str, Reducer] | None = None) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, str] = {}
        self.branches: dict[str, tuple[Router, dict[str, str]]] = {}
        self.reducers = dict(reducers or {})
        if not all(callable(reducer) for reducer in self.reducers.values()):
            raise TypeError("Reducers must be callable")

    def add_node(self, name: str, node: Node) -> None:
        if not isinstance(name, str) or not name.strip() or name in {START, END}:
            raise ValueError("Invalid node name")
        if name in self.nodes or not callable(node):
            raise ValueError("Duplicate node or non-callable node")
        self.nodes[name] = node

    def _check_source(self, source: str) -> None:
        if source == END or source in self.edges or source in self.branches:
            raise ValueError("This sequential graph permits one outgoing rule per source")

    def add_edge(self, source: str, destination: str) -> None:
        self._check_source(source)
        self.edges[source] = destination

    def add_conditional_edges(self, source: str, router: Router,
                              destinations: Mapping[str, str]) -> None:
        self._check_source(source)
        if not callable(router) or not destinations:
            raise ValueError("A conditional edge needs a router and destinations")
        if any(not isinstance(k, str) or not k for k in destinations):
            raise ValueError("Route labels must be nonempty strings")
        self.branches[source] = (router, dict(destinations))

    def compile(self) -> CompiledMiniStateGraph:
        sources = {START, *self.nodes}
        targets = {END, *self.nodes}
        adjacency = {source: [target] for source, target in self.edges.items()}
        adjacency.update({source: list(branch[1].values()) for source, branch in self.branches.items()})
        if START not in adjacency:
            raise ValueError("Missing START edge")
        if set(adjacency) != sources:
            raise ValueError("Unknown source or node without an outgoing rule")
        if any(target not in targets for values in adjacency.values() for target in values):
            raise ValueError("Unknown edge destination")

        def reachable(start: str) -> set[str]:
            seen: set[str] = set()
            todo = [start]
            while todo:
                current = todo.pop()
                if current not in seen:
                    seen.add(current)
                    todo.extend(adjacency.get(current, []))
            return seen

        if not set(self.nodes) <= reachable(START):
            raise ValueError("Unreachable node")
        if any(END not in reachable(source) for source in sources):
            raise ValueError("Every source needs a possible path to END")
        # Freeze routing tables, not callable internals or external resources.
        return CompiledMiniStateGraph(
            dict(self.nodes), dict(self.edges),
            {key: (fn, dict(paths)) for key, (fn, paths) in self.branches.items()},
            dict(self.reducers),
        )


class CompiledMiniStateGraph:
    def __init__(self, nodes: dict[str, Node], edges: dict[str, str],
                 branches: dict[str, tuple[Router, dict[str, str]]],
                 reducers: dict[str, Reducer]) -> None:
        self.nodes, self.edges = nodes, edges
        self.branches, self.reducers = branches, reducers

    def _next(self, source: str, state: State) -> str:
        if source not in self.branches:
            return self.edges[source]
        router, destinations = self.branches[source]
        route = router(deepcopy(state))
        if not isinstance(route, str) or route not in destinations:
            raise ValueError("Router returned an undeclared route")
        return destinations[route]

    def stream(self, initial_state: Mapping[str, Any], *, max_steps: int = 30) -> Iterator[StepSnapshot]:
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if not isinstance(initial_state, Mapping):
            raise TypeError("initial_state must be a mapping")
        state = deepcopy(dict(initial_state))
        trace: list[str] = []
        source = START
        while True:
            try:
                current = self._next(source, state)
            except Exception as exc:
                raise GraphExecutionError("Routing failed", node=source, state=state, trace=trace) from exc
            if current == END:
                return
            if len(trace) >= max_steps:
                raise GraphLimitError(f"Graph exceeded max_steps={max_steps}",
                                      node=current, state=state, trace=trace)
            try:
                update = self.nodes[current](deepcopy(state))
                candidate = merge_update(state, update, self.reducers)
            except Exception as exc:
                raise GraphExecutionError("Node or merge failed", node=current,
                                          state=state, trace=trace) from exc
            state = candidate
            trace.append(current)
            yield StepSnapshot(current, deepcopy(dict(update)), deepcopy(state))
            source = current

    def invoke(self, initial_state: Mapping[str, Any], *, max_steps: int = 30) -> RunResult:
        steps = tuple(self.stream(initial_state, max_steps=max_steps))
        state = deepcopy(steps[-1].state if steps else dict(initial_state))
        return RunResult(state, tuple(step.node for step in steps), steps)


def main() -> None:
    from workflow import build_mini_workflow, initial_state, parse_args, show_result
    from state_graph import GraphExecutionError as EngineError
    args = parse_args()
    graph = build_mini_workflow(draft_style=args.draft_style, max_revisions=args.max_revisions)
    try:
        result = graph.invoke(initial_state(args.cities, not args.celsius_only, args.language),
                              max_steps=args.max_steps)
    except EngineError as exc:
        print("stopped before:", exc.node, "completed nodes:", exc.trace)
        raise SystemExit(1) from None
    if args.show_updates:
        for step in result.steps:
            print(step.node, "updated:", sorted(step.update))
    show_result(result.state)
    if result.state["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
