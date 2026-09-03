# 06 — Health、Graceful Shutdown、Durable Jobs、Metrics 与 Operations

> Language: [English](06-operability-and-background-work.md) | 简体中文

生产 Agent 的完成标准不是“回答过一次请求”，而是在 dependency failure、worker restart、queue 堆积、rolling deployment，以及一个 20 分钟任务跑到第 19 分钟时，系统仍然可理解、可恢复。

Operations 就是“我电脑上能跑”参加正式绩效考核的地方。

---

## 1. Liveness vs Readiness

**Liveness**：process 是否活到 restart 可能有帮助？应便宜、主要 local。

**Readiness**：这个 instance 现在是否应该接收新 traffic？可能依赖关键 Postgres 等。

如果 Postgres 短暂抖动就让所有 app instance liveness fail，orchestrator 会把健康进程集体重启——非常有创造力地制造额外事故。

---

## 2. Readiness 不是 Monitoring

Readiness 只回答：

```text
can this instance serve now?
```

Monitoring 要长期回答：error rate、p95/p99、queue saturation、timeout ratio、provider failure、cost/success、pool pressure。

一个绿色 `/readyz` 不能证明用户今天过得很开心。

---

## 3. Agent Service 的 Golden Signals

例如：request rate、success/failure/abstention、p50/p95/p99、queue wait、in-flight/peak、model calls/tokens/cost、Tool retry/failure、job queue depth/age、HITL wait、checkpoint/resume failure。

Stage 08 负责 evaluation/tracing；Stage 10 补 service saturation 与 infra dimension。

---

## 4. Graceful Shutdown

目标流程：

```text
1. mark not ready / stop new work
2. drain accepted short requests
3. persist/requeue long work
4. release worker leases safely
5. flush telemetry
6. close Redis/Postgres/provider clients
7. exit
```

如果 shutdown 正好发生在 side effect 中间，retry 仍必须遵循 Stage 07 idempotency semantics。

---

## 5. Short Request vs Durable Job

300ms Agent call 可正常 request/response。

20 分钟 research task 可能活得比 browser、proxy timeout、deployment、web worker、sandbox 更久。

更合理：

```text
POST /runs
  -> auth/validate
  -> durable enqueue
  -> 202 + run_id

worker claims
  -> executes/resumes

GET /runs/{id}
  -> state/result

optional stream/webhook
  -> progress view
```

**Durable record 才是 promise；HTTP connection 只是观察 channel。**

---

## 6. 为什么 `BackgroundTasks` 不是这个 Architecture？

它不自动提供 durable enqueue、retry/repair、lease、crash recovery、multi-worker coordination、dead-letter/manual intervention、cancellation semantics。

适合 small best-effort work。

不要对用户承诺“你的两小时任务正在处理”，而这份承诺实际上只活在某个 deployment 随时可能替换掉的 RAM 里。

---

## 7. Job Status 是 State Machine

生产可能需要：

```text
queued
running
waiting_for_human
waiting_for_external_task
completed
failed
cancelled
```

Tiny-Agent `SQLiteRunQueue` 使用更小 subset；Stage 10A `TaskLedger` 管一个 run 内部 sub-work。

不要把所有状态压成：

```text
done: bool
```

因为 ambiguity 本身就是生产问题。

---

## 8. Cross-layer Correlation

可能需要：request_id、run_id、thread_id、trace_id、privacy-governed subject/tenant、worker/instance id、external MCP/A2A task id。

日志应该让你能重建 trajectory，但不应该靠“把所有 prompt、secret、document 全 dump 到中央日志”来实现。

Observability 如果默认策略是 debug everything，也能独立制造数据泄露。

---

## 9. SLO Thinking

例如：

```text
99% accepted interactive runs finish <20s
99.9% durable runs never lose acknowledged work
<1% timeout rate
```

这些目标会反过来影响 admission、queue durability、retry、replica、fallback、timeout budget。

“快”和“可靠”只有量化以后才是 executable requirement。

---

## 10. Alert 用户真正受影响的症状

例如 sustained error/timeout、queue age/depth、readiness capacity collapse、provider failure、DB pool exhaustion、lease churn。

不要因为一次 transient error 就立刻把 on-call 从床上叫起来。

目标是 actionable alert，而不是给值班工程师构建一个 24/7“通知主题 Multi-Agent 系统”。

---

## 11. Rollout Failure Example

```text
new rollout
-> old worker running research job
-> SIGTERM
```

坏：kill -> job disappears -> client 还有 run_id 却再也查不到 state。

好：durable run record -> worker 停止 renew lease/持久 checkpoint -> lease expiry 后新 worker reclaim -> resume。

External side effect 仍需 idempotency，因为 crash point 可能 ambiguous。

---

## Completion Principle

> **把 Agent run 作为显式 state machine 运营：资源有界、saturation 可观察、承诺可持久化、shutdown/failure/recovery 语义明确。**
