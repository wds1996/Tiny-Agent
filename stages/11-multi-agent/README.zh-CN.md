# Stage 11：一个 Agent 不够用？先证明你真的需要第二个——Multi-Agent

> Language: [English](README.md) | **简体中文**

Stage 10 让我们能比较一个 Agent 的答案、轨迹、延迟、成本与拒绝行为。现在才适合提出一个容易被架构图掩盖的问题：**拆成多个 Agent，是否确实改善了结果，还是只增加了调用、Context 传递和排错难度？**

Multi-Agent 不是“多调用几次模型”，也不是给同一模型换几段人格 Prompt。本章把它当成一种明确的系统设计：多个相对独立的执行主体各自接收任务和有限 Context，并在可观察、可授权、可评测的边界上协作。

这一章按如下顺序展开：

```text
先判断要不要拆
    ↓
定义 Specialist 的输入、输出和责任
    ↓
区分 Delegation 与 Handoff
    ↓
限制 Context、权限、预算和循环
    ↓
用 Eval 证明协作收益
    ↓
需要跨系统时，才讨论 A2A
```

本章展示的 Python 片段直接导入同目录的 `team.py`。若要逐段复制运行，先进入代码目录：`cd stages/11-multi-agent/code`，再启动 `python`；从仓库根目录直接运行完整示例时，使用对应知识点后给出的命令。

---

## 1. 第二个 Agent 要解决什么明确问题？

一个 ReAct Agent 在一次任务中调用模型三次，仍可以只是一个 Agent。出现第二个 Agent 的关键不是调用次数，而是出现了新的工作主体：它有不同的任务边界、所见 Context、可用 Tool、权限，或由另一个团队独立维护。

下面这些情况可能值得拆分：

| 需要解决的问题 | 合理的拆分方式 |
| --- | --- |
| 订单与政策需要不同资料、不同 Instructions | Orders Specialist 与 Policy Specialist |
| 子问题互不依赖 | Fan-out 后分别完成，再由 Supervisor 合并 |
| 高风险能力属于不同责任域 | 由具备相应审批、审计和 Tool 权限的 Specialist 处理 |
| 对方是另一个团队或系统维护的 Agent | 使用稳定的跨系统协议边界 |

以下理由不够：单 Agent Prompt 很乱却没有整理；框架示例画了很多框；给同一个模型取了五个角色名；或者希望“再加一个 Critic”自动变正确。拆分前先为单 Agent 与候选团队各跑同一份 Stage 10 Eval Dataset，比较通过率、错误类型、平均 Tool 数、延迟和成本。没有可测收益，就不应保留额外 Agent。

---

## 2. Specialist 不是人格，而是一条可检查的边界

本章的最小 `Agent` 接口只收任务和已投影的 Context，并返回结构化 `AgentMessage`。真正重要的是返回值不再是一段没有来源的自由文本：它带有执行者、状态、摘要、可传递数据和来源。

```python
from team import AgentMessage, Specialist

orders = Specialist("orders", "order specialist")
message = orders.run(
    "Check the order status.",
    {"order_id": "ORDER-42"},
)

assert message.agent == "orders"
assert message.status == "completed"
assert message.data == {"order_id": "ORDER-42"}
assert message.provenance == ("specialist:orders",)
print(message.summary)
```

这里的 `assert` 是 Python 断言：条件不成立时程序会报错。它让示例里的接口约定成为可执行检查。

真实系统的 `data` 可以是订单状态、检索到的证据 ID、文件引用或已验证的结构化结果；`provenance` 记录“这个结果从哪个 Specialist 或来源而来”。它们不能保证内容绝对正确，但能避免消息经过三次转述后只剩一句“有人说可以”。

值得拆分的 Specialist 至少应在任务、Context、Tool、权限、数据源或服务目标（SLA）中的一项上存在实际差异。不同的“语气”和“性格”可以是提示技巧，却不是可靠的系统边界。

---

## 3. Delegation 与 Handoff：谁还拥有总任务？

两个概念都像“交给另一个 Agent”，但控制权不同。

| 方式 | 语义 | 原任务的 Owner |
| --- | --- | --- |
| **Delegation** | “帮我做这个子任务，结果回来给我。” | Caller 保留 |
| **Handoff** | “接下来整个任务归你继续处理。” | Target 接手 |

下面是完整的最小运行时初始化与一次 Delegation。`Principal` 表示当前代表谁工作；`TeamPolicy` 明确授予 `support` 角色访问两个 Specialist 的权限。

```python
from team import (
    Delegation, Principal, Specialist, TeamBudget, TeamPolicy, TeamRuntime,
)

runtime = TeamRuntime(
    [
        Specialist("supervisor", "supervisor"),
        Specialist("orders", "order specialist"),
        Specialist("policy", "policy specialist"),
    ],
    policy=TeamPolicy({"support": frozenset({"orders", "policy"})}),
)
principal = Principal("user-7", frozenset({"support"}))
budget = TeamBudget()

result = runtime.delegate(
    caller="supervisor",
    principal=principal,
    delegation=Delegation("orders", "Check the order status.", ("order_id",)),
    shared_context={"order_id": "ORDER-42", "internal_secret": "do-not-send"},
    budget=budget,
)

assert result.agent == "orders"
assert result.data == {"order_id": "ORDER-42"}
assert budget.delegations == 1
```

