# Stage 15：毕业设计——做一个真的会查政策、查订单、申请退款的 Support Agent

> Language: [English](README.md) | **简体中文**

终于到最后一章了。

如果这是普通教程，毕业设计很容易写成一场技术阅兵：

```text
LangGraph
+ RAG
+ MCP
+ Memory
+ Skills
+ Multi-Agent
+ Sandbox
+ Long-Horizon
+ 再放一个向量数据库
+ 最后画一张有 27 个方框的架构图
```

看起来什么都学会了。

但真实工程里，一个系统最危险的习惯之一，就是“因为我会，所以我就加”。

这门课从 Stage 00 一直强调的并不是“功能越多越像 Agent”，而是另一件事：

> **先弄清当前问题，再给模型刚好够用的决策权、信息和执行能力。**

所以毕业设计不做万能企业 Agent。

我们做一个很具体的 **Support Agent**。它负责三类事情：回答退款政策问题、读取当前用户自己的订单、在符合政策时提出退款申请。真正退款属于金融副作用，因此必须暂停等待人工审批。

就是这么一个看起来并不宏大的场景，已经足够把前面十四章真正串起来。

更重要的是，它还能检验我们有没有学会做减法。

---

## 1. 先写业务题，不要先写架构图

用户可能问：

> “ORDER-42 还能原路退款吗？”

也可能直接说：

> “请退款 ORDER-42。”

系统需要知道订单是谁的、订单多久以前创建、退款政策是什么。

如果证据足够，它可以解释。

如果用户真的要求退款，它可以**提出**退款动作。

但是它不能直接动钱。

于是这个毕业设计最核心的业务路径是：

```text
用户问题
    ↓
模型做语义决策
    ↓
需要订单？
    ↓
读取当前身份可访问的订单
    ↓
需要政策？
    ↓
检索政策证据
    ↓
证据是否足够？
    ├── 不够 → abstain
    └── 足够
          ↓
        只是问政策？
          ├── 是 → grounded answer
          └── 否 → structured refund proposal
                        ↓
                  waiting approval
                        ↓
                approve / edit / reject
                        ↓
                  bounded side effect
```

先看业务链，你会发现没有任何地方天然要求五个 Agent。

也没有地方要求运行 Shell。

没有理由，就不加。

这就是最后一章第一条毕业标准：

> **架构是业务约束长出来的，不是课程目录堆出来的。**

---

## 2. 这一章到底用了前面的哪些东西？

Support Agent 会真实用到这些机制：

| 已学机制 | 在毕业设计里的作用 |
|---|---|
| Structured Decision | 模型提出 Support Decision |
| Tool Boundary | 订单查询属于应用拥有的能力 |
| Workflow / Runtime | 决策和执行分开 |
| Explicit State / Trace | 每一步可以被解释 |
| RAG | 政策来自外部证据 |
| Durable Store | Run 与退款结果可恢复 |
| HITL | 退款必须审批 |
| Context / Evidence Boundary | 只根据需要的订单与政策作答 |
| Reliability | 身份隔离、参数验证、幂等 |
| Evaluation | 用确定性 Case 检查关键不变量 |

但是它**没有**使用：

```text
Multi-Agent
arbitrary Skill execution
Shell / Sandbox
Long-Horizon Lease
```

原因不是这些机制不好。

原因是当前 Support Flow 并没有证明需要它们。

如果以后出现一个独立 Fraud Review Team Agent，Multi-Agent / A2A 可能有意义。

如果任务要在用户仓库里修改代码，Workspace / Sandbox 会有意义。

如果一笔 Case 要持续三天并跨多个 Worker，Long-Horizon Harness 会有意义。

现在没有。

毕业以后，真正重要的能力不是“每个项目都把学过的东西全用上”，而是知道什么时候**不要用**。

---

## 3. 模型仍然只负责“判断”，不是负责“执行”

我们先定义：

```python
@dataclass(frozen=True, slots=True)
class SupportDecision:
    kind: DecisionKind
    order_id: str | None = None
```

