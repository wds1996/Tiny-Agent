# Stage 14：任务跑半天，不能靠一个 `while True` 硬撑——Long-Horizon Agent Harness

> Language: [English](README.md) | **简体中文**

Stage 13 已经把 Agent 变成服务。HTTP Request 可以快速返回 `run_id`，真正工作进入 Durable Queue；服务重启以后，Run Status 仍然存在。

看起来已经很稳了。然后我们让一个任务跑两小时。Worker 在第 87 分钟挂了，数据库里留下 `status = running`。新 Worker 看见以后说：“挺好，有人在跑。”旧 Worker 已经在云端化成一缕青烟。

这就是 Stage 14 的起点。

长时 Agent 的难点不只是“允许更大的 `max_steps`”。真正的问题是：

> **怎样让一个任务的进度脱离某个 Worker、某个进程、某次模型 Context，长期存在并可以被另一个执行者安全接手？**

这就是 Long-Horizon Harness 要解决的事情。

---

## 1. Long Horizon 不是把 Runtime Loop 拉长

一个最朴素的长任务：

```python
while not done:
    think()
    act()
```

只要进程一直活着，它确实能跑很久。但这和 Durable Long-Horizon 是两回事。

真正长任务必须面对 Worker 重启、进程部署、机器故障、网络中断、人工等待、Rate Limit、Workspace 回收和模型 Context 压缩。

如果任何一个事件发生，任务就从头开始，那它只是“长时间占着一条进程”，不是“可恢复的长期任务”。

---

## 2. Task Ledger：任务的真状态要放在外面

Stage 06 有 Checkpoint，Stage 13 有 Run Store。现在我们再向前一步，建立 Task Ledger。

Ledger 至少记录：

```text
task_id
status
step_index
total_steps
lease_owner
lease_until
progress
repair_count
```

它回答：**这个长期任务现在真正做到哪一步？**

关键是“真正”。不是模型上一次 Summary 里说做到哪，不是某个 Worker 内存里认为做到哪，而是 Durable Store 里可重新读取的执行事实。

---

## 3. 把大任务拆成 Bounded Work Unit

如果一个 Worker 领取以后负责从 0% 一直做到 100%，那 Worker 挂掉时，恢复粒度仍然很粗。

更好的方式是：

```text
Task
├── Step 0
├── Step 1
├── Step 2
└── ...
```

Worker 每次只处理一个 Bounded Work Unit。

本章 Harness 的 `work_once()` 恰好只做一步：

```python
task = ledger.claim(...)
output = step(progress)
ledger.record_step_output(...)
ledger.advance(...)
```

然后 Ownership 释放，下一步重新进入 Queue。这样任务天然形成很多 Durable Boundary。

---

## 4. 为什么每一步做完就重新 Queue？

因为这给了系统一个很干净的换班机会：

```text
worker-a
    ↓ step 0
persist progress
    ↓
queued

worker-b
    ↓ step 1
persist progress
    ↓
queued

worker-c
    ↓ step 2
```

这不表示生产系统一定每个 Node 都要换 Worker，可以连续执行多个 Work Unit。

但重要的是：

> **任务的继续执行不依赖“必须还是刚才那个 Worker”。**

这是 Long-Horizon Harness 的核心气质。

---

## 5. Lease：Running 不能等于永久占有

Stage 13 的 `running` 状态有一个问题：谁拥有它？拥有多久？

所以我们加入 Lease。

Worker A Claim：

```text
lease_owner = worker-a
lease_until = 12:00:30
```

只要 Lease 没过期，Worker B 不能抢。如果时间到了，A 还没续约，也没完成，那么系统可以判断 A 可能已经失联，于是 B 可以 Reclaim。

这比 `status = running` 多了一个极其重要的信息：

> **运行权是有期限的。**

---

## 6. Lease 不是 Lock 的另一个名字

普通 Lock 往往依赖一个活着的进程持有。

Lease 的关键是：

```text
ownership + expiry
```

即使 Owner 消失，时间到了以后 Ownership 也会自然失效。这特别适合跨进程、跨机器的 Worker 模型。

当然，真实分布式系统还要考虑 Clock、事务隔离、数据库语义和 Fencing Token。本章先把 Lease 的核心逻辑看清楚。

---

## 7. Heartbeat：我还活着，而且还在干

如果一个 Work Unit 确实需要跑很久，Lease 时间可能会过期。

Worker 可以定期：

```python
ledger.heartbeat(...)
```

把 `lease_until` 往后延。

但 Heartbeat 必须验证 `当前 lease_owner == 当前 worker`，否则任何 Worker 都能替别人续命。

本章检查专门验证 Worker B 不能为 Worker A 拥有的 Task Heartbeat。

Ownership 不能靠自报。

---

## 8. Lease 过期后重跑 Step，会不会产生重复副作用？

会。

场景：Worker A 执行 Step，外部副作用已经成功，但还没写 Ledger 就崩溃；Lease Expire 后 Worker B Reclaim，然后重新执行同一 Step。

你应该已经非常眼熟了。

这就是 Stage 06 和 Stage 09 反复强调的：

```text
recovery != exactly once
```

所以 Work Unit 最好幂等，或者有稳定 Idempotency Key，或者有可检查的完成条件，或者有补偿策略。

Harness 能恢复任务。它不能凭空替所有外部系统创造 Exactly-once。

---

## 9. Step Output 也要 Durable

本章有 `step_outputs`，主键是 `(task_id, step_index)`。

Worker 完成一步后：

```python
ledger.record_step_output(...)
```

结果可以被新进程读取。

这样后续 Step 不必依赖上一个 Worker 的内存，调试时也可以知道每一步实际产出了什么。

