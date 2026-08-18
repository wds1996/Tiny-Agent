"""Stage 06 example 4: durable checkpoints survive saver recreation.

Run:
    python -m pip install -e ".[stage06]"
    python stages/06-memory-persistence-hitl/code/sqlite_durable_checkpoint.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph


class CounterState(TypedDict, total=False):
    count: int


def build_graph(checkpointer):
    def increment(state: CounterState):
        return {"count": state.get("count", 0) + 1}

    builder = StateGraph(CounterState)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=checkpointer)


with TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "checkpoints.sqlite"
    config = {"configurable": {"thread_id": "durable-demo"}}

    print("process A: write checkpoint")
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_graph(saver)
        graph.invoke({"count": 0}, config=config)
        print(graph.get_state(config).values)

    print("\nprocess B: open a fresh saver against the same file")
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        graph = build_graph(saver)
        print(graph.get_state(config).values)

    print("\nThe Python objects were recreated; the checkpoint lived in SQLite.")