`kind` 可能是：

```text
greeting
refund_question
refund_action
policy_question
```

然后定义边界：

```python
class DecisionModel(Protocol):
    def decide(self, question: str) -> SupportDecision:
        ...
```

这一步和 Stage 02 的 Router、Stage 01 的 Model Protocol 是同一条设计思想。

Support Agent 不关心 Provider 怎么产生这个 Decision。

它只接受一个结构化结果。

本章离线代码使用：

```python
DeterministicDecisionModel()
```

它是一个 **Model Double**。

它用规则稳定地产生 `SupportDecision`，方便我们在没有 API Key、没有网络、没有随机性的情况下检查整个 Agent Runtime。

真实系统可以把这个 Adapter 换成一个基于 LLM Structured Output 的实现。

但是无论换成什么模型，下面这件事不能变：

```text
DecisionModel
    -> 提出 refund_action

Application
    -> 查订单
    -> 查政策
    -> 决定能不能形成 Proposal
    -> 决定是否需要审批
    -> 执行最终 Side Effect
```

模型不是因为输出了 `"refund_action"`，就直接拿到了退款权限。

这条边界从 Stage 00 到毕业设计都没有变。

---

## 4. 为什么毕业设计还要保留 Model Double？

有人可能会说：

> “最后一章还用 Deterministic Model，不够真实吧？”

恰恰相反，它让“模型层”和“系统层”被分别测试。

假设真实 LLM 今天把：

> “请告诉我退款政策。”

误分类为：

```text
refund_action
```

这是 Decision Quality 的问题。

但如果 System 在得到这个 Decision 后，竟然绕过订单查询、绕过政策、绕过审批直接退款，那是 Runtime Authority 的问题。

两类问题不能揉成一句：

> “模型不稳定。”

有 Model Interface 以后，你可以分别测试：

```text
LLM Decision Accuracy
```

和：

```text
Runtime Safety Invariants
```

生产系统最怕的是，每个 Bug 最终都被归类成“模型偶尔会这样”。

那不是 Root Cause Analysis。

那是把模型当垃圾桶。

---

## 5. Trusted Identity：订单不是谁知道 ID 谁就能查

订单数据：

```python
Order(
    order_id="ORDER-42",
    tenant_id="acme",
    user_id="alice",
    amount="49.00",
    age_days=12,
    status="paid",
)
```

当前身份：

```python
TrustedIdentity(
    tenant_id="acme",
    user_id="alice",
)
```

查询时不是：

```python
ORDERS[order_id]
```

然后全部返回。

而是：

```text
找到订单
    ↓
tenant 匹配？
    ↓
user 匹配？
    ↓
才作为当前请求可见数据
```

如果 Bob 问：

> “ORDER-42 能退款吗？”

Agent 返回：

```text
I cannot find an accessible order with that ID.
```

而不是：

```text
这是 Alice 的订单，金额 49 元，你没权限。
```

为什么连“属于 Alice”都不说？

因为 Unauthorized Caller 不应该因为猜中一个 ID，就额外获得“这个对象真实存在，而且属于谁”的信息。

Stage 13 的 Tenant Boundary 到这里变成了业务代码的一部分。

---

## 6. 用户说“退 9999”，不能覆盖系统里的订单金额

这是一个很经典的 Authority Boundary。

用户发送：

> “Please refund ORDER-42 for 9999.”

模型可能认真地抽取：

```text
order_id = ORDER-42
requested_amount = 9999
```

真正退款金额应该从哪里来？

当前订单系统。

本章的 Agent 在形成 Proposal 时使用：

```python
order.amount
```

而不是用户文本里的数字。

最终：

```python
ApprovalRequest(
    order_id="ORDER-42",
    amount="49.00",
)
```

这就是一个很重要的数据来源原则：

> **低信任输入可以表达意图，但高影响事实应该从权威数据源重新读取。**

用户可以说“我想退 9999”。

