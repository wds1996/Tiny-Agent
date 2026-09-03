# Stage 08 — Observability、Tracing 与 Evaluation

> Language: [English](README.md) | 简体中文

> 一个 demo 回答的是：**“它能不能成功一次？”**  Stage 08 要回答的是：**“刚才到底发生了什么？做得有多好？新版本有没有退化？”**

Stage 07 给 Tiny-Agent 增加了 deterministic execution control。Stage 08 则把这些行为变成**可以观察、可以度量、可以比较**的工程对象。

本阶段故意不从某个 hosted tracing dashboard 开始。我们先自己构建最小 local trace model 与 evaluation harness，再把这些机制映射到 OpenTelemetry 和 LangSmith。

---

## 为什么需要这一阶段？

Agent 比普通 request/response function 更难评估，因为 final answer 只是整个行为的一部分。

一个 Agent 可能：

- 最终答案正确，但用了错误 Tool；
- Tool 选对了，但 arguments 错了；
- 最终结果正确，却多做了 5 次无意义 retry；
- 给出了有用答案，但过程中碰了 forbidden capability；
- answer quality 不变，latency/cost 却显著上涨；
- 精心挑选的 demo 全通过，真实 production long tail 却不断失败。

所以本阶段首先区分三个问题：

```text
Logging
    -> 发出了哪些文本/事件记录？

Tracing
    -> 这次执行发生了什么？这些操作之间是什么因果结构？

Evaluation
    -> 按明确 criterion 判断，这个行为到底好不好？
```

Trace 是 evidence；Evaluator 是 judge；Dashboard 只是 view。三者谁也不会自动等于另外两个。

---

## 核心心智模型

```text
Agent execution
      |
      +--> spans / trace ----------------------+
      |                                        |
      +--> final output                        |
      +--> Tool trajectory                     |
      +--> failures / retries                  |
      +--> latency / tokens / cost             |
                                               v
                                      RunArtifact
                                               |
                          +--------------------+-------------------+
                          |                    |                   |
                          v                    v                   v
                    deterministic          LLM judge        human feedback
                       graders
                          |                    |                   |
                          +--------------------+-------------------+
                                               |
                                               v
                                       EvaluationReport
                                               |
                                      RegressionGate
                                               |
                                      CI / release decision
```

Tiny-Agent 一贯原则仍然成立：

> **模型可以提出 proposal；application code 负责观察行为、评估行为，并决定 release gate。**

---

## 学习目标

完成 Stage 08 后，你应该能够解释并实现：

1. logging、tracing、metrics、evaluation 的区别；
2. trace / span / parent-child relationship；
3. privacy-aware Agent input/output capture；
4. 在不改变 Tool governance semantics 的前提下 trace Tool execution；
5. 把 evaluation dataset 理解成 executable behavioral specification；
6. final-response evaluation；
7. single-step Tool selection 与 argument evaluation；
8. full-trajectory evaluation；
9. 为什么 exact trajectory matching 对 flexible Agent 往往太严格；
10. deterministic grader vs LLM-as-judge；
11. judge calibration 与 variance；
12. offline evaluation vs online evaluation；
13. quality / latency / token / cost metrics；
14. metric coverage，以及 missing score 怎样掩盖 crash；
15. CI regression gate；
16. OpenTelemetry 作为 vendor-neutral telemetry infrastructure；
17. 当前 OpenTelemetry GenAI semantic convention 的版本/演进风险；
18. LangSmith trace、dataset、experiment、online evaluation；
19. 为什么 trace 不等于 audit log；
20. sampling、retention、PII、secret 与 high-cardinality production concern。

---

## Stage Boundary

Stage 08 构建的是 **evaluation + observability foundation**，并不声称已经解决：

- production-scale telemetry storage；
- enterprise audit/compliance retention；
- Stage 10 所有 distributed service 的完整 tracing；
- 完美自动 task-success grading；
- fully calibrated LLM judge；
- model quality change 的 causal attribution；
- A/B experimentation platform；
- enterprise-scale adversarial red-team evaluation；
- 完整 SLO/alerting operations。

本阶段先让这些更大系统背后的抽象变得清楚。

---

# 推荐学习顺序

## 1. 为什么 Agent Evaluation 不同？

阅读：

- [`theory/01-why-agent-evaluation-is-hard.zh-CN.md`](theory/01-why-agent-evaluation-is-hard.zh-CN.md)

