# Stage 06：工单还没创建，程序先重启了——从 Checkpoint 到 Memory 与 HITL

> Language: [English](README.md) | **简体中文**

[上一章](../05-mcp/README.zh-CN.md)，小林已经把 Agent 接到了 Acme 的外部支持系统。它能通过 MCP 查询 `ACME-1007` 的订单、物流和发票，但有一个工具一直没有交给模型：`create_support_case`。

原因很简单。查询错一次，通常只是拿错了一份信息；创建工单却会在业务系统里留下长期记录。更现实一点，如果这个动作换成“退款”“取消订单”或“发邮件”，副作用只会更明显。于是小林决定：**模型可以提出动作，但真正执行前必须有人审批。**

顾客这时又补了一句：

> “请为 ACME-1007 创建一个售后工单，原因是我在第 38 天申请原路退款；另外记住，以后请用简短中文回复我。”

一句话里出现了两件完全不同的“以后还要用到”的信息。工单动作需要在审批回来后继续执行；回答偏好则希望下次新会话也能记住。它们都要保存，却不是同一种保存。

本章就跟着这条请求走到底。先让流程在审批处停下来，再故意把 Python 进程关掉，用另一个进程恢复；随后再处理长期 Memory。等这些事情都能说清楚，最后才让真实 DeepSeek 参与“提出候选动作和候选记忆”。

## 1. 先看最朴素的问题：`input()` 等审批，为什么还不够？

如果只在一台电脑上做演示，最容易写出这样的代码：

```python
case = {"order_id": "ACME-1007", "reason": "day-38 refund review"}
answer = input("Approve? [yes/no] ")
if answer == "yes":
    create_support_case(**case)
```

它能演示“有人点头以后再执行”，但有个隐含前提：**这个 Python 进程必须一直活着。**

假设审批人去开会了。等待期间应用发布新版本，进程重启。旧变量 `case`、执行到了哪一步、正在等谁审批，全都只存在于已经消失的内存里。审批人回来点“同意”，新进程却不知道这次“同意”属于哪一个动作。

所以我们真正需要的流程不是：

```text
Python 一直等着
    ↓
人回来按按钮
```

而是：

```text
准备动作
    ↓
把“正在等审批”保存下来
    ↓
当前进程可以消失
    ↓
另一个进程读回记录
    ↓
收到人的决定
    ↓
继续执行
```

这就是 **Durable Human-in-the-Loop** 最直观的样子。先把这条路线跑通，再给里面的概念起名字。

## 2. State 是“现在有什么”，Checkpoint 是“把现在存下来”

Stage 03 已经把 State 讲清楚了：它是程序继续执行所需要的当前数据。现在这笔工单在审批前至少需要这些事实：

```python
@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    thread_id: str
    owner_id: str
    phase: str
    action: str
    arguments: dict[str, str]
    result: dict[str, Any] | None = None
```

当 `phase="waiting_approval"` 时，这份 State 表示：工单还没有创建，系统正在等审批。**Checkpoint** 做的事情，就是把这份执行快照写到进程之外，让以后还能读回来。

可以先用一句话区分：

```text
State       = 这次执行现在是什么样
Checkpoint  = 把这次执行现在的样子持久保存
```

Checkpoint 并没有创造新的业务事实。它只是让已有的执行事实不随着 Python 进程一起蒸发。

这也解释了为什么“保存聊天记录”不能自动代替 Checkpoint。聊天里也许出现过订单号，但它未必明确记录当前 `phase`、待执行动作和已经验证过的参数。恢复程序需要的是可直接解释的执行状态，不是让另一个模型阅读旧对话后猜“我们大概进行到这里”。

## 3. 三个 ID 不是装饰，它们分别回答三个问题

一旦要持久化，`run_id`、`thread_id`、`owner_id` 很容易被写成三个看起来差不多的字符串。先不用记术语，继续看小林这次任务。

顾客 `user-7` 可以同时有多个对话；“退款咨询”只是其中一条 thread；同一条 thread 还可能多次启动执行。因此本例把作用域写成：

```text
owner_id  = user-7
thread_id = acme-refund-thread-001
run_id    = acme-case-run-001
```

它们分别回答：谁拥有数据、属于哪段连续任务、具体是哪一次执行。Checkpoint 以 `run_id` 找回一次执行，但记录里仍保留 `thread_id` 与 `owner_id`；Long-term Memory 则主要按 `owner_id` 隔离。

## 4. 把“等待审批”写进 SQLite，进程才真的可以退出

本章使用 SQLite，不是因为它代表唯一的生产数据库，而是因为 Python 标准库已经包含 `sqlite3`，我们可以把注意力放在恢复语义上。