他不能通过把数字写进 Prompt，就改写订单数据库里的实际支付金额。

---

## 7. 政策答案必须有 Evidence

我们有三个政策文档：

```text
refund-within-30-days
refund-after-30-days
standard-shipping
```

Policy Retriever 返回：

```python
Evidence(
    id="refund-within-30-days",
    text="...",
    score=...
)
```

最终答案会带 Evidence ID：

```text
ORDER-42 is 12 days old.
Paid orders within 30 days may be refunded...
Evidence: [refund-within-30-days]
```

这不是为了让字符串看起来更学术。

它建立了一个最小 Provenance：

```text
这个结论
    ↓
来自哪份证据
```

如果答案后来出现问题，我们至少知道它依据的是哪一条政策。

---

## 8. Retriever 找不到时，Agent 应该停下来

用户问：

> “月球瞬移商品的保修政策是什么？”

当前 Corpus 里没有任何相关内容。

一个很会聊天的模型完全可以写出：

> “通常月球瞬移商品享有 14 天量子保修……”

听起来甚至挺像回事。

毕业设计不允许这么干。

Retriever 返回空，系统进入：

```text
answer:abstain
```

最终：

```text
I do not have enough policy evidence to answer reliably.
```

注意，我们不是要求模型“尽量谨慎”。

这是 Runtime 的明确分支。

这一点非常关键：

> **Abstention 不是一种语气，而是一种系统行为。**

---

## 9. 相似度返回第一名，不等于证据自动充分

Stage 04 已经讲过：Retrieval Score 只是排序信号。

因此毕业设计不会写：

```python
evidence = retriever.retrieve(...)
answer(evidence[0])
```

然后就认为万事大吉。

在 Refund Flow 里，我们甚至进一步按具体政策 ID 选择：

```text
订单 <= 30 天
    -> refund-within-30-days

订单 > 30 天
    -> refund-after-30-days
```

为什么？

因为业务 Runtime 已经拿到了明确的 `age_days`。

普通代码能够确定的东西，不需要重新让模型猜。

这正是 Stage 02 的思想：

> **能确定性完成的控制逻辑，继续留在代码里。**

---

## 10. 一个 12 天订单和一个 45 天订单，控制流不一样

`ORDER-42`：

```text
age_days = 12
```

所以：

```text
within 30 days
    -> 可以进入原路退款流程
```

`ORDER-99`：

```text
age_days = 45
```

政策明确说：

```text
After 30 days,
an original-payment refund is not available.
Support may offer store credit after review.
```

于是用户即使说：

> “Please refund ORDER-99.”

系统也不会生成 Refund Approval。

它返回 Policy Answer。

这里有一个很重要的细节：

> **Approval 不是用来把“不允许的动作”变成允许。**

审批发生在 Policy 已允许进入执行流程以后。

如果业务规则已经说“原路退款不可用”，就不应该用“要不找个人点一下同意”绕过去。

---

## 11. Refund Proposal 为什么必须绑定精确参数？

符合政策以后，Agent 创建：

```python
ApprovalRequest(
    run_id=...,
    order_id="ORDER-42",
    amount="49.00",
    reason="Refund changes external financial state.",
)
```

审批的不是：

```text
“让这个 Agent 处理退款”
```

而是：

```text
“允许这个 Run
对 ORDER-42
执行 49.00 的退款”
```

范围越具体，Approval 越有意义。

这就是 Stage 06 的“Exact Approval Binding”。

---

## 12. Edit 可以存在，但不能把权限越改越大

审批人可以修改金额。

比如 Proposal 是：

```text
49.00
```

Reviewer 可以改成：

```text
40.00
```

但是不能改成：

```text
500.00
```

代码会重新验证：

```python
if edited_value > proposed_value:
    raise ValueError(
        "edited amount cannot exceed the proposed refund"
    )
```

为什么？

因为人工编辑也是输入。

而且 Approval Flow 里的 Edit 不是新的任意指令通道。

它只能在应用允许的边界内修改。

