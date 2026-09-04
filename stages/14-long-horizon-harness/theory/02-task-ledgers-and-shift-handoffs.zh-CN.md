# 02 — Task Ledger、崩溃恢复与换班 Handoff

Task ledger 把项目进度从模型会话中外部化，使新的 worker / session 可以从**当前事实**继续，而不是重放一段不可见的对话历史。

Tiny-Agent 刻意先使用人类可读的 JSON ledger，因为在引入 workflow engine 之前，你应该先看清这个机制到底在保存什么。

---

## 1. 最小任务记录

```text
id
description
status
attempts
latest note
artifact paths
```

Tiny-Agent 中：

```python
@dataclass
class TaskRecord:
    id: str
    description: str
    status: str = "pending"
    attempts: int = 0
    note: str = ""
    artifacts: list[str] = field(default_factory=list)
```

ledger 还会保存整个 run 的 objective 和近期 notes。

---

## 2. 先持久化“开始执行”，再真正执行

`LongHorizonHarness` 在调用 worker **之前**，先把任务标记为 running：

```python
task.status = "running"
task.attempts += 1
self.ledger.save(state)

result = await worker(...)
```

为什么要先保存？

因为如果进程在 worker 执行期间死亡，持久化状态至少能告诉下一任 worker：

```text
这个任务已经进入过 in-flight 状态
```

如果只在完成之后保存，那么崩溃后系统甚至不知道任务有没有开始过。

---

## 3. Ledger 写入要尽量原子化

Tiny-Agent 先写临时文件，再替换正式 ledger：

```python
temporary.write_text(json_text)
temporary.replace(self.path)
```

这样可以降低崩溃留下“只写了一半 JSON”的概率。

但要注意：

> 本地 JSON 文件不适合多个分布式 worker 并发修改。

多 worker / distributed mutation 应使用 transaction-capable database 或 workflow backend。

这里要学习的是 **atomic replacement semantics**，不是把本地文件包装成“分布式一致性系统”。

---

## 4. 恢复持久化的 `running`

崩溃场景：

```text
persist running
-> worker 做了一些工作
-> process 在 terminal save 前死亡
```

新进程加载时看到：

```text
task.status = running
```

Tiny-Agent 会显式恢复：

```python
for task in state.tasks:
    if task.status == "running":
        task.status = "pending"
        task.note = "recovered_interrupted_task"
```

这个 note 很重要，因为它保留了“这是一次 crash recovery 后的重试”这一 provenance。

---

## 5. Recovery 恢复的是 liveness，不是 exactly-once

旧 worker 可能在崩溃前一瞬间已经完成外部 side effect：

```text
send_email()
-> provider 已接受邮件
-> process crash
-> ledger 仍是 running
-> 新 worker recover / retry
```

结果可能是重复发信。

因此，可恢复任务仍然需要：

- idempotency key；
- transaction / outbox pattern；
- downstream deduplication；
- side-effect record；
- approval policy。

`recover_interrupted()` 的含义是：

> “这项工作需要重新关注。”

而不是：

> “可以确定之前什么都没发生。”

---

## 6. Handoff summary 是视图，不是 ledger 本身

Tiny-Agent 会生成紧凑摘要：

```python
summary = LongHorizonHarness.handoff_summary(state)
```

大致形态：

```text
Objective: ...
Progress: {pending: 3, running: 0, completed: 5, failed: 1}
Recent notes: [...]
Use workspace and ledger as externalized state...
```

它帮助下一次 session 快速定位当前局面；当需要精确信息时，下一 worker 再去读 ledger / workspace。

因此：

```text
handoff summary
    = derived working view

TaskLedger
    = exact durable source of progress truth
```

绝不能把摘要变成唯一 source of truth。

---

## 7. 换班类比

可以把它想成医院交班。

糟糕的交班：

> 所有情况都在我脑子里，祝你好运。

另一种同样糟糕的交班：

> 这是病人住院以来所有人说过的 900 页逐字记录，你自己看吧。

更好的交班是：

```text
patient / objective
current status
critical decisions
open tasks
recent events
exact records 在哪里
```

长时程 Agent 的 session handoff 也需要在“信息不足”和“整本历史倒进上下文”之间取得这个平衡。

---

## 8. `failed` 不等于 `pending`

```text
pending
    = 尚未执行，或已经被明确安排为可再次尝试

failed
    = 已经发生过一次已知失败
    = 可能需要 repair / replan / human decision
```

不要写成：

```python
for failed_task in tasks:
    retry_forever(failed_task)
```

这不是韧性设计，只是一出规模很小、自动循环播放的悲剧。

---

## 9. 动态增加任务

worker 在执行时可能发现新的工作：

```python
HarnessStepResult(
    success=True,
    note="Found two missing evidence checks",
    new_tasks=(
        "check method A evidence",
        "check method B evidence",
    ),
)
```

harness 将这些工作追加为显式的 `TaskRecord`。

这样 dynamic planning 就进入可观察、可持久化的 project state，而不是只存在模型的一段 prose 中。

---

## 10. Resume 示例

Session 1：

```text
初始化 objective + A/B/C
run max_steps=1
A completed
ledger saved
runtime object 被销毁
```

Session 2：

```text
new AgentWorkspace
new LongHorizonHarness
load same ledger
handoff: A completed, B/C pending
execute B
```

这里不需要任何隐藏 model history。

这正是本阶段需要达到的恢复里程碑。

---

## 完成原则

> **在工作前后都持久化状态转换，让中断执行显式可见，把 handoff summary 当作派生上下文，并且永远不要把 crash recovery 误认为 exactly-once side effect。**