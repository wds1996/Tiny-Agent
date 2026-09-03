# Persistence、Streaming 与 Interrupts

这一章讲的是最早一批真正会让“进程内小 `while` loop”开始别扭的能力。

它们也是引入 stateful orchestration runtime 的核心理由。

---

# 1. Persistence

Persistence 表示 orchestration runtime 可以随时间保存 execution state。

在 LangGraph 中，checkpointer 会把 graph state 保存为与某个 thread 关联的 checkpoint：

```text
thread_id
   |
   +-- checkpoint 1
   +-- checkpoint 2
   +-- checkpoint 3
```

Checkpoint 不只是 chat transcript，它表示 graph 在某个执行时刻的状态。

---

## 2. Checkpoint 为什么重要

它让以下能力成为可能：

- interruption 后 resume；
- 多次 invoke 间维持 conversation/execution state；
- human approval；
- fault recovery；
- state inspection；
- replay / time-travel debugging。

这也解释了 explicit state 的价值：如果 runtime 连“哪些数据决定继续执行”都说不清，就很难可靠持久化。

---

## 3. `thread_id`

启用 checkpointer 后，LangGraph 用 `thread_id` 标识应该加载/保存哪条 execution history。

```python
config = {
    "configurable": {
        "thread_id": "incident-123"
    }
}

graph.invoke(inputs, config=config)
```

继续同一逻辑 thread 时复用同一个 `thread_id`；独立 run 使用新的 ID。

不要混淆：

```text
thread_id != user_id
```

一个 user 可以拥有很多 thread。

---

## 4. `InMemorySaver`

本地学习/测试：

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

它只存在于进程内存，适合：

- tutorial；
- tests；
- local debugging。

它不是 durable production storage。

生产环境通常需要 PostgreSQL 等持久化 checkpointer。Stage 06/10 会再讨论操作层选择。

---

# 5. Streaming

长 Agent execution 可能持续几十秒甚至更久。如果 UI 只能等最终 return，体验和 observability 都很差。

```python
for update in graph.stream(
    initial_state,
    stream_mode="updates",
):
    print(update)
```

`updates` 可以在 graph step 后持续观察 state update。

---

## 6. Streaming 不只是 token streaming

“Streaming” 不仅是：

```text
LLM token
LLM token
LLM token
```

Graph runtime 可以流式暴露：

```text
node/state updates
model message chunks
custom progress events
checkpoint events
task events
```

对 Agent UI 而言，“正在检索 / 正在审批 / 正在执行工具”有时比逐 token 输出更重要。

---

## 7. Streaming vs persistence

二者解决的问题不同：

### Streaming

> 现在正在发生什么？

### Persistence

> 之后还能恢复什么状态？

成熟系统经常同时使用二者。

---

# 8. Interrupt

Interrupt 会暂停 graph，等待外部输入。

典型场景：

- approve risky action；
- 请求缺失信息；
- 允许人类编辑 proposed data；
- 在执行前审查 plan。

```python
from langgraph.types import interrupt


def approval_node(state):
    approved = interrupt(
        {
            "question": "Approve this action?",
            "action": state["action"],
        }
    )
    return {"approved": approved}
```

---

## 9. Interrupt 依赖 persistence

既然 execution 被暂停，runtime 必须记住：

- graph 停在哪里；
- 当时 state 是什么。

所以 HITL interrupt 通常依赖：

```text
checkpointer
thread_id
interrupt(...)
Command(resume=...)
```

---

## 10. Resume

暂停后：

```python
from langgraph.types import Command

graph.invoke(
    Command(resume=True),
    config=config,
)
```

`resume` value 会成为 node 内部 `interrupt()` 的返回值，使 node 能继续处理 human/external input。

---

## 11. 最关键的语义：node 会从头重新执行

这是本阶段最重要的细节之一。

Resume interrupt 时，node 会从**节点开头重新执行**，而不是从某条 Python 指令的下一行继续。

危险例子：

```python
def dangerous_node(state):
    send_email()          # side effect
    approved = interrupt("Continue?")
    ...
```

Resume 时 `interrupt()` 前面的代码可能再次运行，于是邮件可能发两遍。

---

## 12. Idempotency

因此 `interrupt()` 前的代码应当：

- 本身幂等；或
- 被移动到更安全的 orchestration boundary。

常见策略：

- side effect 放到 approval 之后；
- idempotency key；
- 执行前检查是否已完成；
- 把 proposal node 与 execution node 分开。

更安全的 graph：

```text
prepare action
     |
     v
approval interrupt
     |
     +-- approved -> execute side effect
     |
     +-- rejected -> cancel
```

不要先做了，再问用户“你批准我刚才做的事吗？”。

---

## 13. 不要把 interrupt 当普通 error 随手 catch

LangGraph 使用特殊 control-flow semantics 来暂停执行。

不要把 `interrupt()` 放进一个“抓所有异常”的 `try/except` 里，否则 runtime 可能无法正确识别 suspend/checkpoint。

框架语义不是语法糖，必须理解。

---

## 14. Interrupt payload 应可序列化

推荐：

```python
{
    "question": "Approve deployment?",
    "release": "v1.4.2",
}
```

不要直接塞任意内部对象，更不要把 sensitive exception detail 原样抛给 human UI。

Payload 是 application human-facing control protocol 的一部分。

---

## 15. Human approval 不等于 authorization

即使某个人点击 approve，runtime 仍需执行普通 policy：

```text
human approves
      |
      v
permission check
      |
      v
budget / policy validation
      |
      v
execute tool
```

HITL 是 permission system 的补充，不是替代。

Stage 06/07 会继续深入。

---

# 16. Checkpoint vs long-term memory

Checkpoint 回答：

> 如何继续这一次 graph execution？

Long-term memory 回答：

> 哪些信息应该跨未来任务继续记住？

二者可能都使用数据库，但语义完全不同。

不要把所有 database write 都叫“Agent memory”。

---

# 17. Production persistence boundary

`InMemorySaver` 在进程退出后就消失。

生产系统需要继续考虑：

- durable storage；
- serialization；
- cleanup/retention；
- thread identity；
- concurrent update；
- privacy；
- schema migration；
- operational monitoring。

Stage 03 先把概念建立起来，后面再补完整 policy。

---

# 18. Stage 03 capability stack

```text
implicit Python state
        ↓
explicit shared state
        ↓
node / edge graph
        ↓
LangGraph runtime
        ↓
stream updates
        ↓
checkpoint state
        ↓
interrupt
        ↓
resume with external input
```

这就是 durable、human-supervised Agent execution 的基础。

---

## 完成检查

你应该能解释：

1. Checkpoint vs chat history；
2. `thread_id` vs `user_id`；
3. 为什么 `InMemorySaver` 只适合教学/测试；
4. streaming progress vs token streaming；
5. interrupt 为什么需要 persistence；
6. `Command(resume=...)` 与 `interrupt()` 的关系；
7. 为什么 resumed node 会重新执行 `interrupt()` 前的代码；
8. 为什么 side effect 需要 idempotency；
9. HITL 为什么不替代 permission policy；
10. checkpoint persistence vs long-term Agent memory。