---

## 13. Reject 必须真的意味着“没有副作用”

Reviewer 选择：

```python
ApprovalDecision(
    outcome="reject"
)
```

系统更新 Run：

```text
status = rejected
```

并且：

```text
effects count = 0
```

这不是文档约定。

Checks 会实际验证。

Agent 系统里，最值得写测试的往往不是 Happy Path，而是：

> **“不该发生的时候，它真的没发生吗？”**

---

## 14. Approve 以后也要 Idempotency

一个 Refund Run 被批准。

系统调用：

```python
record_refund_once(...)
```

Key 是：

```text
{run_id}:refund
```

第一次执行，写入 Effect。

如果相同 Run 又收到一次 Resume：

```text
status 已经 completed
    ↓
不重复执行
```

Effect Count 仍然是 1。

这仍然只证明教学 Store 内部的幂等语义。

真实 Payment Provider 应有自己的 Idempotency Contract。

但是毕业设计至少不会犯一个最基础的错：

```text
“收到 Approve 消息”
    ↓
每收到一次就退一次
```

---

## 15. Run 也有身份作用域

Store 读取：

```python
get_run(
    run_id,
    tenant_id=identity.tenant_id,
    user_id=identity.user_id,
)
```

Alice 创建的 Refund Run，Bob 不能拿同一个 `run_id` Resume。

这把 Stage 13 的 Trusted Identity 一直带到了 Side Effect 恢复流程。

身份边界不能只在 API 第一层检查一次，然后内部所有函数开始相信“既然进来了应该都没问题”。

越靠近副作用，权限上下文越应该清楚。

---

## 16. Trace 不需要等到出事故才想起来

每个结果带一个小型 Trace：

```text
model:decision:refund_action
tool:lookup_order
retrieval:refund_policy
proposal:refund
approval:waiting
```

Resume 后：

```text
resume:refund
approval:approved
effect:refund_completed
```

它非常简单。

没有分布式 Trace Backend。

但已经能回答：

> “这个结果为什么走到这里？”

这就是 Stage 10 的核心思想。

Observability 不一定从昂贵平台开始。

它首先从清楚的责任边界开始。

---

## 17. Context Engineering 在这里不是一个独立大类，而是一种习惯

这个 Capstone 没有单独复制 Stage 07 的完整 ContextBuilder。

为什么？

因为当前 DecisionModel 只需要 User Question；订单信息和政策证据由 Runtime 在需要时 JIT 获取。

如果换成真实 LLM 做最终 Grounded Answer，Context 应该只包含：

```text
current question
authorized order facts
selected policy evidence
answering instructions
```

不需要把用户所有 Memory、历史 Run、全部政策和整个订单数据库塞进去。

Stage 07 学到的东西，到毕业设计以后最好已经不是“某个类必须 import”，而是设计习惯。

---

## 18. MCP 为什么也没有强行出现？

订单查询和政策数据在教学代码里都是本地实现。

生产环境里完全可能是：

```text
Order Service
    -> MCP Tool / ordinary service adapter

Policy Knowledge Base
    -> remote Retriever / MCP Resource
```

但 Capstone 的核心边界不会变。

如果我们为了展示 Stage 05，特意启动一个 MCP Server，再通过网络调回同一进程里的两个字典，只会让教学代码更长，不会让架构更正确。

真正学会协议，不是每个函数都要套协议。

而是知道：

> **当能力真的跨系统边界时，该在哪里放协议 Adapter。**

---

## 19. 为什么没有 Multi-Agent？

退款支持场景完全可以画成：

```text
Supervisor Agent
Order Agent
Policy Agent
Refund Agent
Approval Agent
```

听起来很热闹。

但当前任务的专业边界没有强到需要五个独立 Task Owner。

订单查询是 Tool。

政策检索是 Retriever。

退款批准是 HITL Workflow。

把它们升级成 Agent，并没有自动获得更好的 Accuracy 或权限隔离。

所以基础 Capstone 使用一个 Support Agent。

