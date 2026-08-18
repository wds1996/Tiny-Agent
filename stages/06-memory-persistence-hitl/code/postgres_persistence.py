"""Stage 06 optional example: durable checkpoint + long-term Store in Postgres.

Prerequisite:
    export DATABASE_URL='postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable'

Run:
    python -m pip install -e ".[stage06]"
    python stages/06-memory-persistence-hitl/code/postgres_persistence.py

The first run calls setup() to create the required tables. In a managed
production deployment, migrations/setup belong in deployment operations rather
than being silently executed on every request.
"""

import os
import uuid
from typing import TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.postgres import PostgresStore


DB_URI = os.environ.get("DATABASE_URL")
if not DB_URI:
    raise SystemExit("Set DATABASE_URL before running this example.")


class State(TypedDict, total=False):
    count: int


def build_graph(checkpointer):
    def increment(state: State):
        return {"count": state.get("count", 0) + 1}

    builder = StateGraph(State)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=checkpointer)


thread_id = f"stage06-example-{uuid.uuid4()}"
config = {"configurable": {"thread_id": thread_id}}
namespace = ("demo-user", "memories")

with (
    PostgresSaver.from_conn_string(DB_URI) as checkpointer,
    PostgresStore.from_conn_string(DB_URI) as store,
):
    checkpointer.setup()
    store.setup()

    graph = build_graph(checkpointer)
    graph.invoke({"count": 0}, config=config)

    store.put(
        namespace,
        "learning-stage",
        {"text": "The user is studying Tiny-Agent Stage 06."},
    )

    print("checkpoint state:", graph.get_state(config).values)
    print("long-term memory:", store.get(namespace, "learning-stage").value)
