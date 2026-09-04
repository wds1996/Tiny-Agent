# 04 — LangGraph Implementation：相同 Domain，不同 Orchestration

framework 版本应该回答一个非常具体的问题：

> 当 application semantics 已经正确之后，LangGraph 究竟给我们带来了什么？

它不应该悄悄重新定义 evidence、memory、permission 或 evaluation。

## Shared Domain Layer

两个版本都复用：

```text
ResearchRequest / ResearchReport
LocalResearchCorpus
CrossrefScholarlySearch
ResearchReviewTeam
ResearchMemoryStore
MarkdownReportExporter
evaluate_research_report
```

Graph 版本增加的是 orchestration primitives：

```text
StateGraph
TypedDict state
nodes
conditional edges
checkpointer
interrupt
Command(resume=...)
```

## Graph Structure

```text
START
  |
load_memory
  |
plan
  |
retrieve
  |
  +-----------------------+
  |                       |
insufficient             draft
  |                       |
  |                     review
  |                       |
  +----------+------------+
             |
          remember
             |
       export requested?
        /            \
      no             yes
      |                |
  finalize      approval_export
                      |
                  finalize
                      |
                     END
```

当 workflow 出现 resumable human boundary，以及多个真正非平凡的 branch / transition 时，graph 把这些结构显式化的价值才开始明显。

## State 是可序列化的 Application Data

Graph state 会保存：

```python
class OpenScholarGraphState(TypedDict, total=False):
    run_id: str
    question: str
    user_id: str
    thread_id: str
    plan: dict[str, Any]
    evidence: list[dict[str, Any]]
    answer: str
    warnings: list[str]
    metrics: dict[str, int]
    status: str
```

注意哪些东西**没有**进入 graph state：

- database connections；
- model clients；
- file handles；
- authorization objects；
- Python coroutine objects。

这些属于 application instance 管理的 runtime dependency，而不是 durable state。

## 为什么 Evidence 要转成 Dictionary

`Evidence` 本身是 domain dataclass。

checkpointed graph state 应尽量保持简单、portable，所以 graph node 会把 evidence 转成普通 dictionary，需要 domain behavior 时再重建对象。

```text
Domain object
  -> graph-safe representation
  -> checkpoint
  -> domain object
```

这形成一个清晰 serialization boundary。

## Checkpointer 与 Long-Term Memory 仍然不同

即使未来两者都保存在 database，它们的语义仍然不同：

```text
Checkpointer
  -> 这个 graph execution 暂停在哪里？
  -> thread-scoped

ResearchMemoryStore
  -> 用户明确允许跨 run 保留的 preference 是什么？
  -> user-scoped
```

framework checkpoint 绝不能因为“已经持久化了”就自动升级成用户永久 semantic memory。

## HITL Node

export node 故意采用这样的顺序：

```python
approval = ApprovalRequest(...)

decision_payload = interrupt(
    approval.to_interrupt_payload()
)

decision = ApprovalDecision.from_payload(
    decision_payload
)

# side effect only after resume
exporter.export(...)
```

为什么 `interrupt()` 必须在 file write 前？

因为包含 `interrupt()` 的 LangGraph node 在 resume 时可能从 node 开头重新执行。

如果 side effect 已经发生在 interrupt 前：

```python
exporter.export(report, path)
decision = interrupt(...)
```

那么 resume 时可能再次执行 export。

这已经不是：

> 请批准我要做的事情。

而更像：

> 请批准我刚才已经做了、而且恢复时可能又做一遍的事情。

## Resume

调用者使用相同 `thread_id`：

```python
report = await agent.resume(
    thread_id="research-42",
    decision=ApprovalDecision(
        outcome="approve"
    ),
)
```

内部通过：

```python
Command(resume=payload)
```

从 checkpointed interrupt boundary 继续。

## 为什么 Graph 不拥有 Permission

一个 node 叫 `approval_export`，并不会让它变成 authorization mechanism。

真实 exporter 仍然检查：

- 必须使用 relative path；
- suffix 必须是 `.md`；
- resolve 后 target 必须留在 configured export root 内；
- 使用 exclusive creation，避免静默 overwrite。

因此：

```text
Framework routing
    = 什么时候执行这段代码？

Application policy
    = 这个 side effect 到底是否合法？
```

两者职责不同。

## Base vs Graph Version

Graph 版本并不会自动更高级。

### 适合 Base Version

- branching 简单；
- process-local execution 足够；
- 希望依赖尽量少；
- ordinary code 仍然清楚可读。

### Graph 开始有明显价值

- human pause 必须跨 process restart 存活；
- state transition 需要显式 inspection；
- workflow 经常 branch / rejoin；
- checkpoint / resume 是核心需求；
- graph streaming / debugging 有真实价值。

一个非常实用的判断标准：

> **如果脱离 LangGraph 之后你根本解释不清 state machine，那么加入 LangGraph 不会让这个 state machine 自动变正确；它最多只是让你的困惑变得可以序列化。**