# 04 — Evaluator、Repair、Replanning 与 Session Boundary

长时程 Agent 必须回答一个看似简单的问题：

> 系统怎么知道“真的有进展”，而不是模型自己觉得进展不错？

“模型说看起来没问题”只能算很弱的证据。

只要条件允许，就应使用外部 evaluator / test。

---

## 1. Evaluator Feedback 闭合执行循环

```text
worker produces result
        ↓
evaluator / test
        ↓
pass -> complete task
fail -> repair / replan / human
```

不同领域可以使用不同证据：

```text
coding      -> tests / lint / type checks
research    -> citation / evidence checks
ETL         -> schema / row invariants
report      -> required sections / format
security    -> policy checks
```

evaluator 可以是 deterministic、model-based、human，或者多层组合。

---

## 2. 能用确定性代码检查，就先用代码

如果条件能够被普通程序精确判断：

```python
assert output_file.exists()
assert tests_passed
assert citation_ids <= known_evidence_ids
```

就没有必要先请另一个 LLM “发表一下看法”。

semantic judge 更适合普通代码无法可靠回答的问题，例如：

```text
这份 evidence 是否真正支撑 claim？
报告是否在实质上完整？
```

即使是 model judge，也只是 evaluator，不是 execution authority。

---

## 3. Retry、Repair、Replan 是三件不同的事

### Retry

基本方法不变，重新尝试同一个 operation：

```text
HTTP 503
-> bounded retry + backoff
```

### Repair

方向基本正确，但产物存在局部错误：

```text
unit test fails
-> inspect failure
-> patch code
```

### Replan

当前方法或前提本身已经错误：

```text
source unavailable
assumption invalid
-> change strategy / task list
```

如果失败属于概念层错误，blind retry 只会让系统更执着地重复同一个错误答案。

“坚持不懈”是优点，但在错误策略上坚持不懈通常只是账单变长。

---

## 4. Failed Task 要留下可行动证据

建议保存：

```text
error category
brief note
artifact / log path
attempt count
relevant evaluator output
```

不要把无界 stack trace 每次都塞进未来 session 的 prompt。

完整 log 可以作为 artifact；handoff 只携带能够推动下一步的摘要。

---

## 5. Session Boundary 本身就是架构工具

主动结束一个 model session 不一定表示失败。

合理的 session boundary 可以：

- 清除不断累积的 context noise；
- 切换 model / Skill role；
- 释放昂贵资源；
- 创建干净的 human-review point；
- checkpoint durable progress。

长任务应该从设计上允许新的 model instance 接手。

如果整个 Agent 只有在“这一场聊天永远不要结束”的条件下才能正常工作，那么所谓 memory architecture 很可能只是一个浏览器标签页。

---

## 6. Handoff 要给下一任 Worker 明确的 Action Affordance

有用的 summary：

```text
Objective: fix authentication regression
Completed: reproduced bug, identified failing module
Current failure: refresh-token test still fails
Relevant artifacts: logs/test-2.txt, src/auth.py
Next task: inspect token expiry conversion
```

下一 worker 一上来就知道从哪里开始。

而下面这种文字几乎没有操作价值：

```text
“We tried many things. Continue investigating.”
```

---

## 7. Evaluator 本身也可能制造循环

糟糕模式：

```text
writer -> critic -> writer -> critic -> ... until perfection
```

“直到完美”为 stop condition，通常意味着“直到预算提醒你现实存在”。

因此 evaluator / repair loop 同样需要：

```text
max repair attempts
max model calls
max wall time
max cost
human escalation threshold
```

Stage 09 的 bounded-loop 原则在多 session 尺度上仍然成立。

---

## 8. 示例：Coding Repair

```text
task: implement parser
worker writes parser.py
pytest -> 2 failures
```

harness 不应直接把任务标记 completed。

而应该：

```text
record failure artifact
-> create / continue repair task
-> next worker loads failing test + parser + brief handoff
-> patch
-> pytest passes
-> task completed
```

一旦精确代码和测试都已经进入 workspace，上一轮完整 coding conversation 通常已经没有继续重放的必要。

---

## 9. Human Review 也可以成为 Session Boundary

高风险操作：

```text
generated migration ready
```

harness 可以持久化：

```text
status = waiting_for_human
artifact = migration.sql
```

worker 随即退出。

几小时后，经过认证的 reviewer 做 approve / reject，再由一个**新的 worker**恢复流程。

这比让一个模型调用悬在 RAM 里等人下午开完会回来要可靠得多。

---

## 完成原则

> **用 evaluator 把“进展”变成证据；区分 transient retry 与 semantic repair / replanning；把 session boundary 视为正常的 resumable checkpoint，而不是灾难性的失忆。**