`delegate()` 返回 Specialist 的 `AgentMessage`，不会改变顶层任务的 Owner。相反，`handoff()` 返回 `TeamResult`，其中 `owner` 会变成 Target：

```python
handed = runtime.handoff(
    caller="supervisor",
    principal=principal,
    target="orders",
    task="Take ownership of the order follow-up.",
    shared_context={"order_id": "ORDER-42", "user_id": "user-7"},
    context_keys=("order_id", "user_id"),
    budget=budget,
)

assert handed.owner == "orders"
assert handed.message.agent == "orders"
```

Handoff 不是“从此拥有永久权限”。它只是这次任务的控制权转移；Target 真正调用 Tool 时仍要经过 Stage 09 的参数、权限、审批、预算和 Deadline 检查。

---

## 4. Context Projection 与 Shared Memory：先问谁需要看、谁可以改

如果 Supervisor 持有如下数据：

```python
context = {
    "user_id": "user-7",
    "order_id": "ORDER-42",
    "policy_excerpt": "...",
    "internal_secret": "...",
}
```

Orders Specialist 只需订单号。`project_context()` 使用允许字段白名单，而不是“复制整个字典再希望对方别看”：

```python
from team import project_context

orders_context = project_context(context, allowed_keys=("order_id",))
assert orders_context == {"order_id": "ORDER-42"}
```

这叫 **Context Projection**：从较大的 Context 中投出某个角色完成工作所需的最小视图。它同时减少噪音、Token 和不必要的数据暴露，是 Stage 07 Context Engineering 在团队场景中的延伸。

“让所有 Agent 共享 Memory”并不是完整设计。至少还要回答：

| 问题 | 需要的明确规则 |
| --- | --- |
| 谁拥有这项信息？ | Owner 或 Namespace |
| 谁能读取？ | 按角色、任务或租户的 Read Policy |
| 谁能修改？ | Write Policy、版本或追加规则 |
| 这是真实事实还是中间推断？ | 类型、来源与置信度 |

不要使用 `shared_global_dict = {}` 作为跨 Agent 协作方案。它既没有最小暴露，也没有冲突、来源和写入语义。

---

## 5. Fan-out、Budget 与事件：团队也必须有边界

订单状态和退款政策相互独立时，可以先把它们分给不同 Specialist，再由 Supervisor 合并：

```text
Orders result ---\
                  -> Supervisor -> final answer
Policy result ---/
```

这叫 **Fan-out / Fan-in**。本章的 `fan_out()` 故意顺序运行多个 Delegation：它演示“任务可以独立”，却不假装“已经并发”。

```text
Fan-out      = 任务结构：哪些子问题可以独立完成
Concurrency  = 执行策略：是否同时启动、怎样限流、怎样取消
```

多 Agent 的循环更容易隐藏：`Supervisor → Reviewer → Planner → Supervisor`。`TeamBudget` 因此分别限制 Delegation 和 Handoff；后者单独计数，因为 Owner 转移是更强的控制变化。

```python
budget = TeamBudget(max_delegations=4, max_handoffs=1)
```

教学运行时会把成功的交接记成 `TeamEvent`，其中只含调用者、目标、投影字段和状态：

```text
TeamEvent(kind='delegation', caller='supervisor', target='orders',
          context_keys=('order_id',), status='completed')
```

这是一种结构化团队轨迹。生产实现应将它与 Stage 10 的 `agent.run`、`policy.authorize`、`team.delegate`、`team.handoff` Span 关联到同一个 `run_id`。仅靠“Agent failed”无法区分模型没有提议、策略拒绝、预算耗尽或 Specialist 失败。

教学代码会拒绝最直接的 `A → A` 自委托。更长的 `A → B → C → A` 环需要团队调用栈或全局图检测；无论实现方式，Budget 和 Trace 都不能省。

现在运行离线 Demo，观察两个 Specialist 分别得到什么 Context、Handoff 后 Owner 如何变化，以及每次交接留下的 `TeamEvent`：

```bash
python stages/11-multi-agent/code/demo.py
```

---

## 6. 内部协作也必须保留 Stage 09 的授权边界

“这些都是公司内部 Agent”不是授权理由。`TeamRuntime` 在每次 Delegation 和 Handoff 前检查 `TeamPolicy`：没有明确 Grant 就抛出 `PermissionError`，即默认拒绝。

```python
from team import Delegation, Principal, TeamBudget

intern = Principal("intern-1", frozenset({"intern"}))
try:
    runtime.delegate(
        caller="supervisor",
        principal=intern,
        delegation=Delegation("orders", "Check ORDER-42."),
        shared_context={},
        budget=TeamBudget(),
    )
except PermissionError as exc:
    print(exc)
```

