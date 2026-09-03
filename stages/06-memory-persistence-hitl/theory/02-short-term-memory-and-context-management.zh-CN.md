# Short-Term Memory 与 Context Management

Short-term memory 听起来很简单：

> 保留 conversation history。

直到 conversation 变成 800 条 message，prompt 看起来像有人试图搬家时把整个公寓塞进一只行李箱。

真正的问题不只是“记住”，而是：

> **在有限 model context 内，怎样有选择地继续记住？**

---

# 1. Short-term memory 是 thread-scoped state

LangGraph 中：

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {
    "configurable": {
        "thread_id": "conversation-123"
    }
}
```

同一个 logical conversation/execution history 复用同一 `thread_id`；另一条 thread 用另一个 ID。

当前 LangGraph 把 short-term memory 描述为通过 checkpointer 在 thread scope 中持久化的 state。

---

# 2. Checkpointer 保存的内容多于 LLM 应看到的内容

Checkpointed state 可能是：

```python
{
    "messages": 300_messages,
    "retrieved_documents": [...],
    "approval": {...},
    "internal_retry_count": 3,
}
```

绝不能因此自动：

```python
prompt = str(all_state)
```

Persistence 与 context selection 是不同步骤。

正确 flow：

```text
checkpointed thread state
        ↓
context management policy
        ↓
selected / summarized messages
        ↓
LLM context
```

---

# 3. Context window 是有限资源

即使 model 支持很大的 context window，无限发送历史也会增加：

- input token；
- latency；
- cost；
- stale information 与 current information 的竞争；
- prompt-injection surface；
- contradictory history；
- noise。

因此：

```text
more history != more useful memory
```

---

# 4. 常见 context-management strategy

## A. 保留最近 N 条 message

```python
recent = messages[-20:]
```

优点：

- deterministic；
- cheap；
- easy to debug。

缺点：

- 重要旧事实可能被切掉；
- message 长度差异巨大。

20 条 message 仍然可以大得惊人。

---

## B. Token-aware trimming

```text
newest messages first
        ↓
add until token budget reached
```

它更直接尊重真实 context budget。

但本质仍是按 recency 忘记，而不是按 meaning。

---

## C. Summarize older conversation

```text
old messages
    ↓
summary

recent messages stay verbatim
```

于是 context 可以变成：

```text
system instructions
conversation summary
recent messages
relevant long-term memories
current evidence
```

通常比把巨大 transcript 原样运输更有效。

---

# 5. Summary 是 lossy compression

Summary 不是 original history。

原文：

```text
User prefers Python for examples,
except when interviewing for a C++ role.
```

糟糕 summary：

```text
User prefers Python.
```

Exception 消失了。

因此 summary 应视为 **derived state with provenance**，而不是不可质疑的 truth。

---

# 6. Short-term memory 不应偷偷变 long-term memory

Thread 里出现一个陈述，不代表它值得跨 session 保留。

例如：

```text
User: Today I am staying in Osaka.
```

对当前 thread 可能有用，但不能自动变成：

```text
Long-term memory:
"User permanently lives in Osaka."
```

所以 Stage 06 明确分离：

```text
thread state
        from
long-term memory writes
```

---

# 7. State cleanup 也是 memory design

Long-running thread 会积累：

- messages；
- Tool results；
- retrieved documents；
- intermediate plans；
- temporary artifacts。

不应该全部永久存在。

用 lifecycle 分类：

```text
ephemeral
  -> one node/step

thread-lived
  -> while this conversation continues

cross-thread durable
  -> selected long-term memory

external archival
  -> logs/audit/history systems
```

这样可以避免“反正都塞 state”架构。

---

# 8. Thread deletion 与 retention

生产系统必须回答：

```text
How long does a thread live?
Who can delete it?
Can a user request deletion?
What happens to old checkpoints?
Do backups obey the same retention policy?
```

Persistence 没有 retention policy，最终就会变成 accidental archival。

而 accidental archival 是一种非常昂贵的隐私法规学习方式。

---

# 9. Stage 06 example

见：

```text
code/thread_short_term_memory.py
```

它用一个 `InMemorySaver` 与两个 thread ID：

```text
thread-a
  -> interaction 1
  -> interaction 2
  -> accumulated state

thread-b
  -> independent empty state
```

这里学的是 **scope**，不是 `InMemorySaver` 本身。

`InMemorySaver` 随 process 消失；durability 在后面章节解决。

---

# 10. Practical prompt assembly

Production-style context builder 概念上可能是：

```python
def build_context(state, memories, evidence):
    return [
        system_message(),
        conversation_summary(state),
        *recent_messages(state),
        memory_message(memories),
        evidence_message(evidence),
    ]
```

注意缺少：

```text
serialize_the_entire_database()
```

Model 应看到的是 **minimum useful context**，不是 application 拥有的所有 byte。

---

## 完成检查

你应该能解释：

1. checkpointer persistence 与 model context 为什么不同；
2. `thread_id` 如何定义 short-term memory scope；
3. 为什么 history 即使能塞进 context，也可能伤质量；
4. recency trimming vs token trimming vs summarization；
5. summary 为什么是 lossy derived state；
6. thread fact 为什么不能自动变 long-term memory；
7. retention/deletion 为什么属于 memory architecture。