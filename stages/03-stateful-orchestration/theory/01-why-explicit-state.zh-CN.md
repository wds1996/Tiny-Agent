# 为什么显式状态很重要

Stage 01 用清晰的 Python `while` loop 实现 Agent，Stage 02 又加入了 Router 和 Planner–Executor。它们都是很好的起点，因为普通 Python 控制流最容易看懂。

Stage 03 真正开始于一个问题：

> **系统下一步能做什么，是由哪些信息决定的？这些信息到底存在哪里？**

这就是显式有状态编排的起点。

---

## 1. 在我们给它命名之前，state 就已经存在

一个简化的 ReAct loop：

```python
messages = [...]
steps = 0

while steps < max_steps:
    response = model.generate(messages, tools)
    steps += 1

    if response.tool_calls:
        ...
        messages.append(...)
        continue

    return response.final_answer
```

它早就包含状态：

```text
messages
steps
pending tool calls
final answer
errors
```

只是这些状态散落在局部变量和 Python 调用栈中。

这叫 **implicit orchestration state**。

规模小时完全没问题。

---

## 2. 为什么隐式状态会逐渐失控

继续加入：

```text
routing
planning
replanning
approval
retry
checkpointing
streaming
parallel branches
process restart 后继续执行
```

当前执行位置可能同时依赖：

```text
messages
selected route
current plan
completed plan steps
retry count
approval status
budget usage
retrieval evidence
pending action
last error
```

如果它们分散在各处，就越来越难回答：

- 当前 run 的完整状态是什么？
- 哪个 transition 产生了它？
- 能否序列化？
- 能否被另一个进程检查？
- 能否在这里暂停？
- 明天还能否继续？
- 能否 replay？
- 能否从旧 checkpoint 分叉？

问题不是 `while` loop 不好，而是 **control state 已经不再容易观察和持久化**。

---

## 3. 显式 state

可以把关键 execution data 变成一等对象：

```python
class AgentState(TypedDict):
    messages: list[dict]
    pending_tool_calls: list[dict]
    final_answer: str | None
    error: str | None
    model_steps: int
```

一个 snapshot：

```python
{
    "messages": [...],
    "pending_tool_calls": [
        {
            "id": "call_42",
            "name": "search",
            "arguments": {"query": "..."},
        }
    ],
    "final_answer": None,
    "error": None,
    "model_steps": 3,
}
```

它回答的是：

> runtime 现在知道什么？

但它不一定回答：

> 下一步哪个 node 要运行？

后者属于 graph transition rule。

---

## 4. State 不等于 memory

### State

State 是**正确继续当前一次 execution** 所需要的数据。

例如：

```text
current messages
selected route
step counter
pending approval
current plan
```

### Long-term memory

Long-term memory 是被有意跨任务/跨会话保留的信息。

例如：

```text
user preferences
previous project decisions
persistent profile facts
learned task history
```

一个 graph 完全可以 stateful，却没有 long-term memory。

Stage 03 关注 execution state；Stage 06 才系统讲跨会话 memory 与 persistence policy。

---

## 5. State 不等于 model context

另一个高频混淆：

```text
Graph State
    !=
LLM Context Window
```

Graph state 可能含：

```text
messages
budget counters
route decisions
approval flags
database IDs
internal workflow metadata
```

真正需要发给 model 的只是其中一部分。

```python
state = {
    "messages": [...],
    "retry_count": 2,
    "permission_scope": "read-only",
}
```

模型可能需要 `messages`，但不一定需要看到所有 internal control field。

好的 orchestration layer 会显式决定哪些 state 进入 model context。

---

## 6. 显式 state 让 transition 可检查

可以把 workflow 理解为：

```text
State_t
   |
   v
Node
   |
   v
Partial update
   |
   v
State_t+1
```

例如：

```text
Before classify:
{ request: "I was charged twice" }

classify()

Update:
{ route: "billing" }

After classify:
{
  request: "I was charged twice",
  route: "billing"
}
```

Node 不需要重新构造完整 state，只需要声明“什么发生了变化”。

---

## 7. 为什么 node 常返回 partial state

推荐 contract：

```text
State -> Partial<State>
```

例如：

```python
def classify(state):
    return {"route": "billing"}
```

而不是每次手工复制所有字段。

好处包括：

- node 责任更小；
- state diff 更清晰；
- tracing 更容易；
- 更容易组合；
- 降低误覆盖字段的风险。

LangGraph `StateGraph` 就采用这种模型：node 读共享 state，返回更新。

---

## 8. 显式 state 不代表模型可以改所有 state

假设 graph state 中还有：

```text
permission_scope = read-only
remaining_budget = 3
```

模型不能通过生成：

```text
permission_scope = admin
remaining_budget = 100000
```

就给自己升权加预算。

延续 Stage 02 的核心原则：

> **Model output 是 proposal，不是 authority。**

某些 state 是 model-generated data；另一些是 application-owned policy。两者绝不能混为一谈。

---

## 9. 什么情况下不该引入 graph

如果 workflow 只有：

```text
parse -> validate -> save
```

普通 Python 通常更清楚。

如果 Agent 只有：

```text
model -> optional tool -> model
```

Stage 01 的 loop 可能仍然是更好的实现。

当你同时开始需要多个能力时，graph 才更有价值：

- branches；
- cycles；
- explicit state inspection；
- persistence；
- interruption；
- resumption；
- streaming progress；
- reusable subflows；
- multiple orchestration policies。

不要因为“图看起来比较高级”就把每个函数都变成 node。

---

## 10. Stage 03 心智模型

```text
                  Shared State
                       |
                       v
                  +---------+
                  |  Node A |
                  +----+----+
                       |
                partial update
                       |
                       v
                  Shared State
                       |
                  transition
                 /           \
                v             v
            +------+       +------+
            |Node B|       |Node C|
            +------+       +------+
```

某个 node 可以调用 LLM，另一个可以执行 Tool，再一个可以做 deterministic validation。

**Graph 的职责是协调它们，而不是把所有东西都变成 LLM。**

---

## 11. 完成检查

你应该能够回答：

1. Stage 01 `while` loop 的 state 存在哪里？
2. 为什么 explicit state 对 pause/resume 有价值？
3. 为什么 graph state 不等于 LLM context？
4. 为什么 graph state 不等于 long-term memory？
5. 为什么 node 尽量只返回变更字段？
6. 哪些 state 应该由 application 而不是 model 控制？
7. 什么复杂度阈值才值得从普通 Python 切到 graph runtime？