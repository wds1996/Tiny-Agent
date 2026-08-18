from __future__ import annotations

from tempfile import TemporaryDirectory
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, interrupt

from tiny_agent import (
    ApprovalDecision,
    ApprovalRequest,
    resolve_approval,
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


def test_checkpointer_is_thread_scoped():
    checkpointer = InMemorySaver()
    graph = build_counter_graph(checkpointer)

    thread_a = {"configurable": {"thread_id": "thread-a"}}
    thread_b = {"configurable": {"thread_id": "thread-b"}}

    graph.invoke({"count": 0}, config=thread_a)

    assert graph.get_state(thread_a).values["count"] == 1
    assert graph.get_state(thread_b).values == {}


def test_sqlite_checkpoint_survives_new_saver_instance():
    with TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/checkpoints.sqlite"
        config = {"configurable": {"thread_id": "durable-thread"}}

        with SqliteSaver.from_conn_string(path) as first_saver:
            first_graph = build_counter_graph(first_saver)
            first_graph.invoke({"count": 0}, config=config)
            assert first_graph.get_state(config).values["count"] == 1

        # Re-open the same SQLite file with a completely new saver/graph pair.
        # This models a fresh process reading durable execution state.
        with SqliteSaver.from_conn_string(path) as second_saver:
            second_graph = build_counter_graph(second_saver)
            assert second_graph.get_state(config).values["count"] == 1


def test_long_term_store_is_namespaced_across_threads():
    store = InMemoryStore()
    user_namespace = ("user-7", "memories")
    other_user_namespace = ("user-8", "memories")

    store.put(
        user_namespace,
        "preferred-language",
        {"text": "The user prefers Chinese explanations."},
    )

    assert store.get(user_namespace, "preferred-language").value["text"].startswith(
        "The user prefers"
    )
    assert store.get(other_user_namespace, "preferred-language") is None


class ApprovalState(TypedDict, total=False):
    action: str
    arguments: dict[str, Any]
    approved_arguments: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "executed"]


def build_approval_graph(checkpointer):
    def review(state: ApprovalState):
        request = ApprovalRequest(
            action=state["action"],
            arguments=state["arguments"],
            reason="This action has an external side effect.",
            risk="high",
        )
        raw_decision = interrupt(request.to_interrupt_payload())
        decision = ApprovalDecision.from_payload(raw_decision)
        resolution = resolve_approval(request, decision)

        if not resolution.approved:
            return {"status": "rejected"}
        return {
            "status": "approved",
            "approved_arguments": resolution.arguments,
        }

    def route(state: ApprovalState) -> Literal["execute", "end"]:
        return "execute" if state["status"] == "approved" else "end"

    def execute(state: ApprovalState):
        # Test-only: no real external side effect.
        return {"status": "executed"}

    builder = StateGraph(ApprovalState)
    builder.add_node("review", review)
    builder.add_node("execute", execute)
    builder.add_edge(START, "review")
    builder.add_conditional_edges(
        "review",
        route,
        {"execute": "execute", "end": END},
    )
    builder.add_edge("execute", END)
    return builder.compile(checkpointer=checkpointer)


def test_hitl_edit_changes_arguments_before_execution():
    graph = build_approval_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "approval-edit"}}

    paused = graph.invoke(
        {
            "action": "send_email",
            "arguments": {"to": "alice@example.com", "subject": "Draft"},
            "status": "pending",
        },
        config=config,
    )

    assert paused["__interrupt__"][0].value["action"] == "send_email"

    resumed = graph.invoke(
        Command(
            resume={
                "outcome": "edit",
                "edited_arguments": {
                    "to": "bob@example.com",
                    "subject": "Reviewed draft",
                },
            }
        ),
        config=config,
    )

    assert resumed["status"] == "executed"
    assert resumed["approved_arguments"]["to"] == "bob@example.com"


def test_hitl_reject_never_enters_execution_node():
    graph = build_approval_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "approval-reject"}}

    graph.invoke(
        {
            "action": "delete_record",
            "arguments": {"record_id": "prod-7"},
            "status": "pending",
        },
        config=config,
    )

    resumed = graph.invoke(
        Command(resume={"outcome": "reject", "feedback": "Too risky."}),
        config=config,
    )

    assert resumed["status"] == "rejected"
    assert "approved_arguments" not in resumed
