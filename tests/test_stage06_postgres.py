from __future__ import annotations

import os
import uuid
from typing import TypedDict

import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.postgres import PostgresStore


POSTGRES_URI = os.environ.get("TEST_POSTGRES_URI")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URI,
    reason="TEST_POSTGRES_URI is required for Stage 06 Postgres integration tests",
)


class CounterState(TypedDict, total=False):
    count: int


def build_counter_graph(checkpointer):
    def increment(state: CounterState):
        return {"count": state.get("count", 0) + 1}

    builder = StateGraph(CounterState)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=checkpointer)


def test_postgres_checkpointer_survives_connection_recreation():
    assert POSTGRES_URI is not None
    thread_id = f"stage06-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    with PostgresSaver.from_conn_string(POSTGRES_URI) as first_saver:
        first_saver.setup()
        first_graph = build_counter_graph(first_saver)
        first_graph.invoke({"count": 0}, config=config)
        assert first_graph.get_state(config).values["count"] == 1

    with PostgresSaver.from_conn_string(POSTGRES_URI) as second_saver:
        second_graph = build_counter_graph(second_saver)
        assert second_graph.get_state(config).values["count"] == 1


def test_postgres_store_persists_cross_thread_memory():
    assert POSTGRES_URI is not None
    owner = f"user-{uuid.uuid4()}"
    namespace = (owner, "memories")
    key = "preferred-style"

    with PostgresStore.from_conn_string(POSTGRES_URI) as first_store:
        first_store.setup()
        first_store.put(
            namespace,
            key,
            {"text": "Prefer concise explanations with runnable examples."},
        )

    with PostgresStore.from_conn_string(POSTGRES_URI) as second_store:
        item = second_store.get(namespace, key)
        assert item is not None
        assert item.value["text"].startswith("Prefer concise")
