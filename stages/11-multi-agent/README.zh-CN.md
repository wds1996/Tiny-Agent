# Stage 11：一个 Agent 不够用？先证明你真的需要第二个——Multi-Agent

> Language: [English](README.md) | **简体中文**

前十章，我们一直在努力把**一个 Agent**做好。它有清楚的 Tool 边界，有 Workflow 和 Graph，有 RAG、MCP、Memory、Context、Skills，也有 Guardrails、Trace 和 Eval。

这时终于可以聊一个特别容易让架构图突然变热闹的话题：Multi-Agent。

典型会议现场大概是这样：这个任务有点复杂，那拆成三个 Agent？三个会不会不够高级？那五个。五分钟以后，白板上出现 Supervisor、Researcher、Planner、Critic、Executor、Reviewer，箭头像春节高速公路。

问题是：

> **为什么一个设计良好的 Agent 不够？**

如果这个问题答不清，Multi-Agent 往往不是能力升级，而是把一个 Debug 问题变成五个 Debug 问题再加一层网络关系。所以 Stage 11 从怀疑开始。

---

## 1. 多个模型调用，不等于 Multi-Agent

一个 Agent 在 ReAct 循环里调用模型三次，仍然可以只是一个 Agent。

Multi-Agent 的关键不是“模型调用次数”，而是系统里出现了多个**相对独立的工作角色或执行主体**，它们拥有各自的任务边界、上下文和责任。

例如 Supervisor 把政策解释交给 Policy Specialist。Specialist 得到一个明确子任务，返回结果，然后 Supervisor 继续拥有原任务。这才开始接近 Multi-Agent 协作。

---

## 2. 什么时候第二个 Agent 才值得存在？

比较合理的理由包括：专业化真的需要不同 Instructions、Context 或 Tools；权限边界明显不同；任务天然可以分成相互独立的子问题；或者对方本来就是另一个团队维护的独立 Agent 系统。

不太好的理由则包括：名字听起来高级、框架示例就是这么画、单 Agent Prompt 太乱但没人愿意整理，或者想把一个大函数改成五个大函数。

Multi-Agent 应该解决明确问题，而不是用来掩盖单 Agent 设计没整理好。

---

## 3. Specialist：先从最简单的角色分工开始

本章定义一个极小接口：

```python
class Agent(Protocol):
    name: str

    def run(
        self,
        task: str,
        context: Mapping[str, str],
    ) -> str:
        ...
```

然后有 `supervisor`、`orders`、`policy`。每个 Agent 接一个 Task 和被投影过的 Context。

注意这里没有“共享整个全局 State”。这是故意的。

Multi-Agent 的第一道题不应该是“怎样让大家什么都知道”，而应该是：

> **这个 Agent 完成自己的子任务到底需要知道什么？**

这和 Stage 07 的 Context Engineering 是直接相连的。

---

## 4. Delegation：我请你做一部分，但总任务还是我的

Delegation 可以理解成 Supervisor 说：“帮我查一下 ORDER-42 的状态，结果告诉我。”

```python
Delegation(
    target="orders",
    task="Check the order status.",
    context_keys=("order_id",),
)
```

Orders Agent 做完以后，结果回给 Supervisor。

```text
Supervisor owns task
    ↓ delegates subtask
Orders Agent works
    ↓ returns result
Supervisor continues
```

所以 Delegation 的关键是：**Caller 保留原任务控制权。**

---

## 5. Handoff：这次真的把接力棒交出去

Handoff 不一样。例如客服 Supervisor 判断“接下来整个订单跟进都应该交给 Orders Agent”。

```python
result = runtime.handoff(
    caller="supervisor",
    target="orders",
    task="Take ownership of the order follow-up.",
    ...
)
```

返回：

```python
TeamResult(
    owner="orders",
    ...
)
```

这里 Owner 发生变化。

可以这样记：

```text
Delegation
    -> 帮我做一部分，回来告诉我

Handoff
    -> 这件事接下来归你
```

两者都叫 Agent 协作，但控制权完全不同。如果一个框架把它们都包装成相似 API，你仍然应该知道自己设计的是哪一种。

---

## 6. Context Projection：不要把 Supervisor 的整间办公室搬过去

假设共享数据有：

```python
context = {
    "user_id": "user-7",
    "order_id": "ORDER-42",
    "policy_excerpt": "...",
    "internal_secret": "...",
}
```

Orders Agent 只需要 `order_id`。为什么要把 `internal_secret` 一起给它？

本章使用白名单投影：

```python
project_context(
    context,
    allowed_keys=("order_id",),
)
```

得到：

```python
{"order_id": "ORDER-42"}
```

Context Projection 同时减少 Context 噪音和不必要的数据暴露。因此 Multi-Agent 并没有让 Stage 07 失效，恰恰相反，Agent 越多，Context Engineering 越重要。

---

## 7. “共享 Memory”也是一句需要拆开的需求

有人会说“这些 Agent 共用 Memory 就好了”。先问清楚什么叫共用。

Policy Agent 是否应该看到用户所有私人偏好？Billing Agent 写入的执行状态，Research Agent 是否可以修改？一个 Agent 产生的总结，是事实，还是它自己的中间判断？

Multi-Agent 系统里，Shared State 很容易从“方便”变成“谁都能改的一张白板”。

更稳妥的思路是明确 Owner、Namespace、Read/Write 权限，并只投影必要信息，而不是放一个 `shared_global_dict = {}` 然后祈祷大家有团队精神。

---

## 8. Fan-out / Fan-in：有些子任务天然可以并列做

订单状态和退款政策可以分别交给 Orders Agent 与 Policy Agent：

```text
Order Result ---\
                 -> Supervisor -> final
Policy Result --/
```

