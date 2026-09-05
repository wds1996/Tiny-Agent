# Stage 06：Agent 也得学会“下班前存档”——从 State 到 Memory、Checkpoint 与 HITL

> Language: [English](README.md) | **简体中文**

前五章结束以后，我们的 Agent 已经不像最开始那个“会聊天的函数”了。它能调用 Tool，能自己走 ReAct 循环，能按照 Workflow 或 Graph 编排任务，能去知识库里找证据，也能通过 MCP 接上外部系统。

能力越来越多，接下来出现的问题却非常朴素：

> **程序关掉以后，刚才做到哪了？**

假设 Agent 正准备给用户退款。它已经查完订单、确认规则、算好金额，最后一步因为会真的动钱，所以系统暂停下来等人工审批。审批人午饭回来点了“同意”，结果原来的 Python 进程早就因为部署重启消失了。

如果你的系统只能回答：

> “不好意思，那次审批属于上一条进程的人生经历。”

那它还不能算真正可持续运行的 Agent 系统。

Stage 06 就从这里开始。我们不急着把所有能存东西的数据库统称为“Memory”，而是先把几个非常容易混在一起的概念分清：**State、Checkpoint、Short-term Memory、Long-term Memory，以及 Human-in-the-Loop。**

这一章的核心不是“怎样把 JSON 塞进数据库”，而是：

> **什么必须为了继续执行而保存，什么值得跨会话记住，以及什么时候程序必须停下来把决定权交还给人。**

---

## 1. State 已经有了，为什么还要 Checkpoint？

Stage 03 里我们把 State 摊在了桌面上。一个退款流程可能有这样的状态：

```python
state = {
    "order_id": "ORDER-42",
    "amount": "18.50",
    "phase": "waiting_approval",
}
```

只要 Python 进程还活着，这个状态待在内存里没有问题。

问题是，内存没有忠诚度。进程退出、容器重启、机器故障，它说没就没。

于是我们需要一个很自然的动作：

```text
runtime state
    ↓ persist
checkpoint
```

Checkpoint 可以理解成某个执行时刻的**可恢复快照**。它关心的问题不是“用户喜欢什么”，而是：

> “这次 run 已经执行到了哪里，恢复时必须知道什么？”

这一点很重要，因为 Checkpoint 和 Memory 经常都存到数据库，于是名字一模糊，架构也跟着糊。

把它们先粗略分开：

| 概念 | 它回答的问题 |
|---|---|
| State | 当前执行需要知道什么？ |
| Checkpoint | 当前执行快照怎样跨进程保存？ |
| Short-term Memory | 同一条会话 / thread 里过去哪些信息要继续保留？ |
| Long-term Memory | 跨会话以后，哪些用户相关信息仍值得记住？ |
| RAG Knowledge | 外部文档里有哪些证据可以被检索？ |

数据库表可能长得很像，但**语义不是由数据库产品决定的**。

把 `checkpoint` 表改名叫 `memory_super_pro_max`，它也不会突然获得心理学学位。

---

## 2. `run_id`、`thread_id`、`user_id` 别混成一锅粥

随着系统开始持久化，你会遇到几个 ID。

最危险的写法不是忘记 ID，而是所有地方都用一个 `"123"`，然后靠感觉解释它是谁。

考虑一个用户 Alice。她可能同时开两个对话：

```text
user_id = alice

thread_id = trip-planning
thread_id = expense-reimbursement
```

而“报销”这条 thread 里，又可能启动一次具体的执行：

```text
run_id = reimburse-2026-09-04-001
```

三个 ID 的作用域完全不同。

`user_id` 表示谁拥有长期数据；`thread_id` 表示哪段连续会话或任务上下文；`run_id` 表示某一次实际执行。

所以一个合理关系更像：

```text
User
├── Thread A
│   ├── Run 1
│   └── Run 2
└── Thread B
    └── Run 3
```

如果把 `thread_id` 当成 `user_id`，跨会话记忆很容易丢；如果把 `user_id` 当成 `thread_id`，不同任务的执行状态又可能莫名串在一起。

