# LangChain vs LangGraph

Many beginners encounter the names together and assume they are competing ways to do exactly the same thing.

That is too simplistic.

For Tiny-Agent, use this mental model:

```text
LangChain
    -> reusable LLM application abstractions and integrations

LangGraph
    -> low-level stateful orchestration/runtime
```

Current LangChain agents are themselves built on LangGraph, which is another reason to understand the layers separately.

---

## Recommended companion resources

If this is your first time seeing LangChain, it helps to read one short official overview before continuing:

- [LangChain Overview](https://docs.langchain.com/oss/python/langchain/overview) — current framework positioning and ecosystem layering.
- [LangChain Quickstart](https://docs.langchain.com/oss/python/langchain/quickstart) — shows the current high-level `create_agent()` workflow.
- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents) — explains the high-level Agent abstraction and its graph-based execution model.
- [LangChain Messages](https://docs.langchain.com/oss/python/langchain/messages) — use this beside the message examples in this chapter.
- [LangChain Tools](https://docs.langchain.com/oss/python/langchain/tools) — use this beside the `@tool` example.
- [LangChain Essentials — Python](https://academy.langchain.com/courses/langchain-essentials-python) — free official guided course covering agents, messages, tools, streaming, MCP, memory, structured output, and HITL.

For LangGraph-specific material, use:

- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [Graph API Overview](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph Essentials — Python](https://academy.langchain.com/courses/langgraph-essentials-python)
- [Dive into LangGraph — LangGraph 1.0 完全指南](https://www.luochang.ink/dive-into-langgraph/) — recommended Chinese companion tutorial.

Do not try to memorize both frameworks at once. First answer this question for every abstraction you see:

> Is this component describing an LLM/application primitive, or is it controlling stateful execution?

That question makes the rest of this chapter much easier to follow.

---

## 1. What LangChain gives you

LangChain provides standardized abstractions around common LLM application components.

Examples include:

- messages;
- model interfaces;
- tools;
- agent abstractions;
- document/retriever integrations;
- provider integrations.

These reduce provider-specific and application boilerplate.

---

## 2. Messages

Tiny-Agent currently stores messages as dictionaries:

```python
{
    "role": "user",
    "content": "hello",
}
```

LangChain provides message objects such as:

```python
HumanMessage(content="hello")
AIMessage(content="...")
ToolMessage(content="42", tool_call_id="call_1")
```

These standardize message metadata and multimodal/provider interactions.

The abstraction is useful once you understand the underlying roles and tool-call correlation from Stage 00/01.

---

## 3. Tools

Tiny-Agent:

```python
Tool(
    name="multiply",
    description="Multiply two numbers.",
    parameters={...},
    handler=multiply,
)
```

LangChain:

```python
from langchain.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two integers exactly."""
    return a * b
```

The decorator can derive tool metadata/schema from Python typing and the docstring.

This is a convenience abstraction, not a different Function Calling mechanism.

The model still receives a tool description/schema and proposes a tool call.

---

## 4. Models

Tiny-Agent created its own provider-neutral `Model` protocol and OpenAI adapter so you could learn the boundary explicitly.

LangChain offers standardized model interfaces across providers.

That can be valuable in a production application where you want:

- consistent model invocation;
- provider switching;
- standard tool binding;
- standard message types;
- middleware/integration support.

But if you learn this abstraction before understanding the provider boundary, it can hide important details such as tool-call IDs and provider state.

---

## 5. LangChain agents

LangChain also provides a high-level agent API.

That is useful when you want a prebuilt, production-oriented tool-calling Agent architecture quickly.

Tiny-Agent deliberately does not replace Stage 01 with `create_agent()` because our educational goal is different:

```text
first understand the loop
        ↓
then understand graph orchestration
        ↓
then evaluate high-level agent abstractions
```

A framework shortcut is most valuable after you know what it is shortening.

---

## 6. What LangGraph gives you

LangGraph focuses on execution orchestration:

- explicit state;
- nodes and edges;
- conditional transitions;
- cycles;
- persistence/checkpoints;
- durable execution;
- interrupts;
- streaming;
- subgraphs;
- human-in-the-loop infrastructure.

It does not require every node to use LangChain.

You can put ordinary Python functions, custom model clients, or Tiny-Agent components inside LangGraph nodes.

---

## 7. They can be used together

A common architecture is:

```text
LangChain model abstraction
          |
          v
LangGraph model node
          |
          v
LangChain tool abstraction
          |
          v
LangGraph tool node / workflow
```

LangChain supplies reusable components.

LangGraph supplies orchestration.

---

## 8. Tiny-Agent's role

Tiny-Agent is not trying to replace either project.

It acts as a transparent reference implementation.

```text
Tiny-Agent Stage 00/01
    -> learn API/tool/Agent mechanics

Tiny-Agent Stage 02
    -> learn workflow/planning control

Tiny-Agent Stage 03
    -> compare handwritten orchestration with LangGraph/LangChain
```

The goal is that when you later see:

```python
create_agent(...)
```

or:

```python
StateGraph(...)
```

you can explain what responsibilities are hidden underneath.

---

## 9. Do not import framework abstractions without a reason

Examples of poor reasoning:

```text
"Use PromptTemplate because this is LangChain code."
"Use a graph because this is an Agent."
"Wrap every Python function with @tool."
```

Instead ask:

- does this abstraction reduce meaningful boilerplate?
- does it standardize something that varies across providers?
- does it improve observability or composition?
- does the team need the interoperability it provides?

Use abstractions intentionally.

---

## 10. Practical comparison

| Concern | Tiny-Agent | LangChain | LangGraph |
|---|---|---|---|
| Learn raw Agent loop | Excellent | Usually abstracted | Can express it, but more infrastructure |
| Model/provider abstraction | Minimal custom protocol | Strong | Not primary focus |
| Tool abstraction | Minimal custom Tool | Strong | Can consume tools, not primary role |
| Stateful graph orchestration | Educational/minimal | High-level agents use it indirectly | Primary focus |
| Checkpoints / interrupts | Not in handwritten core | Exposed through agent runtime where relevant | Primary runtime capability |
| RAG integrations | Later Stage 04 | Strong ecosystem | Orchestrates retrieval workflows |
| High-level quick agent | Deliberately manual | `create_agent` | Lower-level |

---

## 11. Current ecosystem layering

A useful 2026 mental model is:

```text
High-level prebuilt Agent
        LangChain
            |
            v
Low-level orchestration runtime
        LangGraph
            |
            v
Provider/model/tool integrations
  LangChain components or your own code
```

This layering can evolve over time, so always re-check current official documentation when implementing production code.

---

## Completion check

You should be able to answer:

1. Why LangChain and LangGraph are not interchangeable labels.
2. Why LangGraph can be used without LangChain.
3. Why LangChain tools do not change the underlying Function Calling concept.
4. Why Tiny-Agent teaches its own runtime before `create_agent()`.
5. Which layer you would choose for model abstraction, and which for stateful orchestration.
