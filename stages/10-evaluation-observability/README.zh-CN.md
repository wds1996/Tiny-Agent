# Stage 10：别只看最后一句答得像不像——Evaluation 与 Observability

> Language: [English](README.md) | **简体中文**

Stage 09 给 Agent 装上了护栏：Validation、Permission、Budget、Retry、Deadline、Safe Error 都有了明确位置。

这时团队里很容易出现一个熟悉场景。工程师 A 说：“我刚优化了 Agent，效果好多了。”工程师 B 问：“怎么证明？”A 打开聊天窗口，问了三个问题，三个都答得不错，然后会议结束。

这不是 Evaluation。这叫“挑了三个顺眼的例子给大家看”。

Agent 比普通函数更难测，因为它的质量不只在最后一句话里。两个 Agent 可能得到同一个答案，其中一个只查了一次正确资料，另一个却先调错三个 Tool、绕了八步、花了五倍 token，最后靠运气碰到正确结果。

如果只比较 Final Answer，它们看起来一样好。

Stage 10 就解决这个问题：

> **既要看结果，也要看过程；既要能解释一次 Run 发生了什么，也要能用固定数据集判断系统改动到底是进步还是回归。**

前者是 Observability，后者是 Evaluation。它们关系很近，但不是一回事。

---

## 1. Log、Trace、Metric 先别混在一起

最普通的 Log：

```text
2026-09-04 lookup_order success
```

能告诉我们“发生了一件事”。

Metric 更像聚合数字：

```text
tool_success_rate = 98.4%
p95_latency = 820 ms
average_tool_calls = 2.3
```

Trace 则试图回答：**这一次请求完整经历了什么？**

```text
run-42
├── context.build
├── model.turn
├── tool.lookup_order
├── retrieval.search_policy
├── model.turn
└── final
```

三者不是互相替代。Log 适合离散事件，Metric 适合看整体趋势，Trace 适合还原一次 Run 的因果链。

Agent 特别需要 Trace，因为它往往不是一次函数调用，而是一条轨迹。

---

## 2. Span 是 Trace 里的“这一小段发生了什么”

我们先写一个很小的 Span：

```python
@dataclass(frozen=True, slots=True)
class Span:
    name: str
    duration_ms: float
    attributes: Mapping[str, Any]
    status: str
```

然后用：

```python
with tracer.span("tool.lookup_order", tool="lookup_order"):
    ...
```

记录某一步。

一个 Agent Run 里常见的 Span 可能包括：

```text
context.build
model.generate
retrieval.search
tool.execute
policy.authorize
memory.read
skill.activate
```

你会发现，前面每一章建立的机制，现在都开始有了一个可观察的位置。这就是课程为什么把 Observability 放到这里，而不是 Stage 01 就先教某个监控 SDK：你得先有值得观察的系统。

---

## 3. Trace 不是“把所有内容全部存下来”

很多团队第一次加 Trace，会想：“太好了，以后所有 Prompt、Tool Result、Memory 都完整记录，排查一定方便。”

确实方便，也可能顺便把用户隐私、Access Token、内部文档和敏感 Tool 参数保存得整整齐齐。

Observability 本身也是数据系统，它同样需要最小化、权限和保留策略。

所以本章的 `CapturePolicy` 默认：

```python
capture_content=False
```

字符串不直接保存，而只记录长度和摘要 Hash。

如果某个受控环境明确需要抓取内容，可以显式打开：

```python
CapturePolicy(
    capture_content=True,
    max_text_chars=120,
)
```

并且仍然限制长度。

默认不抓全文，意味着“调试方便”不能自动压过“数据边界”。

---

## 4. 为什么 Hash 也有用？

假设两个 Run 都出现：

```text
prompt_sha256 = 3fe0a8c2762d
```

你虽然不知道 Prompt 原文，却能知道它们处理的是同一份内容。同样，如果某个 Context Item 每次都发生变化，Hash 也会变化。

Hash 不是隐私的万能解决方案，尤其对低熵数据仍可能被猜测。但它展示了一个重要思想：

> **Observability 可以记录结构和关联，而不必默认记录全部原文。**

