# 01 — 为什么 Agent Evaluation 很难？

> Language: [English](01-why-agent-evaluation-is-hard.md) | 简体中文

普通 function 往往很好测试：

```python
assert add(20, 22) == 42
```

Agent 不是一个普通 function。它是一个 policy-driven process，会选择 action、收集 evidence、调用 external system、retry、branch，并且可能在不同位置停止。

因此，“正确”这个词本身就变得多维。

---

## 1. Final Answer 只是一个 Observable

同一个 research task 有两个 run。

Run A：

```text
search
-> read trusted report
-> summarize
-> final answer
```

Run B：

```text
search
-> read trusted report
-> delete unrelated file
-> search again five times
-> summarize
-> final answer
```

两者 final sentence 一模一样。

如果 evaluator 只检查：

```text
final_answer == reference_answer
```

两者都会得到 1.0。

显然不够。

Agent evaluation 至少可能需要：

```text
Outcome quality
Tool selection
Tool arguments
Evidence quality
Trajectory quality
Safety / policy compliance
Reliability
Latency
Token usage
Cost
```

核心原则：

> **在理解不同 failure mode 之前，不要急着把它们压缩成一个数字。**

---

## 2. Correctness 有多个层级

### Final-response Correctness

问：最终 answer 是否完成 user task？

这是最 black-box 的评估，适用于用户可见 correctness、helpfulness、task completion、factuality/faithfulness 等。

但它解释不了“为什么成功/失败”。

### Single-step Correctness

问：在当前 state，Agent 是否选择了正确 next action？

例如：

```text
Should it call weather or calculator?
Did it use city="Tokyo" or city="Osaka"?
Should it retrieve at all?
```

适合 debug 某个 decision boundary。

### Trajectory Correctness

问：整个 decision/action sequence 是否可接受？

```text
search -> read -> answer
```

与：

```text
search -> search -> search -> read -> answer
```

后者可能仍正确，但效率更差。

而：

```text
search -> delete_database -> read -> answer
```

即使 final answer 完美，也完全不可接受。

---

## 3. Exact Trajectory Matching 也可能错

Reference：

```text
search -> read -> answer
```

实际 Agent 走：

```text
query_knowledge_base -> answer
```

同样安全、grounded，而且结果正确。

如果强制：

```python
actual_trajectory == reference_trajectory
```

就会错误惩罚 legitimate alternative。

Flexible Agent 常更适合：

- required-step coverage；
- forbidden-step detection；
- Tool-set precision/recall；
- sequence similarity；
- max-step / max-cost constraint；
- 必要时 semantic trajectory judge。

Tiny-Agent 用 LCS-like required-sequence recall + deterministic policy check 作为透明教学 baseline，但不把它吹成 universal metric。

---

## 4. Non-determinism 改变 Evaluation Experiment

Run 之间可能因这些因素变化：

- sampling；
- provider/model update；
- retrieval ordering；
- live API data；
- race condition；
- timestamp-dependent state；
- dynamic memory；
- parallel Tool completion order。

所以一次成功是很弱的 evidence。

Stochastic system 往往需要：

```text
same example
    -> run N times
    -> inspect mean / variance / failure rate
```

`EvaluationSuite` 支持 repetitions。

一次 demo 成功，就像只往雨伞上倒一茶匙水，然后宣布它已经通过暴雨测试：有一点参考价值，但离“能扛台风”还很远。

---

## 5. Evaluation != Testing

### Test

通常检查 crisp invariant：

```python
assert permission_denied
assert output == "42"
assert retry_count <= 2
```

尽量 deterministic。

### Evaluation

在 task distribution 上测量：

```text
answer correctness = 0.91
tool_f1 = 0.96
trajectory_policy_ok = 1.00
mean_cost = $0.014
p95_latency = 2.8 s
```

通常产生 continuous signal。

### Regression Gate

把 evaluation measurement 转回 release decision：

```text
if correctness < 0.90: fail CI
if safety < 1.00: fail CI
if latency regression > 20%: fail CI
```

即：

```text
Evaluation -> measurement
Regression gate -> policy over measurements
```

---

## 6. 先定义 Failure Mode，再选 Metric

坏问题：

> “我们需要一个 Agent score。”

更好的问题：

> “我们具体想检测哪种坏行为？”

| Failure | Useful signal |
|---|---|
| wrong Tool | Tool selection precision/recall/F1 |
| right Tool, wrong args | Tool argument accuracy |
| missed evidence | retrieval recall/document relevance |
| unsupported answer | faithfulness/citation support |
| forbidden action | deterministic policy score |
| useless loop | Tool-call count/loop rate |
| unstable result | repeated-run variance |
| slow response | latency percentiles |
| expensive response | cost/task, tokens/task |
| crash | execution-success rate |

每个 metric 都应该有存在理由。

---

## 7. Agent Evaluation 通常是 Multi-objective

```text
Candidate A
quality = 0.94
latency = 2.0 s
cost    = $0.01
safety  = 1.00

Candidate B
quality = 0.95
latency = 9.0 s
cost    = $0.12
safety  = 0.98
```

B 不能因为 quality 多 0.01 就自动叫“更好”。

生产选择通常是在 quality/reliability/safety/latency/cost 之间做 Pareto-style tradeoff。

Hard constraint 应保持 hard：

```text
safety must equal 1.00
execution_success >= 0.99
then optimize quality/cost
```

而不是让 catastrophic safety regression 被“更漂亮的回答”在 weighted average 中抵消。

---

## 8. Evaluation Dataset 是 Behavioral Specification

Agent example 可以包含：

```text
input
expected output
expected Tools
reference Tool arguments
required trajectory steps
forbidden Tools
Tool-call budget
risk class
source
split/version
```

也就是说，dataset 描述的是**行为预期**，不是只有答案文本。

---

## 9. 从真实 Failure Category 构建 Dataset

来源：

1. hand-curated critical cases；
2. previous bugs；
3. production traces；
4. adversarial/safety cases；
5. boundary cases；
6. representative normal traffic；
7. 有可信 seed set 后再做 synthetic augmentation。

先自动生成 500 个 case，却没人认真看过 20 个真实 case，很容易得到一个“看起来很大、实际测的是不存在分布”的 benchmark。

---

## 10. Evaluator 自己也会失败

Evaluator 也可能有：

- wrong references；
- ambiguous rubrics；
- label leakage；
- stale datasets；
- biased LLM judges；
- flaky dependencies；
- hidden missing-metric coverage；
- benchmark overfitting。

所以也要 evaluate evaluator：

```text
Does it agree with expert humans?
Can it separate known good/bad cases?
Is it stable across repetitions?
Does the rubric measure the intended construct?
```

---

## 11. Stage 10 Design Principle

Tiny-Agent 拆成：

```text
RunArtifact
├── output
├── spans
├── Tool calls
├── metrics
└── error

Evaluators
├── exact response
├── Tool selection
├── Tool arguments
├── trajectory
├── run metrics
└── optional LLM judge
```

因此既能回答：

```text
Did it fail?
```

也能回答：

```text
How did it fail?
```

第二个问题，才让 evaluation 从 leaderboard 变成 engineering tool。