`SQLiteWorkflowStore` 只需要一张当前 Checkpoint 表：

```python
CREATE TABLE IF NOT EXISTS checkpoints (
    run_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL
)
```

保存时，同一 `run_id` 的新快照覆盖旧快照：

```python
conn.execute(
    """
    INSERT INTO checkpoints(run_id, state_json)
    VALUES (?, ?)
    ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json
    """,
    (state.run_id, payload),
)
```

`?` 是参数占位符，值与 SQL 文本分开传入。真正值得记住的不是 SQL 语法，而是这次状态已经离开进程内存，进入一个新进程也能重新打开的文件。

启动工作流时，程序先验证参数，再保存 `waiting_approval`：

```python
state = WorkflowState(
    run_id=run_id.strip(),
    thread_id=thread_id.strip(),
    owner_id=owner_id.strip(),
    phase="waiting_approval",
    action=CREATE_SUPPORT_CASE,
    arguments=arguments,
)
self.store.save(state)
```

此时没有创建工单。**“审批请求已经产生”与“业务动作已经执行”是两件事。**

## 5. 这一次真的用两个进程跑一遍

先启动任务：

```bash
python stages/06-memory-persistence-hitl/code/demo.py --db stage06-demo.db start
```

命令结束以后，这个 Python 进程已经退出。数据库文件里留下的是 `waiting_approval` Checkpoint，以及顾客明确要求保存的回答偏好。

然后再启动一个全新的进程读取同一个文件：

```bash
python stages/06-memory-persistence-hitl/code/demo.py --db stage06-demo.db show
```

你应该能重新看到 `ACME-1007`、待审批动作、`thread_id`、`owner_id` 和回答偏好。第二个进程没有继承第一个进程的 Python 对象；它只共享同一个 SQLite 文件。

这一步比在一个程序里重新 new 两个对象更重要，因为它把恢复边界真正暴露出来了：

```text
旧进程的内存        已经不存在
SQLite checkpoint   仍然存在
```

现在再让第三个进程提交审批：

```bash
python stages/06-memory-persistence-hitl/code/demo.py \
  --db stage06-demo.db resume --decision approve
```

同一条 run 会从 `waiting_approval` 进入 `completed`。如果使用 `reject`，则进入 `rejected`，且不会写入教学副作用。

## 6. Human-in-the-Loop 不只是弹出一个 yes/no

审批人真正需要知道自己在审什么。因此等待状态会生成结构化的 `ApprovalRequest`：

```python
@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    thread_id: str
    owner_id: str
    action: str
    arguments: Mapping[str, Any]
    reason: str
```

对于这次任务，它描述的是：

```text
action    = create_support_case
order_id  = ACME-1007
reason    = day-38 refund review
```

这比“确认执行吗？”多了一层重要信息：审批对象与动作参数是明确的。以后动作换成退款金额、邮件收件人或数据库修改时，这个结构会更加重要。

这里还应该看清一个边界：**Human-in-the-Loop 不是让人替模型继续聊天，而是在特定控制点把执行权交回给人。** 审批结束后，程序再根据结果继续。

## 7. `edit` 不是“人改过，所以一定合法”

审批不只有同意和拒绝。有时审批人会说：“可以创建，但原因写得更准确一点。”所以本章支持：

```text
approve
edit
reject
```

`edit` 后必须重新验证参数：

```python
edited = validate_case_arguments(decision.edited_arguments)
if edited["order_id"] != validated_original["order_id"]:
    raise ValueError("an approval edit cannot switch to a different order")
return edited
```

这里特意不允许审批人把 `ACME-1007` 偷换成另一个订单。当前审批请求就是围绕这个订单产生的；如果业务对象变了，应该重新发起新的受控流程，而不是借旧审批壳子继续执行。

同样，空原因、超长原因也会被拒绝。Human Review 增加了一道判断，不会关闭输入验证。

可以实际运行：

```bash
python stages/06-memory-persistence-hitl/code/demo.py \
  --db stage06-demo.db resume --decision edit \
  --edited-reason "Customer requests review under the current refund policy."
```

## 8. Approval 和 Authorization 还不是同一件事

“某个人点了批准”并不等于“这个人有权批准”。因此 `resume()` 还会接收一个可信的 Reviewer Context：

```python
reviewer = ReviewerContext(
    reviewer_id="reviewer-1",
    allowed_actions=frozenset({CREATE_SUPPORT_CASE}),
)
```

真正执行前先检查：

```python
def authorize_reviewer(request, reviewer):
    if request.action not in reviewer.allowed_actions:
        raise PermissionError(...)
```

