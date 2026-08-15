from typing import TypedDict

from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


def test_langgraph_stream_exposes_node_updates():
    class State(TypedDict, total=False):
        value: int

    def increment(state: State):
        return {"value": state["value"] + 1}

    builder = StateGraph(State)
    builder.add_node("increment", increment)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    graph = builder.compile()

    updates = list(graph.stream({"value": 1}, stream_mode="updates"))

    assert updates
    assert any("increment" in update for update in updates)
    assert graph.invoke({"value": 1})["value"] == 2


def test_langgraph_interrupt_can_resume_same_thread():
    class State(TypedDict, total=False):
        action: str
        approved: bool
        status: str

    def approval(state: State):
        decision = interrupt({"action": state["action"]})
        return {"approved": bool(decision)}

    def finish(state: State):
        return {"status": "approved" if state["approved"] else "rejected"}

    builder = StateGraph(State)
    builder.add_node("approval", approval)
    builder.add_node("finish", finish)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", "finish")
    builder.add_edge("finish", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "test-approval"}}
    paused = graph.invoke({"action": "deploy"}, config=config)

    assert "__interrupt__" in paused
    assert paused["__interrupt__"][0].value == {"action": "deploy"}

    resumed = graph.invoke(Command(resume=False), config=config)

    assert resumed["approved"] is False
    assert resumed["status"] == "rejected"


def test_langchain_tool_and_messages_preserve_familiar_tool_call_concepts():
    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers."""
        return a * b

    human = HumanMessage(content="What is 6 * 7?")
    tool_result = ToolMessage(content="42", tool_call_id="call_1")

    assert human.content == "What is 6 * 7?"
    assert tool_result.tool_call_id == "call_1"
    assert multiply.name == "multiply"
    assert multiply.invoke({"a": 6, "b": 7}) == 42