这里检查的是“这个身份能否进入 Orders Specialist 边界”。它不替代 Orders 自己执行 Tool 时的授权：如果 Orders 能退款，退款 Tool 仍必须在自己的执行边界再次检查 Principal、业务策略和必要审批。Delegation 不能把 Supervisor 没有的外部执行权悄悄放大。

---

## 7. Critic、错误传播与 Eval：协作收益需要证据

增加 Critic 很诱人：

```text
Generator -> Critic -> final
```

但 Critic 也可能误判、遗漏证据或制造新循环，并且一定增加一次模型调用的成本和延迟。它不是免费的正确性按钮。

用 Stage 10 的同一 Dataset 比较：

```text
single Agent:  pass rate / latency / cost / unnecessary tools
team version:  pass rate / latency / cost / unnecessary delegations
```

只有在关键 Case 的收益足以覆盖额外成本与失败路径时，才保留 Critic 或额外 Specialist。

消息必须尽量保留 `status`、`data` 与 `provenance`，因为每次自然语言转述都可能丢失事实、来源、不确定性和错误类别。出现失败时，Supervisor 不应把 “policy service timed out” 重写成 “policy says no”；应将结构化失败状态交给自己的恢复或上报逻辑。

相应的离线检查放在这里运行。它会验证 Context Allowlist、结构化消息、Delegation 与 Handoff、默认拒绝、Budget、Self-delegation、Unknown Agent 与 Fan-out 的隔离 Context：

```bash
python stages/11-multi-agent/code/checks.py
```

---

## 8. MCP、进程内团队与 A2A 分别解决什么边界？

三者常一起出现，却不是一回事：

| 边界 | 主要对象 | 本课程对应内容 |
| --- | --- | --- |
| Agent ↔ Tool / Resource | 工具、数据、Prompt Provider | Stage 05 MCP |
| Agent ↔ Agent（同一应用内） | Supervisor 与 Specialist 的协作 | 本章 `TeamRuntime` |
| Agent ↔ 独立 Agent 系统 | 跨团队、框架或服务的互操作 | A2A |

如果对方只暴露 `search_database`，它更像 Tool；如果对方接收目标、自己规划执行、维护任务生命周期并返回 Artifact 或阶段状态，它更像独立 Agent。

当对方属于另一个系统时，进程内的 `runtime.delegate(...)` 不够用。A2A（Agent2Agent）是面向独立 Agent 系统互操作的开放协议：它定义能力发现、消息、任务状态和 Artifact 交换，但不会替你决定是否应该拆分、是否可信、或是否有权限。可继续阅读 [A2A 官方规范](https://a2a-protocol.org/latest/specification) 与 [核心概念](https://a2a-protocol.org/latest/topics/key-concepts/)。

因此 A2A 与 MCP 是互补关系：一个 Specialist 可以通过 MCP 使用自己的 Tool 和数据，再通过 A2A 与其他独立 Agent 协作。

---

## 9. 真实 DeepSeek 团队：Supervisor 委托两个真实 Specialist

离线 `Specialist` 让我们稳定地观察 Runtime 语义。真实模型接入在 [`code/deepseek_team.py`](code/deepseek_team.py)：

1. DeepSeek Supervisor 根据用户任务提出 `delegate_to_specialist` Tool Call。
2. Host 验证目标和任务，按 `CONTEXT_KEYS_BY_SPECIALIST` 投影 Context，并通过 `TeamRuntime.delegate()` 做授权与 Budget 检查。
3. Orders 或 Policy Specialist 各自发起一次真实 DeepSeek 调用，只接收自己的投影视图。
4. Host 将结构化 `AgentMessage` 作为 Tool Result 交回 Supervisor，由它生成最终回答。

```text
user
  ↓
DeepSeek supervisor
  ↓ delegate_to_specialist
Host policy + context projection + budget
  ↓
DeepSeek orders / policy specialist
  ↓ structured Tool Result
DeepSeek supervisor final answer
```

示例里的 `order_id` 与 `policy_excerpt` 是本地教学数据；`internal_secret` 故意存在于 Supervisor Context 中，用来观察它不会被投影给 Specialist。它不会连接订单或支付系统。

安装依赖：

```bash
python -m pip install -r stages/11-multi-agent/code/requirements.txt
```

Windows 命令提示符（CMD）：

```bat
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/11-multi-agent/code/deepseek_team.py
```

PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/11-multi-agent/code/deepseek_team.py
```

真实模型的结果会受模型版本和服务状态影响，因此这里的 live run 是集成观察，不应取代 Stage 10 的固定回归测试。

---

## 10. 从团队协作进入 Agent Workspace

Multi-Agent 并没有让任务只剩下聊天。随着 Agent 开始生成 Artifact、读写文件、运行测试和执行脚本，下一个问题变成：**它到底能碰到机器上的哪些文件、进程、网络与凭证？**

这就是 [Stage 12：Agent Workspace 与 Sandbox](../12-agent-workspace-sandbox/README.zh-CN.md)。