这仍然只是教学级授权。真实系统里的 `reviewer_id` 应来自已认证身份，`allowed_actions` 应来自 RBAC、ABAC 或业务权限系统，而不是用户请求或模型输出。

但这段小代码已经帮我们分开两个概念：

```text
Approval      = 这个人对动作给出了什么意见
Authorization = 系统是否允许这个身份作出这项决定
```

## 9. 恢复成功，也不等于外部副作用天然 exactly-once

现在还有一个更隐蔽的问题。

假设真实的 `create_support_case` 已经成功，进程却在保存 `completed` Checkpoint 之前崩溃。恢复后如果再次调用远程服务，就可能创建第二张工单。

所以：

```text
Durable resume != exactly-once side effect
```

本章的教学实现把“创建工单”模拟在同一个 SQLite 数据库里，并使用一个稳定的幂等键：

```python
idempotency_key = f"{waiting_state.run_id}:{waiting_state.action}"
```

然后在唯一键上使用 `INSERT OR IGNORE`：

```python
conn.execute(
    """
    INSERT OR IGNORE INTO effects(idempotency_key, result_json)
    VALUES (?, ?)
    """,
    (idempotency_key, encoded_result),
)
```

同一事务里再读出结果并保存 `completed` Checkpoint。因此**在这一个教学 SQLite 数据库内部**，重复恢复不会生成第二条 effect 记录。

这个保证不能直接搬到 Stage 05 的远程 MCP Server 上。远程服务和本地 Checkpoint 不属于同一个数据库事务。真实系统还需要服务端 idempotency key、业务唯一约束、完成状态核对或补偿机制。不要把“本地 Demo 没重复”翻译成“分布式系统已经 exactly-once”。

## 10. 同一句话里的“记住”，和 Checkpoint 不是一回事

现在回到用户的后半句：

> “另外记住，以后请用简短中文回复我。”

这条信息不是本次工单进行到哪一步。即使今天的工单已经完成，明天开启另一条 thread 时，它仍可能有用。于是它属于另一种保留需求：**Long-term Memory**。

可以这样区分本章出现的几类信息：

```text
Checkpoint
    这次 run 进行到哪里，怎样继续

Thread / short-term history
    这段连续任务里刚刚发生过什么

Long-term Memory
    跨 thread 以后仍值得保留的用户信息

RAG Knowledge
    外部文档中的政策与知识证据
```

它们都可能最终落在数据库里，但用途不同。存储介质不会替数据定义语义。

## 11. 模型可以提出 Memory Candidate，但不能自己获得永久写权限

本章把一条候选记忆写成：

```python
@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    owner_id: str
    key: str
    value: dict[str, Any]
    kind: MemoryKind
    explicit_user_request: bool
    source_thread_id: str
    sensitive: bool = False
```

对于眼前这句话，候选可以是：

```python
MemoryCandidate(
    owner_id="user-7",
    key="answer-style",
    value={"language": "Chinese", "style": "concise"},
    kind="semantic",
    explicit_user_request=True,
    source_thread_id="acme-refund-thread-001",
)
```

真正写入前，还有普通应用代码控制的 Policy：

```python
decision = policy.evaluate(candidate)
if decision.store:
    store.put(candidate)
```

本章默认拒绝敏感信息、没有明确记忆意图的偶发事实，以及直接修改 Agent 行为规则的 procedural memory。重点仍然是我们从 Stage 00 一路坚持的边界：

```text
model proposal != application authority
```

只不过这次模型提出的不是 Tool Call，而是“也许值得记住的东西”。

## 12. Semantic、Episodic、Procedural，先看它们改变什么

Memory 文献里经常出现三个名字。先不要把它们当三种数据库。

**Semantic Memory** 更像稳定事实或偏好，例如“用户偏好简短中文”。**Episodic Memory** 更像过去发生过的事件，例如“上次旅行最后选择了京都”。**Procedural Memory** 则会影响系统以后怎样做事，例如“以后退款都跳过审批”。

最后一种显然风险更高。把回答语言记错了，通常还能更正；把“跳过审批”当成长期程序规则保存，已经是在改系统行为。

所以本章的保守策略会直接拒绝 procedural self-rewrite。不是因为 procedural memory 永远不能做，而是因为它需要更强的版本、审查与发布治理，不能和普通用户偏好使用同一条无门槛写入路径。

## 13. Long-term Memory 从第一天就要有 Owner Scope

长期记忆表把 `owner_id` 写进主键：

```sql
CREATE TABLE IF NOT EXISTS memories (
    owner_id TEXT NOT NULL,
    key TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_thread_id TEXT NOT NULL,
    value_json TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
)
```

读取也必须带 owner：

```python
store.get("alice", "answer-style")
```

