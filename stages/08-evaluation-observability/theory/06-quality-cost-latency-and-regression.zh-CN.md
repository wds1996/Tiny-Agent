# 06 — Quality、Cost、Latency 与 Regression Gate

> Language: [English](06-quality-cost-latency-and-regression.md) | 简体中文

Agent change 很少能在所有 dimension 同时“更好”。

所以 Stage 08 在决定 release 是否可接受前，会把 quality、reliability、safety、latency、cost 分开看。

---

## 1. Quality 是 Multi-dimensional

例如：

```text
answer correctness
tool selection F1
argument accuracy
trajectory safety
retrieval faithfulness
instruction following
```

Candidate 可以一项变好、一项退化。先看 component metric，再考虑 composite。

---

## 2. Reliability Metric

```text
execution_success_rate
timeout_rate
transient_failure_rate
permission_denial_rate
retry_rate
mean_retries_per_task
loop_detected_rate
```

Stage 07 已产生 classification；Stage 08 负责 aggregate/compare。

---

## 3. Latency

Mean 不够。99 个请求 1s、1 个请求 60s，mean 约 1.59s，却掩盖那个痛苦 outlier。

生产常看：

```text
p50 p90 p95 p99
```

并按 span 拆：model、retrieval、Tool、queue、retry/backoff。

### Parent/Child Span Duration 不能盲目相加

```text
invoke_agent      1000 ms
└── execute_tool   400 ms
```

End-to-end 是 **1000ms**，不是 1400ms。Child 已包含在 parent 时间里。

总 wall-clock 应用 root span 或 explicit timer；child 用来 breakdown，只有预先定义为 non-overlapping category 才能求和。

Trace tree 不是餐厅账单：不能看到数字就全部加起来。

---

## 4. Token Usage

关注 input/output/total tokens、tokens per successful task、tokens per Tool decision。

Token 增长可能来自 longer system prompt、oversized history、retrieved context、repeated planning、retry、verbose Tool observation。

Stage 06 context management 和 Stage 04 RAG 会直接影响 Stage 08 usage metric。

---

## 5. Cost

通常更有意义的是：

```text
cost per successful task
```

而不是只有 cost per model call。

一个便宜 model 若失败两次再 escalation，task-level 可能更贵。

```text
Model A: $0.01/call, 5 calls/task
Model B: $0.03/call, 1 call/task
```

B 反而可能便宜。

评估 system，不只评估一条 API line item。

---

## 6. Quality-Cost Frontier

```text
A: quality .88, cost .01
B: quality .92, cost .02
C: quality .93, cost .10
```

C 相比 B 只多 .01 quality，却多 5x cost。业务取舍不在 benchmark 自动决定。

用 Pareto frontier 思考：是否存在另一个配置，在所有重要维度至少不差，并至少一项更好？若有，被 dominate 的配置就难以 justify。

---

## 7. Hard Gate vs Optimization Metric

Hard constraint：

```text
trajectory_policy_ok == 1.0
critical safety cases == 1.0
permission bypasses == 0
```

Optimization target：quality、latency、cost。

不要允许更低 latency 去“补偿” forbidden action。

---

## 8. Absolute Threshold

例如：

```text
exact_match >= 0.95
execution_success >= 0.99
latency_ms <= 2000
```

`MetricGateRule.absolute_limit` 表示这个约束。

方向不同：quality/recall/success 是 higher-is-better；latency/cost/error rate 是 lower-is-better。

---

## 9. Relative Regression Threshold

Candidate 可能超过最低线，但相较 baseline 大幅退化：

```text
minimum = .80
baseline = .95
candidate = .86
```

所以还可要求：

```text
max_regression <= .02
```

---

## 10. Coverage 是 Release Metric

Grader 只跑一半 example，其 mean 不能与 full-coverage baseline 直接比较。

Tiny-Agent gated metric 默认：

```text
min_coverage = 1.0
```

避免“50 crash + 50 perfect = quality 1.0”。同时必须 gate `execution_success`。

---

## 11. Statistical Uncertainty

大规模 stochastic experiment 应考虑 sample size、confidence interval、repetitions、bootstrap、paired comparison、practical effect size。

Tiny-Agent teaching gate 故意小且 deterministic；production platform 可加入更强统计 machinery。

---

## 12. Paired Evaluation

Baseline/candidate 尽量跑同一批 case，再看 per-example delta：

```text
case 1: +0.1
case 2:  0.0
case 3: -1.0 safety
```

Mean 可能隐藏只发生在 critical category 的 regression，所以需要 slice analysis。

---

## 13. Slice Metric

可按 metadata：

```text
risk=high
language=zh
retrieval=true
multi_step=true
customer_tier=...
```

看分组结果。Global quality 提升时某个重要 slice 可能已经崩了。

敏感用户属性只有在合法、privacy-compliant 的评价目的下才应使用。

---

## 14. Previous Incident 应进入 Regression Set

每个 meaningful production bug 都应该问：能不能最小化成稳定 regression case？

```text
incident -> minimized example -> expected behavior -> regression dataset -> CI gate
```

可靠性就这样逐步积累。

---

## 15. Benchmark Gaming

只优化 gate 指标，可能伤害未测行为：为 latency 缩短回答却降低 helpfulness；为 Tool cost 直接不用 Tool；overfit exact wording；逃避 difficult case。

应定期检查 metric 是否仍代表真实 user value。

---

## 16. Tiny-Agent Regression Flow

```text
baseline commit -> EvaluationReport
candidate commit -> EvaluationReport
                   ↓
             RegressionGate
                   ↓
                pass/fail
```

Gate 不替你决定 product value；它把 value 变成足够明确、可被 CI enforcement 的规则。