---

## 5. Status 也应该属于 Span

本章的 Tracer 会记录 `status = ok` 或 `status = error`。

如果 `with tracer.span(...)` 内部抛异常，Span 记录 Error，然后异常继续向上抛。

为什么不吞掉？因为 Tracing 是旁观者。

> **Observability 不应该悄悄改变被观察系统的语义。**

这条原则后面做任何 Instrumentation 都很重要。

---

## 6. Evaluation 为什么不能只看 Final Answer？

来看一个退款案例，期望 Agent 的轨迹是：

```text
lookup_order
search_policy
final answer
```

Agent A 正常执行。

Agent B 却先 `search_weather`，然后重复 `lookup_order`，最后才找到政策。

最终答案完全一样。如果只打 Answer Accuracy，A 和 B 都 Pass，你就会错过 B 明显更差的 Trajectory。

所以本章的 Eval Case 同时定义：

```python
EvalCase(
    question=...,
    expected_answer_contains=("30 days",),
    expected_tools=("lookup_order", "search_policy"),
)
```

然后分别评分：

```text
answer_ok
tool_trajectory_ok
abstention_ok
```

最后才组合成 Pass。

---

## 7. Component Eval 比“全系统一个总分”更容易修 Bug

Stage 04 已经学过 Retrieval 的 `Recall@K`。这是因为 Retrieval 本身就有独立质量。如果 Ground Truth Evidence 根本没被 Retriever 找到，Generator 再聪明也没材料。

所以 Agent Eval 应该尽量拆层：

```text
Router
    -> route accuracy

Retriever
    -> Recall@K / MRR

Tool layer
    -> success / argument correctness

Context Builder
    -> required-context retention / omission

Agent trajectory
    -> tool sequence / step budget / unnecessary actions

Final answer
    -> correctness / groundedness / abstention
```

当总分下降时，Component Eval 能告诉你从哪里开始找。否则你只能对着 Final Answer 猜：“是不是 Prompt 又不够有灵性？”

---

## 8. Deterministic Eval 应该尽可能先上

能用确定规则判断的东西，不必第一时间请另一个 LLM 当裁判。

例如：应该调用 `lookup_order` 吗？Tool 参数对不对？有没有超出 Budget？Evidence 不足时是否 Abstain？相关文档是否进入 Top-K？这些都有确定答案。

确定性 Evaluator 的优点很朴素：便宜、稳定、可重复、失败容易解释。

LLM Judge 不是没用。它适合那些确实难写成简单规则的问题，例如语义完整性、写作质量或开放式支持度。但要知道 Judge 也是模型，也有自己的误差、成本和版本漂移。

不要用一个不稳定评分器去掩盖本来可以精确判断的问题。

---

## 9. Eval Dataset 是产品行为的“考试卷”

随手问几个问题，不叫 Dataset。

一个最小 Eval Dataset 应该保存稳定 Case：

```python
EvalCase(
    id="refund-within-window",
    question="...",
    expected_answer_contains=("30 days",),
    expected_tools=("lookup_order", "search_policy"),
)
```

Case 最好来自真实失败模式、关键业务路径和边界条件，而不是只收集“模型最容易答对的示范题”。

随着系统迭代，过去修过的 Bug 应该进入 Dataset。这样它们不会每隔三个月换个发型重新回来。

---

## 10. Abstention 也是正确行为

Stage 04 已经建立了一个重要能力：Evidence 不足时 Abstain。

所以 Eval 也要表达：

```python
should_abstain=True
```

如果一个问题没有足够证据，Agent 自信地编了一段漂亮答案，不能因为“句子通顺”给高分。

在很多场景里，正确地说不知道，比错误地装懂更有价值。

---

## 11. Unnecessary Tool Rate 是一个很实用的小指标

假设 Greeting Case 只问 `hello`，期望 Tool 是空元组，但 Agent 先调了 `lookup_order`，最后还是说 `Hello.`。

Answer 没错，行为却很奇怪。

所以本章统计：

```text
unnecessary_tool_rate
```

它能抓出一种常见退化：模型变得“什么问题都想先调点东西显得很忙”。Agent 很容易出现这种数字化职场表演，Eval 应该能识别。

