# Stage 06：Agent 也得学会“下班前存档”——从 State 到 Memory、Checkpoint 与 Human-in-the-Loop (HITL)

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

把 `checkpoint` 表改名叫 `memory_super_pro_max`，它也不会突然变成加强版的memory。

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

本章教学实现有意只保存 `run_id`，这样读者可以把注意力放在 Checkpoint 与恢复机制上。在真实产品中，Checkpoint 记录还应关联它所属的 `thread_id` 和已认证的 `user_id`；不要把这个最小表结构当成完整的多用户数据模型。

---

## 3. Checkpoint 保存的是“继续干活所需的信息”

### 为什么这里使用 SQLite

SQLite 是嵌入式关系型数据库：数据保存在本地的一个文件中，例如 `agent.db`；它不像 MySQL 或 Postgres 那样需要先运行一个独立的数据库服务。Python 标准库自带 [`sqlite3`](https://docs.python.org/3/library/sqlite3.html)，所以本章无需安装额外依赖。

这一节只需要先认识四个词：

| 术语 | 在本章中的含义 |
|---|---|
| 数据库文件 | 可持久化保存的数据文件，例如 `agent.db`；新的 Python 进程可以重新打开它。 |
| 表（table） | 一类有名字的记录集合，例如 `checkpoints`。 |
| 行（row） | 一条保存的记录；这里由 `run_id` 唯一标识。 |
| 事务（transaction） | `with conn:` 中的写入成功时提交；若异常逃出则回滚。 |

SQLite 是本章便于理解的本地起点，并不是唯一的生产选择。需要继续学习时，可阅读 [SQLite 官方文档](https://www.sqlite.org/docs.html)、[Python `sqlite3` 官方文档](https://docs.python.org/3/library/sqlite3.html)，或中文的[菜鸟教程 SQLite 教程](https://www.runoob.com/sqlite/sqlite-tutorial.html)。

先定义“恢复时必须读回什么”的状态：

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkflowState:
    run_id: str
    phase: str
    action: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
```

Store 打开数据库文件，并在第一次使用时建表。`run_id TEXT PRIMARY KEY` 表示同一次 run 最多有一条当前 Checkpoint：

```python
from contextlib import contextmanager
from pathlib import Path
import sqlite3


class SQLiteCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_db()

    @contextmanager
    def _session(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._session() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                )
                """
            )
```

接下来在同一个 session 中完整地保存和读回状态：

```python
from dataclasses import asdict
import json


def save(self, state: WorkflowState) -> None:
    payload = json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)
    with self._session() as conn:
        conn.execute(
            """
            INSERT INTO checkpoints(run_id, state_json)
            VALUES (?, ?)
            ON CONFLICT(run_id) DO UPDATE SET state_json=excluded.state_json
            """,
            (state.run_id, payload),
        )


def load(self, run_id: str) -> WorkflowState:
    with self._session() as conn:
        row = conn.execute(
            "SELECT state_json FROM checkpoints WHERE run_id=?",
            (run_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"unknown run_id: {run_id}")
    return WorkflowState(**json.loads(row[0]))
```

`?` 是 SQL 参数占位符：值与 SQL 文本分开传入，而不是用字符串拼接 SQL。`ON CONFLICT ... DO UPDATE` 表示同一个 `run_id` 再次保存时，覆盖旧快照。

最重要的变化不在 SQLite 语法，而在架构：新的 Runtime 只要拿到同一个持久化文件和 `run_id`，就能读回 `phase`、`action` 与 `arguments`。于是“恢复”第一次不再依赖原进程的寿命；这就是 Durable Execution 最基础的一层含义。

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

完整的教学方法会先返回已经保存的结果；没有记录时再写入新的结果：

```python
def record_effect_once(
    self,
    idempotency_key: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with self._session() as conn:
        existing = conn.execute(
            "SELECT result_json FROM effects WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            return json.loads(existing[0])
        conn.execute(
            "INSERT INTO effects(idempotency_key, result_json) VALUES (?, ?)",
            (idempotency_key, encoded),
        )
    return result
```

这只能证明**教学数据库内部**的幂等思路。

这个示例保存的是“模拟退款结果”，并没有真的调用支付服务；它展示的是幂等边界的形状，不是分布式事务。两个独立 Worker 也可能恰好同时通过 `SELECT`，然后在 `INSERT` 处竞争。因此生产系统还需要原子地抢占执行权、处理唯一键竞争，或更理想地使用外部 API 自己支持的 idempotency key、业务唯一约束或补偿机制。

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

先定义本章允许讨论的 Memory 类别，再定义模型提出的候选：

```python
from dataclasses import dataclass
from typing import Any, Literal


MemoryKind = Literal["semantic", "episodic", "procedural"]


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

它的判断是普通的应用程序代码，不是模型自己的判断：

```python
@dataclass(frozen=True, slots=True)
class MemoryDecision:
    store: bool
    reason: str


class ConservativeMemoryWritePolicy:
    def evaluate(self, candidate: MemoryCandidate) -> MemoryDecision:
        if candidate.sensitive:
            return MemoryDecision(False, "sensitive data is not stored")
        if candidate.kind == "procedural":
            return MemoryDecision(False, "procedural memory needs stronger governance")
        if not candidate.explicit_user_request:
            return MemoryDecision(False, "an incidental fact is not durable memory")
        if not candidate.owner_id.strip() or not candidate.key.strip():
            return MemoryDecision(False, "owner_id and key are required")
        return MemoryDecision(True, "explicit non-sensitive memory is allowed")
```

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

本章的表结构把 Owner Scope 直接写进了主键：

```python
CREATE TABLE IF NOT EXISTS memories (
    owner_id TEXT NOT NULL,
    key TEXT NOT NULL,
    kind TEXT NOT NULL,
    value_json TEXT NOT NULL,
    PRIMARY KEY (owner_id, key)
)
```

读取时也必须带 `owner_id`：

```python
store.get("alice", "answer-style")
```

真实服务中的 `owner_id` 必须来自已认证的请求上下文，不能直接相信模型建议或不可信客户端字段。表中有一个 owner 列，并不等于访问控制已经成立。

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

并产生结构化审批请求。类型本身说明：审批人看到的是待执行动作、参数和原因，而不是一个没有上下文的布尔值：

```python
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    run_id: str
    action: str
    arguments: Mapping[str, Any]
    reason: str


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

本章代码中的 `resolve_refund_arguments` 负责这一步。下面是能看清重新验证位置的完整核心逻辑：

```python
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Literal


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    outcome: Literal["approve", "edit", "reject"]
    edited_arguments: Mapping[str, Any] | None = None


def resolve_refund_arguments(
    original: Mapping[str, Any],
    decision: ApprovalDecision,
) -> dict[str, Any] | None:
    if decision.outcome == "reject":
        return None
    if decision.outcome == "approve":
        candidate = dict(original)
    elif decision.outcome == "edit" and decision.edited_arguments is not None:
        candidate = dict(decision.edited_arguments)
    else:
        raise ValueError("edit requires edited_arguments")

    order_id = candidate.get("order_id")
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id must be a non-empty string")
    try:
        amount = Decimal(str(candidate.get("amount")))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be numeric") from exc
    if amount <= 0:
        raise ValueError("amount must be positive")
    return {"order_id": order_id.strip(), "amount": str(amount)}
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
from pathlib import Path

from approval import ApprovalDecision
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore


db_path = Path("agent.db")
runtime_a = RefundWorkflow(SQLiteCheckpointStore(db_path))
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
state = SQLiteCheckpointStore(db_path).load("run-001")
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

`runtime_b` 与 `runtime_a` 不共享任何 Python 对象；真正的恢复边界是共同的数据库文件和 `run_id`。仓库中的 `demo.py` 为了反复运行后不在项目里留下 `.db` 文件，使用了临时目录；因此它证明的是“同一进程内重建对象也能从同一文件恢复”。如果要亲自测试真实进程重启，请使用像 `agent.db` 这样明确的持久路径，并且不要把数据库文件提交到 Git。

---

### 12.1 可选扩展：让 DeepSeek 提出提案，而不是做决定

离线示例已经足够学习持久化与 HITL。这里接入真实模型的目的更窄：观察模型如何把用户消息变成**退款提案**和 **Memory Candidate**。模型仍然没有写入 Memory 或执行退款的权限。

[`code/deepseek_hitl.py`](code/deepseek_hitl.py) 要求 DeepSeek 返回一个含有 `reply`、`refund`、`memory` 的 JSON 对象。在发生任何写入之前，应用会验证 JSON 结构，确认模型提出的订单号确实来自用户消息，从可信的应用状态写入 `owner_id`，执行 Memory Policy，并保存等待审批的 Checkpoint。退款结果仍必须等人工输入审批后才会记录。

[`code/langgraph_deepseek_hitl.py`](code/langgraph_deepseek_hitl.py) 把相同的准备过程表达为一张图：

```text
DeepSeek proposal
    -> 验证并应用 Memory Policy
    -> 验证退款提案并保存 waiting_approval Checkpoint
    -> 在图外等待人工审批
```

LangGraph 版本让这些准备节点和状态更新可观察；SQLite 仍然是持久化 Checkpoint Store，`RefundWorkflow.resume()` 仍负责处理审批后的结果。只运行一张 Graph 并不会自动让人工审批持久化。

先安装这两个可选真实模型示例的依赖，再沿用前面章节的环境变量：

```bash
python -m pip install -r stages/06-memory-persistence-hitl/code/requirements.txt
```

Windows CMD：

```bash
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=deepseek-v4-flash"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py
python stages/06-memory-persistence-hitl/code/langgraph_deepseek_hitl.py
```

PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/06-memory-persistence-hitl/code/deepseek_hitl.py
python stages/06-memory-persistence-hitl/code/langgraph_deepseek_hitl.py
```

两个程序使用相同的示例请求。可以修改任一文件中的 `user_message`，对照退款请求、只请求记忆、以及没有任何提案的请求。所有持久化写入与副作用仍必须由应用程序控制。

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

离线版完整代码在 `code/` 中，只使用 Python 标准库，因此不需要安装依赖。

先运行：

```bash
python stages/06-memory-persistence-hitl/code/demo.py
```

新的 Runtime 到达审批边界后，按提示输入其中一种结果：

```text
approve  # 执行教学退款结果
edit     # 输入替换后的订单号和金额；两者都会重新验证
reject   # 不记录退款结果，直接结束本次审批
```

例如选择 `edit`，再把金额输入为 `-1`，可以看到程序拒绝这次人工编辑。Checkpoint 会保持在 `waiting_approval`，随后程序会再次询问，因此你可以继续输入一个有效结果。

边界检查：

```bash
python stages/06-memory-persistence-hitl/code/checks.py
```

它覆盖了几个本章真正重要的不变量：Checkpoint 能跨对象重建恢复；Reject 不产生副作用；Edit 后重新验证；教学存储中的 effect key 保持幂等；Memory 默认不保存偶发信息；敏感候选被拒绝；不同 owner 的长期记忆互不串线。

`demo.py` 使用的数据库在程序退出后会被删除。它的目的，是在清理发生前演示第二个 Runtime 能读取同一个 SQLite 文件；这不是生产环境的保留策略。

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

这就是 [Stage 07：Context Engineering](../07-context-engineering/README.zh-CN.md)。