运行：

```bash
python stages/08-evaluation-observability/code/eval_dataset.py
```

核心：

```text
final answer quality != execution quality
```

## 2. 从 First Principles 构建 Trace

阅读：

- [`theory/02-tracing-and-observability.zh-CN.md`](theory/02-tracing-and-observability.zh-CN.md)

运行：

```bash
python stages/08-evaluation-observability/code/trace_model.py
python stages/08-evaluation-observability/code/local_tracer.py
python stages/08-evaluation-observability/code/traced_guarded_tool.py
```

```text
Trace = one end-to-end execution
Span  = one timed operation inside that execution
```

Local tracer 用 `ContextVar` 维护 parent-child context，并把完成的 span 放进 in-memory sink。

Raw input/output capture 默认关闭。Observability 绝不能为了 dashboard 好看，就把 Stage 07 的 secret-redaction 原则全部倒回去。

## 3. 评估 Tool 与 Trajectory

阅读：

- [`theory/03-tool-and-trajectory-evaluation.zh-CN.md`](theory/03-tool-and-trajectory-evaluation.zh-CN.md)

运行：

```bash
python stages/08-evaluation-observability/code/tool_call_evaluator.py
python stages/08-evaluation-observability/code/trajectory_evaluator.py
```

分别评估：

```text
Tool selection
Tool arguments
Required trajectory steps
Forbidden actions
Tool-call budget
Final answer
```

因为：

```text
right Tool + wrong arguments
```

和：

```text
wrong Tool + valid arguments
```

是完全不同的工程问题。一个统一 `agent_quality=0.63` 会把诊断信息抹掉。

## 4. 构建 Offline Evaluation Dataset

阅读：

- [`theory/04-offline-online-and-datasets.zh-CN.md`](theory/04-offline-online-and-datasets.zh-CN.md)

一个 Agent eval example 不只记录 input/output，还可以包含 expected Tool、reference arguments、required trajectory、forbidden Tool、budget 与 metadata。

## 5. 理解 LLM-as-Judge

阅读：

- [`theory/05-graders-and-llm-as-judge.zh-CN.md`](theory/05-graders-and-llm-as-judge.zh-CN.md)

运行：

```bash
python stages/08-evaluation-observability/code/llm_judge_boundary.py
```

经验法则：

```text
普通代码能稳定判断吗？
    yes -> 用代码
    no  -> 再考虑 human 或 LLM judge
```

除非你的预算已经产生了感情，否则没有必要请一个 stochastic LLM 来判断 `2 + 2 == 4`。

## 6. 把 Metric 变成 Regression Gate

阅读：

- [`theory/06-quality-cost-latency-and-regression.zh-CN.md`](theory/06-quality-cost-latency-and-regression.zh-CN.md)

运行：

```bash
python stages/08-evaluation-observability/code/regression_gate.py
python stages/08-evaluation-observability/code/end_to_end_eval.py
```

例如：

```text
execution_success >= 1.00
exact_match       >= 0.95
tool_f1           >= 0.95
trajectory_policy == 1.00
latency_p95       <= threshold
cost_per_task     <= threshold
```

Tiny-Agent 还检查 **metric coverage**：如果一半 run 直接 crash，不能只用幸存的一半算出“完美平均分”。

## 7. 映射到 OpenTelemetry 与 LangSmith

阅读：

- [`theory/07-opentelemetry-langsmith-and-production.zh-CN.md`](theory/07-opentelemetry-langsmith-and-production.zh-CN.md)

运行：

```bash
python stages/08-evaluation-observability/code/opentelemetry_tracing.py
python stages/08-evaluation-observability/code/langsmith_traceable.py
```

```text
OpenTelemetry
    -> vendor-neutral telemetry APIs/context/processors/exporters,
       traces/metrics/logs + evolving GenAI semantic conventions

LangSmith
    -> LLM/Agent-oriented tracing UI, datasets, experiments,
       evaluators, feedback, online/offline evaluation workflows
```

它们都不会替代你先学会的 evaluation design。

---

# Reusable Tiny-Agent API

## Local tracing

```python
from tiny_agent import InMemorySpanSink, LocalTracer

sink = InMemorySpanSink()
tracer = LocalTracer(sink)

with tracer.span("invoke_agent", kind="agent"):
    with tracer.span("execute_tool search", kind="tool") as span:
        span.set_attribute("tool.name", "search")
```