持久化系统的第一道题，往往不是“选 SQLite 还是 Postgres”，而是先把作用域说清楚。

---

## 3. Checkpoint 保存的是“继续干活所需的信息”

本章的教学代码用 SQLite 手写一个很小的 Checkpoint Store：

```python
@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    phase: str
    action: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
```

保存时，我们把状态序列化后写入数据库：

```python
def save(self, state: WorkflowState) -> None:
    payload = json.dumps(asdict(state))
    conn.execute(
        """
        INSERT INTO checkpoints(run_id, state_json)
        VALUES (?, ?)
        ON CONFLICT(run_id)
        DO UPDATE SET state_json=excluded.state_json
        """,
        (state.run_id, payload),
    )
```

这段代码最重要的不是 SQLite 语法，而是一个变化：

以前，流程能不能继续依赖原来的 Python 对象还在不在。

现在，只要新的 Runtime 能拿到同一个持久化存储和 `run_id`，就能重新读出：

```text
phase = waiting_approval
action = issue_refund
arguments = ...
```

于是“恢复”第一次不再依赖原进程的寿命。

这就是 Durable Execution 最基础的一层含义。

---

## 4. Durable 不等于“永远不会重复执行”

这里很容易兴奋过头。

我们已经保存了 Checkpoint，于是有人会宣布：

> “太好了，现在所有副作用都 exactly-once 了！”

先把庆功蛋糕放回冰箱。

Checkpoint 能告诉你“上一次做到哪”，但它不能自动控制数据库之外的世界。

想象这样一段流程：

```text
1. 调用支付服务退款
2. 支付服务成功
3. 程序还没来得及保存 completed checkpoint
4. 机器断电
5. 系统恢复旧 checkpoint
6. 再调用一次退款
```

如果外部支付服务不知道这两个请求其实属于同一次业务动作，你可能真的退了两次。

所以 Durable Recovery 和 Exactly-once Side Effect 是两回事。

本章的教学实现用一个很小的 `idempotency_key` 演示这个思想：

```python
idempotency_key = f"{run_id}:issue_refund"
```

然后在本地 `effects` 表里用唯一键保证同一动作不会被重复记录。

这只能证明**教学数据库内部**的幂等思路。

到了真实外部 API，你通常还需要对方支持 idempotency key、业务唯一约束，或者设计安全的补偿机制。

这是一个很典型的工程习惯：

> 不要因为解决了恢复，就顺手宣称解决了整个分布式一致性。

---

## 5. 现在轮到 Memory：什么东西值得跨会话记住？

Checkpoint 解决的是“这次任务做到哪”。

但用户可能还有另一类期待：

> “以后都用中文回答我。”
>
> “记住我喜欢简短解释。”
>
> “下次别再问我的默认城市了。”

这些不是某一次 Workflow 的执行进度。它们属于跨 thread 的长期信息。

于是我们得到另一个方向：

```text
execution continuity
    -> checkpoint

cross-thread personalization / retained knowledge
    -> long-term memory
```

关键问题随之变化。

Checkpoint 往往有很强的机械依据：没有它就无法恢复执行。

Memory 则不是“看到信息就存”。真正困难的是：

> **什么值得被保存？谁允许保存？保存多久？属于谁？**

这就是为什么本章不会写一个函数：

```python
def remember_everything(user_message):
    database.insert(user_message)
```

这个函数确实很好写。

它也确实很容易让隐私团队在凌晨给你打电话。

---

## 6. 模型提取出的 Memory 只是候选，不是写入许可

我们定义一个 `MemoryCandidate`：

```python
@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    owner_id: str
    key: str
    value: dict[str, Any]
    kind: MemoryKind
    explicit_user_request: bool
    sensitive: bool = False
```

注意名字叫 Candidate。

模型可以从一句：

> “以后请用简洁中文回答我。”

提取出：

```python
MemoryCandidate(
    owner_id="user-7",
    key="answer-style",
    value={"language": "Chinese", "style": "concise"},
    kind="semantic",
    explicit_user_request=True,
)
```

但 Candidate 不应该直接执行：

```python
store.put(candidate)
```