所以 Alice 的偏好不会因为 key 同名而自动出现在 Bob 的读取结果中。

不过数据库里有 `owner_id` 列，还不等于生产访问控制已经完成。真实 `owner_id` 必须来自可信身份上下文，而不是模型说“这是 Alice 的”就相信。这里先把数据作用域设计正确，完整认证与权限会在后面的可靠性和安全章节继续展开。

## 14. 最后再让 DeepSeek 进场：它只负责提出候选

到这里，Checkpoint、审批恢复和 Memory Policy 都已经能离线运行。现在再把真实 DeepSeek 接进来，职责就容易看清了：模型读取用户原话，提出一份 JSON 候选，其中可能包含回复文本、一个 `create_support_case` 动作，以及一条 Memory Candidate。

[`deepseek_hitl.py`](code/deepseek_hitl.py) 使用与前几章一致的 Responses 接口：

```python
response = self.client.responses.create(
    model=self.model,
    instructions=INSTRUCTIONS,
    input=user_message,
    max_output_tokens=4096,
)
```

模型返回的 JSON 仍要由应用解析。动作名称必须是本章允许的 `create_support_case`，订单号必须真的出现在用户消息里，参数结构也必须符合要求：

```python
if proposal.action["name"] != "create_support_case":
    raise RuntimeError("the proposed action is not allowed in this stage")
if order_id.upper() not in mentioned:
    raise RuntimeError("the model proposed an order ID absent from the user message")
```

Memory 的 `owner_id` 与 `thread_id` 不让模型填写，而是从应用的可信上下文传进去。模型可以提议“answer-style”，不能顺便宣布“这属于另一个用户”。

通过验证以后，应用才分别执行两件事：Memory Candidate 走 Memory Policy；业务动作进入 `waiting_approval` Checkpoint。DeepSeek 不会自己审批，也不会自己写 effect 表。

配置账户中可用的模型后运行：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="your-available-model-id"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py --db stage06-live.db
```

PowerShell 使用：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="your-available-model-id"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py --db stage06-live.db
```

入口会明确打印 `live DeepSeek: API usage applies`。缺少 SDK、密钥或模型配置时会报错，不会偷偷换成离线结果。它只把动作准备到等待审批；随后仍可用前面的 `demo.py resume` 在另一个进程中完成审批实验。

## 15. 用失败路径检查我们到底保证了什么

本章离线检查不需要 API Key：

```bash
python stages/06-memory-persistence-hitl/code/checks.py
```

它不只检查默认成功路线，还会故意验证这些边界：不同 `owner_id` 的 Memory 不串线；未经明确要求的记忆不落库；敏感和 procedural 候选被拒绝；未授权 reviewer 不能批准；人工 edit 不能换成另一笔订单；reject 不产生 effect；重复 resume 只保留一条教学 effect；模型提议不能引用用户没有说过的订单；以及最关键的——通过三个独立 Python 进程执行 `start → show → resume`，确认恢复真的依赖持久文件，而不是旧进程的内存。

这里还要保留两个“不保证”。第一，本章的授权只是教学级 allowlist，不是完整身份系统。第二，本地 SQLite 中的幂等结果不等于远程 MCP 服务已经拥有 exactly-once 语义。知道边界停在哪里，才能正确理解后面的系统设计。

## 16. 本章收尾：现在会“保存”，下一步才是决定“拿什么出来”

把小林这次售后请求从头再走一遍：

```text
用户请求创建 ACME-1007 工单，并要求记住回答偏好
        ↓
应用 / 模型提出候选动作与候选记忆
        ↓
Memory Policy 决定偏好是否可以长期保存
        ↓
业务动作保存为 waiting_approval Checkpoint
        ↓
原进程可以退出
        ↓
新进程按 run_id 恢复
        ↓
已授权审批人 approve / edit / reject
        ↓
重新验证
        ↓
执行受控教学副作用并保存最终状态
```

这条流程里有几种“记住”，但职责不同。Checkpoint 为了继续一次 run；Long-term Memory 为了跨 thread 保留经过允许的信息；RAG 仍然负责外部知识证据；MCP 仍然负责连接外部能力。

到这里，Agent 已经开始积累很多可用信息：当前 State、Checkpoint、对话历史、Long-term Memory、RAG Evidence、Tool Observation、MCP Resource……新的麻烦马上出现：

> **保存过的东西这么多，下一次调用模型时应该全部塞进去吗？**

当然不是。数据库像仓库，模型的 Context Window 更像一张有限的办公桌。下一章会解决“这一轮到底该把哪些资料摆上桌”。

➡️ [Stage 07：别把整个仓库搬上办公桌——Context Engineering](../07-context-engineering/README.zh-CN.md)