如果以后 Fraud Review 真的由另一个团队维护一个独立 Agent，它有自己的模型、数据、权限和任务生命周期，这时再引入 Delegation / A2A 就合理了。

这就是 Stage 11 最终要教的判断能力。

---

## 20. 为什么没有 Sandbox？

Support Agent 不需要修改代码、运行 Shell，也不需要执行用户上传 Script。

那就不提供。

没有 Shell，本身就是一种非常好的 Shell Security Policy。

最小权限经常意味着：

> **根本不要暴露那项能力。**

这比先给 `bash`，然后写两千字 Prompt 告诉模型“请不要做危险操作”可靠得多。

---

## 21. 为什么没有 Long-Horizon Harness？

这个核心流程很短：

```text
Decision
Order Lookup
Policy Retrieval
Approval
Refund
```

唯一可能长时间等待的是人工审批。

Stage 06 的 Durable Run 已经足够承载它。

没有多个长时间 Work Unit，也没有 Worker Lease Reclaim 的需要。

所以不引入 Stage 14 Harness。

如果未来 Support Case 会自动收集多份证据、联系多个外部团队、等待异步资料、跨天生成复杂 Artifact，那时再升级成 Long-Horizon Task。

架构应该随问题增长，而不是一次性预装未来十年的可能性。

---

## 22. 运行毕业项目

先运行：

```bash
python stages/15-capstone-enterprise-agent/code/demo.py
```

你会看到第一条请求：

```text
Can ORDER-42 be refunded to the original payment method?
```

Agent：

```text
model decision
    ↓
lookup ORDER-42
    ↓
retrieve refund policy
    ↓
grounded answer + evidence
```

然后：

```text
Please refund ORDER-42.
```

系统进入：

```text
waiting_approval
```

人工 Approve 后，退款 Effect 只执行一次。

---

## 23. 运行毕业检查

```bash
python stages/15-capstone-enterprise-agent/code/checks.py
```

检查覆盖九个关键不变量。

第一，Policy Answer 必须带 Evidence ID。

第二，未知政策必须 Abstain。

第三，订单读取受 Trusted Identity 限制。

第四，退款金额来自订单事实，不来自用户随口写的数字。

第五，超过 30 天的订单不会产生原路退款 Approval。

第六，Reject 不执行任何 Refund Effect。

第七，Edit 不能把退款金额扩大到原 Proposal 以上。

第八，同一 Run 重复 Resume 不重复退款。

第九，一个用户不能读取另一个用户的 Durable Run。

这九条比“Demo 看起来挺顺”更能说明系统做对了什么。

---

## 24. 真实 LLM 应该接在哪里？

如果把 Model Double 换成真实模型，最自然的位置就是：

```python
class DecisionModel(Protocol):
    def decide(
        self,
        question: str,
    ) -> SupportDecision:
        ...
```

真实 Adapter 使用 Structured Output 返回受约束的：

```json
{
  "kind": "refund_action",
  "order_id": "ORDER-42"
}
```

然后 Application 继续执行后面的流程。

不要让 Provider Adapter 顺手：

```text
查数据库
读政策
批准退款
写 Effect
```

Provider Adapter 的职责只是：

```text
Provider-specific response
    ↕
Application-owned decision model
```

课程学到最后，边界应该越来越窄，而不是越来越混。

---

## 25. 真正的 Production 版本还缺什么？

毕业并不意味着“这个 Demo 可以明天接银行生产流量”。

真实系统仍然需要根据部署环境补充很多东西，例如真实认证、外部订单服务、可靠的支付幂等、数据库迁移、Secret 管理、服务级 Trace、真实模型 Adapter、Provider Rate Limit、Policy Corpus 生命周期、在线 Eval、完整 Authorization、审计记录和数据保留规则。

但是注意表达方式。

不是：

> “我们还差一万个功能，所以前面白学了。”

而是：

> **我们已经知道这些新增能力分别属于哪一层，不需要重新把系统揉成一团。**

