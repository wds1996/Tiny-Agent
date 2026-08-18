"""Stage 06 example 2: thread-scoped short-term memory with a checkpointer.

Run:
    python -m pip install -e ".[stage06]"
    python stages/06-memory-persistence-hitl/code/thread_short_term_memory.py
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


def acknowledge(state: MessagesState):
    last = state["messages"][-1]
    return {
        "messages": [
            {
                "role": "assistant",
                "content": f"ack: {last.content}",
            }
        ]
    }


builder = StateGraph(MessagesState)
builder.add_node("acknowledge", acknowledge)
builder.add_edge(START, "acknowledge")
builder.add_edge("acknowledge", END)

graph = builder.compile(checkpointer=InMemorySaver())

thread_a = {"configurable": {"thread_id": "thread-a"}}
thread_b = {"configurable": {"thread_id": "thread-b"}}

# Two invocations with the same thread ID accumulate the thread's state.
graph.invoke(
    {"messages": [{"role": "user", "content": "My project is Tiny-Agent."}]},
    config=thread_a,
)
graph.invoke(
    {"messages": [{"role": "user", "content": "Today I am learning memory."}]},
    config=thread_a,
)

print("thread-a history:")
for message in graph.get_state(thread_a).values["messages"]:
    print(f"  {message.type:9} {message.content}")

print("\nthread-b state before any interaction:")
print(graph.get_state(thread_b).values)