中间还有 Policy：

```python
decision = policy.evaluate(candidate)

if decision.store:
    store.put(candidate)
```

本章的保守策略会拒绝三类东西：敏感信息、没有明确记忆意图的偶发信息，以及直接修改 Agent 自身程序规则的 procedural memory。

这并不是说所有产品都必须使用完全一样的规则。

重点是：

> **模型负责提出“这也许值得记住”；应用负责决定“允许不允许真的写进去”。**

这个边界和我们从 Stage 00 一直坚持的原则其实完全一样：

```text
model proposal != application authority
```

只是这一次，“Tool Call”换成了“Memory Candidate”。

---

## 7. Semantic、Episodic、Procedural：先理解，不要急着全实现

Memory 讨论里经常出现三个词。

Semantic Memory 更像稳定事实或偏好，例如“用户偏好中文”。

Episodic Memory 更像过去发生过的事件，例如“上次旅行规划最后选择了京都”。

Procedural Memory 则涉及“应该怎样做事”，例如某种工作流程、策略甚至行为规则。

三者的风险并不相同。

把“用户喜欢中文”写错了，通常还能修。

把“执行退款不需要审批”错误地写进 Procedural Memory，后果显然不在同一个量级。

所以学习 Memory 时不要只问：

> “能不能向量搜索？”

还要问：

> “它改变的到底是事实、经历，还是系统行为？”

这也是为什么本章默认对 Procedural Memory 更保守。

---

## 8. Memory Store 必须有 Owner Scope

一个最小 Long-term Memory Store 至少应该知道“这是谁的数据”。

本章使用：

```python
PRIMARY KEY (owner_id, key)
```

读取时也必须带 `owner_id`：

```python
store.get("alice", "answer-style")
```

而不是：

```python
store.get("answer-style")
```

后者在单用户 Demo 里看起来毫无问题。

一旦进入多用户环境，它就像公司储物柜只写了“钥匙”两个字，没有柜号。

更完整的系统还会有 tenant、namespace、版本、过期时间、来源、删除状态等，但这些属于规模扩大后的治理问题。这里先把最重要的一件事刻进直觉：

> **Long-term Memory 从一开始就应该有所有权边界。**

---

## 9. Human-in-the-Loop：有些地方 Agent 就该停下来

现在回到退款流程。

模型已经提出：

```text
issue_refund(order_id="ORDER-42", amount="18.50")
```

参数也通过验证。

这并不意味着它应该立即执行。

因为我们又遇到了熟悉的问题：

```text
模型建议做什么
≠
系统现在就有权做什么
```

退款会产生真实金融副作用，所以我们把流程停在：

```text
waiting_approval
```

并产生结构化审批请求：

```python
ApprovalRequest(
    run_id="run-001",
    action="issue_refund",
    arguments={"order_id": "ORDER-42", "amount": "18.50"},
    reason="Refund changes external financial state.",
)
```

这个设计比弹出一句：

> “确认吗？yes/no”

要强得多，因为审批人明确知道自己正在审什么。

---

## 10. 审批不是只有“同意”和“拒绝”

实际业务里，人经常想说：

> “可以退，但金额改成 12.50。”

所以我们提供三种结果：

```text
approve
edit
reject
```

`edit` 特别容易写错。

人修改了参数，不代表新参数自动合法。

因此流程应该是：

```text
model proposal
    ↓
human review
    ↓
approve / edit / reject
    ↓
if edit: validate edited arguments again
    ↓
authorization check
    ↓
execute
```

本章代码中的：

```python
resolve_refund_arguments(...)
```

会对编辑后的 `order_id` 和 `amount` 重新验证。

比如人工把金额改成 `-1`，程序不会因为“这是人改的”就肃然起敬，然后给负数退款。

Human-in-the-Loop 是增加一道决策边界，不是关闭输入验证。

---

## 11. Approval 也不是 Authorization

这个区别值得单独讲。

假设 Bob 点了“批准退款”。

系统还必须问：

> Bob 有退款审批权限吗？

如果 Bob 只是隔壁桌刚好路过的实习生，那么他的鼠标点击并不会获得魔法加持。

