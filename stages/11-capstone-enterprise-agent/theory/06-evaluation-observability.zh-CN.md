# 06 — OpenScholar 的 Evaluation 与 Observability

研究 Agent 最危险的地方之一，是它可以“听起来非常专业”，同时在证据层面失败。

因此 Stage 11 把 evaluation 定义成对 **evidence usage 与 trajectory** 的契约，而不是只对 prose 做一次“观感评分”。

## 应该测量什么？

至少包括：

```text
status correctness
local evidence availability
citation labels used
unknown / hallucinated citations
citation coverage
grounding gate
required-term recall
retrieval counts
model calls
review revisions
Agent calls
latency / trace structure
```

如果答案写得非常漂亮，却引用 `[E999]`，而 `[E999]` 根本不存在，那就不能算成功。

## Deterministic First

`evaluate_research_report()` 先做不需要另一个 LLM 的检查：

```python
evaluation = evaluate_research_report(
    report,
    required_terms=("retrieval", "reasoning"),
)
```

evaluator 会抽取：

```text
[E1]
[E2]
...
```

并与 report 中真实 evidence inventory 比较。

## Unknown Citation

```text
available: [E1], [E2]
answer uses: [E1], [E999]
```

结果：

```text
unknown_citations = ([E999],)
```

这个检查应该 deterministic fail。

让 LLM judge 来判断 E999 是否存在，就像雇一位文学评论家帮你确认 database 有没有第 42 行——并不是它完全不能回答，而是你明明有更可靠的工具。

## Grounding Gate

当存在 local full-text evidence 时，一个 `completed` report 至少必须引用一个 local item。

当 substantive local evidence 不存在时，正确状态应该是：

```text
insufficient_evidence
```

这样同时防止两类相反错误：

```text
Evidence exists
but answer cites none
```

以及：

```text
Evidence does not exist
but answer confidently fabricates one
```

## Citation Coverage 并不总是“越高越好”

evaluator 可以统计：

```text
used available citations / available citations
```

如果很低，可能说明 retrieval noise 太多。

但如果强迫答案把每一个 retrieved chunk 都引用一遍，又可能出现 citation spam。

所以 citation coverage 是 diagnostic metric，不应机械设成 `must == 1.0`。

## Required-Term Recall

在 controlled regression set 中，我们可能提前知道某些概念必须出现。

Capstone 提供简单 deterministic required-term recall。

它适合 CI 教学案例，但绝不是 universal semantic-correctness metric。

真正研究答案的 nuanced quality 最终仍可能需要：

- expert human labels；
- calibrated LLM judges；
- domain-specific rubrics。

## Retrieval Evaluation 位于 End-to-End Evaluation 之下

如果 final answer 错了，trace 应该帮助定位错误来自：

```text
planner
retrieval
trust filtering
synthesis
review
memory
export
```

所以 observability 与 evaluation 必须组合使用。

trace 可能显示：

```text
openscholar.run
  plan                 3ms
  retrieve.local       2ms
  retrieve.crossref  800ms
  synthesize          20ms
  review.team         15ms
```

evaluation 告诉我们 grounding fail；trace 告诉我们应该去哪个 subsystem 里调查。

## Trace Data Model

Capstone 继续复用 Stage 08 `LocalTracer`，记录 nested spans，并允许以后适配 OpenTelemetry / LangSmith。

core 保持 vendor-neutral：

```text
OpenScholar
   -> Tracer interface
      -> local sink / OTel adapter / platform integration
```

## Privacy 仍然是 Observability 的一部分

default capture policy 不记录 raw input / output。

否则 trace backend 很容易不知不觉变成：

```text
complete user questions
+ complete paper corpus
+ complete Tool output
+ complete secrets
```

“为了方便 debug”不是一个足以绕过数据治理的理由。

## Base vs LangGraph Evaluation

非常有价值的 Capstone exercise：让两个实现跑**同一套 dataset**。

比较：

- final grounding pass rate；
- evidence counts；
- model calls；
- Agent calls；
- revisions；
- latency；
- approval / resume 行为。

如果它们共享 domain services，那么这些差异才真正能够反映 orchestration overhead / capability。

## Regression Gates

生产项目应该把部分 metrics 转成 release policy，例如：

```text
unknown citation rate = 0
insufficient-evidence behavior must remain correct
export path escape tests must pass
HITL resume test must pass
local retrieval regression cases must pass
```

quality metric 可以允许一定 statistical variation；security / grounding invariant 往往应该 hard gate。

不要让“文章写得更漂亮 +5%”抵消“开始出现假 citation”。

## Failure-Case Promotion

最好的 evaluation dataset 会不断吸收真实失败：

```text
production trace
  -> identify failure
  -> redact / minimize
  -> add deterministic or labeled regression case
  -> fix
  -> never silently regress again
```

成熟 Agent 工程会逐渐把生产环境里那些令人尴尬的 surprise，变成 CI 中无聊但稳定的 test。

而“无聊的 CI test”其实是工程领域非常值得骄傲的成就。