---

## 12. Latency 和 Cost 也是质量

如果新版 Agent Accuracy 从 92% 提到 93%，但 Tool Call 从 2 次变 9 次、Latency 从 1.2 秒变 8.4 秒、Cost 翻六倍，这不能自动叫“升级”。

质量至少是一个多目标问题：

```text
correctness
groundedness
latency
cost
reliability
user experience
```

不同产品权重不同，因此 Regression Gate 也不应该只有 `pass_rate >= 0.9`，还可能限制 P95 Latency、平均 Tool Call 和 Abstention 行为。

---

## 13. Offline Eval 和 Online Signal 不是同一件事

Offline Eval 使用固定 Dataset、固定期望，在开发和 CI 中反复运行，优点是可重复。

Online Signal 来自真实生产请求、真实用户分布、真实延迟与失败，优点是现实。

只做 Offline，Dataset 可能和真实流量脱节；只看 Online，又很难做受控对比，而且错误已经发生在用户身上。

两者要配合。

---

## 14. Trace 怎么帮助 Eval？

假设一个 Case 失败了：期望答案包含 “30 days”，实际却说 “policy unclear”。

Trace 可能告诉你：

```text
retrieval.search
    -> 找到了 refund-policy

context.build
    -> refund-policy 被 omission

model.generate
    -> 根本没看到政策
```

于是 Bug 不在 Retriever，也不一定在 Model，而在 Context Selection。

这就是两者的组合价值：

```text
Eval
    -> 告诉你哪里退化

Trace
    -> 帮你解释为什么退化
```

---

## 15. Trace 也应该记录 Policy Decision

Stage 09 有 Authorization。如果 Tool 没执行，你需要区分：模型没提、Validation 失败、Permission Denied、Approval Reject，还是 Tool 真正执行后失败。

只记录 `tool failed` 会把完全不同的问题揉成一团。

所以好的 Trace 应该沿责任边界放 Span，而不是只围着网络请求打点。

---

## 16. Eval 不应该反过来控制被测 Agent

Evaluator 的职责是观察和评分。

不要让它为了“判断模型是否会调 Tool”而偷偷帮模型调一次 Tool；也不要让 Judge 自动修答案以后再评分。

否则你测的是 `Agent + Evaluator` 的联合系统，不是 Agent 本身。

测试工具也要保持边界。

---

## 17. 一个最小 Regression Report

本章 Evaluator 输出：

```python
EvalReport(
    scores=...,
    pass_rate=...,
    unnecessary_tool_rate=...,
    average_latency_ms=...,
)
```

这个 Report 很小，但已经比“我试了几个问题感觉不错”强很多。

以后完全可以继续增加 Retrieval Recall、Tool Failure Rate、Token Usage、Cost、Policy Denial Rate 和 Context Omission Rate。先把 Eval Loop 建起来，再逐渐增加指标。

---

## 18. 运行完整代码

```bash
python stages/10-evaluation-observability/code/demo.py
python stages/10-evaluation-observability/code/checks.py
```

Demo 先产生两个 Span，再跑三个固定 Eval Case。

检查覆盖默认不抓原始 Prompt、显式 Capture 仍有长度上限、Span 正确记录 OK / Error、Answer 与 Tool Trajectory 分开评分、Abstention、Unnecessary Tool Rate 和 Retrieval Recall@K。

---

## 19. 为什么下一章才讨论 Multi-Agent？

我们已经能比较一个 Agent 的结果、轨迹、成本和失败。现在才有资格问：

> **把一个 Agent 拆成多个 Agent，真的更好吗？**

如果没有 Eval，Multi-Agent 很容易变成架构表演：一个 Agent 拆成五个 Agent，图变复杂了，大家觉得很高级，但 Accuracy 有没有提高、Latency 是否翻倍、Context 在 Agent 之间丢了什么，没人知道。

所以下一章 Stage 11 会先从一个非常克制的问题开始：

> **什么时候真的需要第二个 Agent？**

然后再讲 Delegation、Handoff、Context Projection 和 Team Runtime。