Approval 表示“某个人对某个动作给出了审查结果”。

Authorization 表示“这个身份是否被系统允许批准或执行这个动作”。

所以更完整的路径是：

```text
proposal
    ↓
validation
    ↓
approval required?
    ↓
authorized reviewer approves
    ↓
authorization for execution
    ↓
side effect
```

本章重点是 Durable HITL，所以不会展开完整 RBAC / ABAC 系统。后面的可靠性与安全章节会继续处理权限边界。

---

## 12. 最关键的一步：原进程死了，审批回来以后还能继续

现在把前面的东西串起来。

Runtime A 启动退款：

```python
runtime_a.start(
    run_id="run-001",
    order_id="ORDER-42",
    amount="18.50",
)
```

它把状态保存成：

```text
run-001
phase = waiting_approval
```

然后 Runtime A 消失。

过了一段时间，Runtime B 启动：

```python
runtime_b = RefundWorkflow(
    SQLiteCheckpointStore(db_path)
)
```

它不认识 Runtime A，也没有共享任何 Python 对象。

但它能：

```python
state = store.load("run-001")
```

恢复后再处理：

```python
ApprovalDecision(outcome="approve")
```

于是我们第一次得到真正有意义的 Durable HITL：

```text
run
  ↓
persist
  ↓
pause
  ↓
process disappears
  ↓
new process loads checkpoint
  ↓
human decision arrives
  ↓
resume
```

这比“在一个 `input()` 前面停住 Python”多迈了一大步。

---

## 13. 为什么 Stage 06 不把所有历史直接塞回模型？

学到这里，一个很自然的问题出现了。

我们现在已经能保存：

- Checkpoint；
- 对话历史；
- Long-term Memory；
- 外部检索结果；
- Tool Observation；
- MCP 返回数据。

于是很容易写出一句豪迈的产品需求：

> “既然都存了，每次调用模型时全给它不就行了？”

不行。

**能保存什么**和**这一轮该给模型看什么**是两个不同问题。

Stage 06 解决的是 retention 与 durability：哪些东西应该存在。

下一章 Stage 07 要解决的是 selection：面对这些已经存在的信息，这一次模型到底应该看到哪些。

这两个问题看起来挨得很近，但混在一起会让架构迅速失控。

数据库是仓库。

Context Window 是办公桌。

你可以在仓库里放一百箱资料，不代表每次开会都应该把一百箱一起倒在桌上。

---

## 14. 完整运行一次

本章完整代码在 `code/` 中。

先运行：

```bash
python stages/06-memory-persistence-hitl/code/demo.py
```

你会看到流程先暂停等待审批，然后由一个重新创建的 Runtime 从同一个 SQLite 文件恢复并完成执行；之后再经过 Memory Policy 写入一条显式长期偏好。

边界检查：

```bash
python stages/06-memory-persistence-hitl/code/checks.py
```

它覆盖了几个本章真正重要的不变量：Checkpoint 能跨对象重建恢复；Reject 不产生副作用；Edit 后重新验证；教学存储中的 effect key 保持幂等；Memory 默认不保存偶发信息；敏感候选被拒绝；不同 owner 的长期记忆互不串线。

---

## 15. 这一章真正应该带走什么

到这里，不需要背一堆数据库产品名。

更重要的是形成几组明确边界。

State 是运行时执行快照，Checkpoint 是 State 的持久化版本。

Checkpoint 主要服务“继续执行”，Long-term Memory 服务“跨会话保留经过选择的信息”。

模型可以提出 Memory Candidate，但不能因为它“觉得重要”就自行获得永久写入权。

Human Approval 可以批准、编辑或拒绝动作，但人工编辑后的参数仍要验证，而且 Approval 不能替代 Authorization。

Durable Resume 可以让新进程继续旧任务，但它不会自动让外部 Side Effect 获得 exactly-once 语义。

如果这些区别已经能自然说清楚，下一章的问题就出现了：

> **现在我们什么都能存了，可每一次调用模型时，到底该从这些东西里拿什么出来？**

这就是 Stage 07：Context Engineering。