这就是整门课真正的目标。

---

## 26. 从 Stage 00 再走一次，你会看到什么？

最开始：

```text
User
    ↓
Model
    ↓
Text
```

Stage 00 让输出第一次有契约，也第一次能提出 Tool Call。

Stage 01 把一次 Tool Call 变成有边界的 Agent Runtime。

Stage 02 开始问：哪些控制权应该留在普通程序里？

Stage 03 把复杂执行状态显式化成 State / Graph。

Stage 04 让 Agent 不再闭卷考试，学会从外部证据回答。

Stage 05 把外部能力边界标准化成 MCP。

Stage 06 让执行和 Memory 能跨时间留下，并允许人在关键动作前接管。

Stage 07 告诉我们：能保存很多信息，不等于每轮都该给模型看。

Stage 08 把可复用 Procedure 做成按需加载的 Skill。

Stage 09 开始系统限制权限、失败、Retry、Budget 和 Deadline。

Stage 10 让“感觉更好了”变成可以被 Trace 与 Eval 验证的说法。

Stage 11 终于讨论什么时候值得拆成多个 Agent。

Stage 12 给代码与文件执行建立 Workspace / Sandbox 心智模型。

Stage 13 把单机程序变成有身份、Queue、Backpressure 和 Durable Run 的服务。

Stage 14 让长期任务脱离某一个 Worker，能够靠 Ledger / Lease / Artifact 换班继续。

最后 Stage 15 做的事情反而变简单了。

我们拿出这些工具，只选择真正需要的那几件。

这就是从“会调用 Agent Framework”到“会设计 Agent System”的区别。

---

## 27. 最后一张架构图

我们的 Support Agent 最终可以画成：

```text
                   Trusted Identity
                          │
                          v
User Question --> DecisionModel
                          │
                          v
                    SupportAgent
                   /      |       \
                  /       |        \
                 v        v         v
          Order Lookup  Policy    Greeting
               │       Retriever
               │          │
               └────┬─────┘
                    v
               Evidence Check
                    │
          ┌─────────┴─────────┐
          │                   │
     grounded answer      refund proposal
                              │
                              v
                        Durable Run
                              │
                              v
                       Human Approval
                              │
                    ┌─────────┴─────────┐
                    │                   │
                 reject          validated approve/edit
                                        │
                                        v
                              Idempotent Refund Effect
```

你会发现这张图没有非常炫。

这很好。

一张优秀架构图的目标不是让别人觉得“这里用了好多技术”。

它应该让别人看清：

> **谁负责判断，谁拥有数据，谁拥有权限，什么时候会产生副作用，以及系统失败后怎样恢复。**

如果这五个问题能回答清楚，Agent 就开始从 Demo 变成工程系统了。

---

## 28. 毕业以后继续学什么？

Agent 技术还会继续变化。

模型会变，框架会变，协议会变，产品名字当然也会变。

但这门课真正希望留下的是一套不那么容易过期的判断方式：

遇到模型输出，先问契约。

遇到自主循环，先问停止条件。

遇到 Tool，先问执行权。

遇到 RAG，先问 Evidence。

遇到 Memory，先问 Retention Policy。

遇到 Context，先问这一轮真的需要什么。

遇到 Skill，先问 Procedure 和 Authority 是否分开。

遇到 Retry，先问 Side Effect 是否幂等。

遇到 Multi-Agent，先问为什么一个 Agent 不够。

遇到 Sandbox，先问真正隔离了什么。

遇到 Production，先问身份、作用域和 Durable State。

遇到 Long-Horizon，先问 Worker 消失以后任务还能不能继续。

最后，遇到任何漂亮的 Agent Demo，都可以多问一句：

> **如果把模型名字和框架 Logo 都遮住，这套系统的责任边界还说得清楚吗？**

说得清楚，说明你真正理解了系统。

说不清楚，就回到最小机制，一层一层重新搭。

至此，Tiny-Agent 的课程主线结束。