Long-Horizon 系统最怕：“任务现在在第 8 步，但前 7 步到底干了啥没人知道。”

---

## 10. Progress 不应该只存在模型 Context

假设 Agent 做一份长报告。如果所有 Progress 都只写在 Conversation 里，Context 一旦压缩、丢失或重新构建，任务就可能开始失忆。

更可靠的模式：

```text
模型 Context
    -> 用来做当前一步决策

Task Ledger
    -> 保存执行进度

Artifact Store
    -> 保存中间与最终产物
```

模型可以读 Durable Progress，但 Durable Progress 不应该依赖模型记得自己说过什么。

---

## 11. Artifact 是 Long-Horizon 的外部记忆器官

长任务很容易生成研究笔记、CSV、代码仓库、测试报告、中间草稿和最终报告。

把所有东西放进 Context 不现实。

所以 Harness 更像：

```text
Ledger
    -> 我做到哪了

Artifact
    -> 我做出了什么

Context
    -> 这一轮我需要看什么
```

三个层次再次分开。

Stage 12 已经建立 Workspace / Artifact 的区别。Stage 14 进一步要求 Artifact 能脱离当前 Compute 生命周期继续存在。

---

## 12. Repair Loop：失败以后不是只有“全任务重来”

长期任务很容易在后半程发现前面结果不合格。

例如：

```text
draft
    ↓
verify
    ↓
发现缺内容
```

一个笨办法是整个 Task 从头无限重跑。

本章允许 Evaluator 输出：

```python
{
    "needs_repair": True,
    "restart_step": 0,
}
```

Harness 把 Task 重新 Queue 到指定 Step。这就是一个最小 Repair Loop。

---

## 13. Repair 也必须有 Budget

如果 Draft 永远过不了 Verify：

```text
draft
verify fail
draft
verify fail
...
```

没有边界，Long-Horizon 就变成 Long-Forever。

所以 Task 记录 `repair_count` 和 `max_repairs`，超过以后直接 `repair budget exhausted`。

这和前面的 Agent Step Budget、Tool Budget、Retry Budget、Delegation Budget 一脉相承：自主循环必须有停止条件。

---

## 14. “Evaluator / Repair”不等于必须再加两个 Agent

这里特别容易回到 Stage 11 的架构冲动：Worker Agent、Evaluator Agent、Repair Agent、Manager Agent。

不一定。

Evaluator 可以是确定规则、测试程序、Schema Check、静态分析、人工 Review 或 LLM Judge。

根据任务选择最简单、最可靠的方法。

能运行测试判断代码是否通过，就不要先创建一个“测试哲学家 Agent”讨论它看起来像不像通过。

---

## 15. Compute Rehydration：新的 Worker 怎样重新建立工作环境？

Worker B 接手时，原来的临时目录可能已经没有了。

所以真实 Harness 需要能根据 Durable State 重建 Source、Inputs、Dependencies、Artifacts 和 Task Progress。

这叫 Rehydration。

Stage 12 的 Workspace 是当前 Compute 的工作台。Stage 14 的 Ledger / Artifact 决定：**新工作台要恢复哪些东西。**

本章 Demo 没启动真实 Container，但架构关系已经明确。

---

## 16. Session Handoff 不应该靠一段“请接着做”的 Prompt

很多长任务恢复会写：

```text
Previous agent summary:
"We were working on..."
Please continue.
```

Summary 可以作为 Context，但它不应该是唯一恢复依据。

更可靠的是 Task ID、Current Step、Structured Progress、Step Outputs、Artifact References 和 Repair History，然后再生成面向当前模型的 Handoff Context。

也就是说：

```text
Durable State
    ↓
build continuation context
    ↓
model
```

不是把 Model Summary 假装成 Durable State。

---

## 17. Long-Horizon 并不意味着无限自主

任务能跑几天，不代表应该给它无限 Tool Call、无限网络、无限 Cost、无限 Repair、无限 Delegation和无限 Credential。

时间尺度变长以后，Budget 反而更重要。

一个成熟 Harness 通常会有每个 Work Unit 的 Deadline、整个 Task 的 Budget、Cost Limit、Repair Limit、Permission Scope 和 Approval Point。

“长期”是 Durable，不是 Unlimited。

---

## 18. 运行完整代码

```bash
python stages/14-long-horizon-harness/code/demo.py
python stages/14-long-horizon-harness/code/checks.py
```

Demo 有三个 Step：Draft、Verify、Finalize。第一次 Verify 故意失败，触发一次 Repair，第二次通过，最后产生 Artifact。

检查覆盖 Expired Lease Reclaim、未过期 Lease 不能被偷、Heartbeat Owner、Step Output Durable、一次 `work_once()` 只推进一个 Work Unit、Repair Budget、Harness 重建后 Progress 仍在，以及 Completed Task 不再被领取。

---

## 19. 最后一章终于可以做 Capstone 了

现在从 Stage 00 回头看，我们已经不只是知道怎么“调用一个模型”。我们依次解决了输出契约、Tool Loop、Workflow/Planning、State Graph、RAG、MCP、Memory/HITL、Context、Skills、Reliability、Evaluation、Multi-Agent、Workspace、Production Service 和 Long-Horizon Harness。

最后一章不应该把这些东西全部打开，像毕业典礼上把家里所有电器同时插进一个插线板。

真正成熟的 Capstone 应该做另一件事：

> **面对一个具体业务，挑真正需要的机制，明确哪些能力故意不用。**

Stage 15 会做一个 Support Agent。它会查订单、查政策、在证据不足时拒答、对退款动作走审批、保存 Run，并留下可测试轨迹。

它不会为了“展示课程学全了”强行上五个 Agent。

这恰恰是毕业设计最重要的一课：**会做减法。**
