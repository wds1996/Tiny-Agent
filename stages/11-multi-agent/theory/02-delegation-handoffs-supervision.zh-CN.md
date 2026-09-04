# 02 — Delegation、Handoff 与 Supervisor

> Language: [English](02-delegation-handoffs-supervision.md) | 简体中文

“让另一个 Agent 来做”这句话，实际上隐藏了几种完全不同的 control-flow semantics。

Stage 11 要把它们拆开。

---

## 1. Delegation：Manager 保持 Control

```text
user -> manager -> specialist -> manager -> user
```

Specialist 像 high-level Tool，manager 继续拥有 user conversation、final synthesis、是否还需要别的 specialist、final-answer responsibility。

适用于 specialist 只提供 expertise，不接管 conversation。

---

## 2. Handoff：Control Ownership 改变

```text
user -> triage --handoff--> refund specialist -> user
```

成功 transfer 后 target 成为 active Agent。

Tiny-Agent：

```python
await team.delegate(...)
# active_agent unchanged

await team.handoff(...)
# target 成功后 active_agent 才变化
```

如果 target 调用失败却先改 ownership，runtime 就会声称“控制已经转移给一个根本没有成功接住任务的 Agent”。

---

## 3. Supervisor / Worker

```text
             -> researcher
            /
supervisor ----> analyst
            \
             -> reviewer
                    |
                    v
              supervisor synthesis
```

Supervisor 决定 worker、subtask、结果是否充分、是否继续调用、怎样 aggregation。可以 LLM-driven，也可以 code-driven。

---

## 4. LLM Orchestration vs Code Orchestration

OpenAI Agents SDK 同样区分：

```text
LLM orchestration -> model chooses handoff/agent-tool
code orchestration -> application chooses sequence/parallelism/routing
```

Stage 02 原则仍成立：control rule 已知就用 deterministic code。

如果每次都固定：

```text
research -> legal review -> final formatting
```

就直接写 workflow。没有必要每次付钱让 LLM 重新发现你架构图里已经画好的箭头。

---

## 5. OpenAI Agents SDK：Agent as Tool

```python
specialist_tool = specialist.as_tool(
    tool_name="refund_expert",
    tool_description="Handle a bounded refund subtask",
)
manager = Agent(..., tools=[specialist_tool])
```

Nested specialist 返回原 manager；manager 保持 conversation ownership。

---

## 6. OpenAI Agents SDK：Handoff

```python
triage = Agent(..., handoffs=[refund_agent])
```

Model 选择 transfer Tool 后，execution 转到 target Agent。

这不是换了一个 method name，而是 responsibility graph 变了。

---

## 7. Context Behavior 也不同

Agent-as-Tool 往往接收 manager 生成的 bounded subtask；handoff 为了 conversation continuity，常转移更多 history。

但：

```text
conversation continuity != permission to copy every internal state field
```

因此 current OpenAI Agents SDK 提供 handoff input filtering。

---

## 8. Delegation Task Contract

坏：

```text
"Do the important part."
```

好：

```text
Goal: Extract three evidence-backed risks.
Constraints:
- Use only supplied evidence.
- Do not make external mutations.
- Return exactly three bullets.
Success:
Every bullet cites an evidence ID.
```

Sub-Agent 不是读心术专家。Supervisor 若重述错 user task，worker 很可能认真完成了错误问题。

---

## 9. Constraint Loss

```text
original request
 -> supervisor summary
 -> critical constraint omitted
 -> worker solves wrong task
```

输出仍可能十分流畅。所以 critical constraint 应显式保留；高价值 task 可以像 Stage 09 validation Tool args 一样 validate delegation contract。

---

## 10. Result Acceptance 也是 Decision

```text
worker returned text != task successfully completed
```

Supervisor 还可能检查 schema、evidence coverage、constraint、policy、quality threshold。Stage 10 evaluator 可直接复用。

---

## 11. Failed Handoff

Invariant：

```text
handoff attempt -> target fails -> active owner stays source
```

类似 transaction：transfer 真正成功前不要先更新 control pointer。

---

## 12. Escalation 不是 Handoff Ping-pong

合法：

```text
triage -> billing -> human
```

坏：

```text
triage -> billing -> triage -> billing -> ...
```

后者烧 token、latency、budget 和 user patience，所以需要 total handoff/repeated-edge limit。

---

## 13. Manager vs Handoff Checklist

Manager/agents-as-tools：一个 Agent 负责 final response；specialist bounded；global context 集中；fan-in 确定。

Handoff：specialist 直接继续 conversation；domain ownership 真正变化；需要 conversation continuity；decentralized responsibility 是有意设计。

不要根据哪张图的箭头更酷来做 architecture decision。