前半段是 Fan-out，结果回来合并是 Fan-in。

本章 `fan_out()` 为了保持教学确定性，**顺序执行**两个 Delegation。为什么不立刻上并发？因为：

```text
Fan-out 是任务结构
Concurrency 是执行策略
```

两者不是同一件事。先理解“这些子任务彼此独立”，再决定是否值得并发。

---

## 9. Multi-Agent 也要 Budget

单 Agent 会 Loop，多个 Agent 当然也会，而且方式更多：

```text
Supervisor -> Reviewer
Reviewer   -> Planner
Planner    -> Supervisor
Supervisor -> Reviewer
...
```

看起来大家都很忙，任务一点没动。

于是：

```python
TeamBudget(
    max_delegations=4,
    max_handoffs=1,
)
```

分别限制 Delegation 与 Handoff。Handoff 单独限制，是因为 Owner 转移属于更强的控制变化。

---

## 10. Self-delegation 是最容易发现的环

本章直接拒绝 `Agent A -> Agent A`。更复杂的 `A -> B -> C -> A` 则需要全局 Delegation Trace 或调用栈识别。

教学代码没有假装解决所有图环检测，但先建立同一原则：

> **Multi-Agent 自主度也必须有边界和可观察轨迹。**

Stage 10 的 Trace 在这里再次变得重要。

---

## 11. Specialist 不等于“人格不同”

一个常见 Demo 会定义“严肃专家”“创造力专家”“批判性专家”，然后三个人讨论。

这有时能产生不同视角，但不同人格描述不是强架构边界。

真正值得拆分的 Specialist 往往还应该在任务、Context、Tool、权限、数据源或 SLA 上有差异。否则三个 Agent 只是同一个模型戴了三顶帽子。

---

## 12. Critic Agent 不是免费的正确性按钮

再加一个 Reviewer / Critic 很诱人：

```text
Generator
    ↓
Critic
    ↓
Final
```

但 Critic 也可能错，还会增加 Cost、Latency 和新的失败路径。

所以要回到 Stage 10：**它在固定 Eval Dataset 上真的提高结果了吗？**

如果没有可测收益，就不要因为 “Self-reflection” 听起来漂亮而永久多加一次模型调用。

---

## 13. Multi-Agent 的错误传播更难

Orders Agent 返回错误信息，Supervisor 总结一次，Policy Agent 又根据总结做判断，最后用户看到第三手信息。

每一次交接都可能丢事实、来源、不确定性和错误类型。

所以 Agent-to-Agent Message 最好不要只传一段自由文本。可以保留 Task、Result、Provenance、Status 和 Structured Data。

和前面几章一样：边界越重要，越值得结构化。

---

## 14. 权限不要因为“内部 Agent”就消失

如果 Billing Agent 能退款，Supervisor 不能直接退款，那么 Supervisor Delegates to Billing 也不代表 Supervisor 自动继承 Billing 权限。

Billing 自己仍然应该在执行边界检查 Principal、Approval 或业务策略。

“这是我们自己系统里的另一个 Agent”不是 Authorization。

---

## 15. Multi-Agent 和 MCP 的区别

MCP 解决：

```text
Agent / Host
    ↕
Tool / Resource / Prompt provider
```

Multi-Agent 协作解决：

```text
Agent
    ↕
another Agent
```

如果对方只是暴露一个 `search_database` 能力，它更像 Tool；如果对方接受目标、自己规划执行、维持任务生命周期、返回 Artifact 或阶段状态，它更像独立 Agent。

不要因为所有远程调用都走 HTTP 就把它们当成同一层。

---

## 16. 独立 Agent 跨系统以后，需要协议边界

在同一个 Python 程序里，我们可以直接调用 `runtime.delegate(...)`。

但如果对方 Agent 属于另一个团队、另一个框架或另一个服务，就需要稳定的 Agent-to-Agent 交互协议。

当前 A2A 标准就是为这种**独立 Agent 系统之间的互操作**设计的：能力发现、消息、任务状态和产物交换可以跨实现边界。

这里不急着把本章变成 A2A SDK 教程。最重要的是先分清：

```text
internal Team Runtime
    -> 进程内的协作抽象

A2A-style protocol boundary
    -> 独立 Agent 系统之间的互操作
```

协议不会替你决定该不该拆 Multi-Agent，也不会自动建立信任。

---

## 17. A2A 和 MCP 为什么互补？

可以用一句话记：

```text
MCP
    -> Agent 去接 Tool / Data

A2A
    -> Agent 去接另一个 Agent
```

一个 Specialist Agent 自己内部完全可以使用 MCP。不同协议服务不同边界。

---

## 18. 运行本章

```bash
python stages/11-multi-agent/code/demo.py
python stages/11-multi-agent/code/checks.py
```

Demo 先让 Supervisor 分别委托 Orders 与 Policy Specialist，再演示一次 Handoff。

检查覆盖 Context Projection Allowlist、Delegation 不改变 Owner、Handoff 改变 Owner、Self-delegation、Delegation/Handoff Budget、Unknown Agent，以及 Fan-out 中每个 Specialist 只得到自己的 Context。

---

## 19. 为什么下一章是 Workspace / Sandbox？

Multi-Agent 并没有让所有任务都变成聊天。

随着 Agent 开始做更长、更复杂的任务，它们经常需要读写文件、生成 Artifact、运行测试、执行脚本、操作临时目录。Stage 08 的 Skill 甚至可能携带 Script。

这时一个危险问题终于不能再绕开：

> **如果让 Agent 真的操作文件和运行代码，它到底能碰到这台机器的多少东西？**

所以下一章 Stage 12，我们给 Agent 一张工作台，但不会顺手把整台电脑的钥匙也塞给它。
