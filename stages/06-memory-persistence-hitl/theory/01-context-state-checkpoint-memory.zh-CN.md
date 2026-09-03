# Context、State、Checkpoint 与 Memory

在 Agent 教程里，**memory** 是一个极度过载的词。

很多材料会把任何“活过一行 Python”的东西都叫 memory：

```text
chat history?       memory!
LangGraph state?    memory!
Redis?              memory!
vector database?    memory!
checkpoint?         memory!
```

这对营销很方便，对 architecture 很糟糕。

Stage 06 第一件事就是把这些概念拆开。

---

# 1. 五个盒子

先建立这个 mental model：

```text
LLM context
    = model 在当前这次 call 中能看到什么

runtime state
    = application 为了继续执行而需要什么

checkpoint
    = runtime state 的持久化 snapshot/version

short-term memory
    = thread-scoped retained state

long-term memory
    = 有意跨 thread/session 保留的 selected information
```

旁边还有第六个概念：

```text
external knowledge / RAG corpus
    = system 检索的 documents/evidence
```

RAG knowledge 和 Agent memory 可能使用相同 storage technology，但 application semantics 不同。

---

# 2. Context 是 model 现在能看到的内容

假设 runtime 拥有：

```python
state = {
    "messages": [...],
    "customer_id": "cust-17",
    "approval_status": "pending",
    "internal_retry_count": 2,
}
```

LLM 不需要自动看到每个 key。

你可能只构造：

```python
model_messages = [
    {"role": "system", "content": "You are a support Agent."},
    *relevant_messages,
    {"role": "system", "content": "Approval is pending."},
]
```

因此：

```text
state != context
```

State 是 application data；Context 是其中被选出来、转换后暴露给 model 的 representation。

这个区别对 secrets、internal counter、authorization data 与巨大的 history 尤其关键。

---

# 3. State 是 Agent 的 working notebook

State 保存后续 execution step 需要的数据，例如：

- current plan；
- Tool observations；
- retrieved evidence；
- approval request；
- selected route；
- draft output；
- retry metadata；
- conversation messages。

Stage 03 的原则仍然适用：

> 能存 raw facts/state 时就存 raw state，需要调用模型时再格式化 prompt。

不好的 state：

```python
{
    "giant_prompt": "SYSTEM: ... USER: ... EVIDENCE: ..."
}
```

更好：

```python
{
    "messages": [...],
    "evidence": [...],
    "approval": {...},
}
```

Prompt formatting 是 state 的一个 view，而不是 state 本身。

---

# 4. Checkpoint 是 recovery artifact

Checkpoint 回答：

> 如果 execution 现在消失，继续这个 thread 需要保存什么？

概念上：

```text
thread-42
  |
  +-- checkpoint A
  +-- checkpoint B
  +-- checkpoint C
```

Checkpoint 不只是 transcript，它还可能包含：

```text
messages
current state values
next graph tasks
checkpoint metadata
pending writes
execution position
```

所以 checkpointing 属于 orchestration concern。

---

# 5. Short-term memory 是 thread-scoped

当前 LangGraph terminology 把 short-term memory 描述为：通过 checkpointer 在 thread scope 中持久化的 state。

```text
user-7
  |
  +-- thread-A
  |     +-- conversation state
  |
  +-- thread-B
        +-- independent conversation state
```

同一个人可以拥有很多 thread。

因此：

```text
thread_id != user_id
```

如果每个 conversation 都直接把 `user_id` 当 `thread_id`，这个用户本来互不相关的执行历史可能全部挤进同一条 thread。

---

# 6. Long-term memory 跨越 thread boundary

Long-term memory 回答另一个问题：

> 哪些经过选择的信息，应该在未来另一个 conversation 中继续可用？

例如：

```text
thread-A:
User: Please remember that I prefer concise Chinese explanations.

        ↓ approved memory write

namespace = ("user-7", "memories")
key       = "explanation-style"
value     = {...}

        ↓ later

thread-B:
Agent retrieves that preference
```

这个 memory 属于 user/application namespace，而不是 thread-A。

---

# 7. Memory 不是“把整个聊天永远存下来”

初学实现经常是：

```python
memory = every_message_ever
```

这不叫 memory strategy。

这叫带着怀旧情绪的 storage bill。

Long-term memory 应该通常是 **selected**。

例如：

```text
"I had ramen for lunch."
```

明天可能完全无关。

而：

```text
"Please remember that I am allergic to peanuts."
```

可能非常重要——同时它又属于敏感健康信息，因此需要更强 policy。

真正困难的不是 `PUT`，而是：

```text
what to write
what not to write
who owns it
how to retrieve it
when to update it
when to delete it
```

---

# 8. RAG knowledge 不自动等于 long-term memory

Stage 04 的 external evidence：

```text
Company handbook
API documentation
research papers
```

这些是 knowledge source。

Long-term memory 更可能是：

```text
user preferences
past task outcomes
learned examples
application-specific facts
selected instructions
```

Vector database 技术上可以都存，但不表示应该无语义地混进同一 namespace。

Database 是 infrastructure；memory/knowledge 是 application meaning。

---

# 9. 实用分类表

| Information | Best first home |
|---|---|
| current ToolCall | runtime state |
| current conversation history | short-term/thread state |
| execution recovery position | checkpoint |
| user preference across chats | long-term memory |
| company policy document | RAG / knowledge base |
| API key | secret manager，不是 Agent memory |
| authorization decision | application policy/state |
| debug trace | observability system |

最后几行非常重要。

不是所有 persistent fact 都属于“Agent memory”。

---

# 10. Tiny-Agent Stage 06 的规则

```text
information appears
       ↓
MemoryCandidate
       ↓
MemoryWritePolicy
       ↓
   allow / deny
       ↓
Store (if allowed)
```

Model 可以 **propose** memory。

Application 才拥有 durable write boundary。

这与 Tool、Route、Plan、MCP capability 的设计原则完全一致。

---

## 完成检查

你应该能够解释：

1. State vs LLM context；
2. Checkpoint vs chat transcript；
3. Short-term vs long-term memory；
4. `thread_id` vs `user_id`；
5. Long-term memory vs RAG knowledge；
6. 为什么 database technology 不定义 data 的 semantic type；
7. 为什么“永久保存所有 message”不是 memory policy。