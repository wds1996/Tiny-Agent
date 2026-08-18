"""Stage 06 example 3: cross-thread long-term memory with LangGraph Store.

Run:
    python -m pip install -e ".[stage06]"
    python stages/06-memory-persistence-hitl/code/long_term_memory_store.py
"""

from langgraph.store.memory import InMemoryStore

from tiny_agent import memory_namespace


store = InMemoryStore()

user_id = "user-42"
namespace = memory_namespace(user_id)

# Imagine this write happened in conversation/thread A.
store.put(
    namespace,
    "explanation-style",
    {
        "text": "The user prefers concise Chinese explanations with runnable code.",
        "kind": "semantic",
        "source": "explicit-user-request",
    },
)

# Imagine this read happens later in a completely different conversation/thread B.
item = store.get(namespace, "explanation-style")
print("same user, another thread:")
print(item.value if item else None)

print("\nother user cannot see that namespace by default:")
other = store.get(memory_namespace("user-99"), "explanation-style")
print(other)

print("\nall memories in user-42 namespace:")
for memory in store.search(namespace):
    print(memory.key, memory.value)