## Privacy-aware capture

```python
from tiny_agent import TraceCapturePolicy

policy = TraceCapturePolicy(
    capture_inputs=True,
    capture_outputs=True,
    max_text_chars=256,
)
```

即使 capture 被打开，`password`、`token`、`api_key`、`authorization` 等 key 仍会被 redact。

这是 teaching safeguard，不是完整 DLP system。

## 观察 Stage 07 Guarded Executor

```python
observed = ObservedGuardedToolExecutor(
    guarded_executor,
    tracer,
)
```

这个 adapter 只负责 observe，不会替代 validation、permission、approval binding、budget、retry、timeout。

## Evaluation dataset

```python
example = EvalExample(
    id="case-001",
    inputs={"question": "..."},
    reference_output="...",
    expected_tools=("search",),
)
```

## Evaluation suite

```python
suite = EvaluationSuite([
    ExactMatchEvaluator(),
    ToolSelectionEvaluator(),
    TrajectoryEvaluator(),
])

report = suite.run(dataset, target)
```

## Regression gate

```python
gate = RegressionGate([
    MetricGateRule("execution_success", absolute_limit=1.0),
    MetricGateRule("trajectory_policy_ok", absolute_limit=1.0),
])
```

---

# 不要把所有 Metric 压成一个分数

| Dimension | Example metric | 作用 |
|---|---|---|
| execution | `execution_success` | target 是否 crash |
| answer | `exact_match` / correctness judge | 最终结果是否正确/有用 |
| Tool choice | precision / recall / F1 | capability 选择是否合适 |
| Tool arguments | argument accuracy | Tool 输入是否正确 |
| trajectory | sequence recall | required steps 是否出现 |
| safety | `trajectory_policy_ok` | forbidden Tool/budget 是否被遵守 |
| reliability | failure/retry rate | transient problem 是否过多 |
| latency | mean/p50/p95 | 用户等待多久 |
| usage | tokens | 消耗多少 model capacity |
| economics | cost/task | 改进是否值得成本 |

Composite score 可以辅助排序，但 component score 必须可见。

否则可能出现：

```text
quality improved +2%
safety regressed -100%
weighted average: looks fine 😬
```

安全退化不能靠“文案更好看”抵消。

---

# Offline vs Online Evaluation

## Offline

用于 release 前：regression、prompt/model comparison、Tool/RAG/policy change、reproducible benchmark、incident backtest。

## Online

利用 production trace 观察真实分布、drift、rare failure、feedback、latency/cost，并把有价值 failure 转回新的 offline regression case。

不要把每一条 production trace 都无脑送给昂贵 LLM judge。

---

# OpenTelemetry 2026 注意事项

OpenTelemetry 在 2026 年 3 月宣布 deprecate **Span Events API**。新的 event-like instrumentation 应朝与当前 span 关联的 log-based event 方向迁移。

所以本阶段使用：

```text
span hierarchy for operations
+ logs for event-like records when needed
```

而不新增 `span.add_event(...)`。

GenAI semantic conventions 也仍在快速演化，attribute name 应被当作 versioned convention，而不是永恒法律。

---

# LangSmith 注意事项

当前 LangSmith 概念：

```text
Trace       -> 查看一次执行
Dataset     -> evaluation examples 集合
Experiment  -> target × dataset + evaluator scores
Online eval -> 对选中的 production run/thread 进行评价
```

Tiny-Agent 先构建 local model，再引入平台，是为了让平台术语不再抽象。

Runnable example 用 `tracing_context(enabled=False)`，因此 CI 不需要 API key 或 network upload。

---

# 安装

```bash
python -m pip install -e ".[dev]"
```

Stage 08 integrations：

```bash
python -m pip install -e ".[dev,stage08]"
```

---

# Exercises

完成：

- [`exercises/review-questions.zh-CN.md`](exercises/review-questions.zh-CN.md)

---

# Milestone

你应该能够构建并解释：

```text
Agent run
  -> privacy-aware trace
  -> RunArtifact
  -> final/Tool/trajectory evaluators
  -> multi-dimensional report
  -> regression gate
  -> OpenTelemetry/LangSmith integration
```

更重要的是回答：

> **如果 Agent 最终答案正确，但它通过浪费资源、不安全或未授权的 trajectory 得到这个答案，这次执行应该通过 evaluation 吗？**

Tiny-Agent 的答案是：**不应该。**
