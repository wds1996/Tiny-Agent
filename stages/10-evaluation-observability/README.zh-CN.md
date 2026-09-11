# Stage 10：别只看最后一句答得像不像——Evaluation 与 Observability

> Language: [English](README.md) | **简体中文**

Stage 09 已经把 Validation、Permission、Budget、Retry 和 Deadline 放进了 Runtime。现在有一个顺理成章的问题：修改了 Prompt、Tool、RAG 或 Guardrail 之后，怎么知道系统真的变好了？

随手挑几个回答顺眼的问题试一试，只能说明这几个演示碰巧不错。Agent 的质量还存在于它走过的路径中：有没有漏掉关键证据、是否调了不该调的 Tool、花了多少步骤、被护栏拒绝的原因是什么、是否在证据不足时停止猜测。

这一章建立两种互补能力：

| 要回答的问题 | 能力 | 产物 |
| --- | --- | --- |
| “这一次 Run 到底发生了什么？” | **Observability（可观测性）** | Trace、Log、Metric |
| “这次改动是否让一组重要行为变好？” | **Evaluation（评测）** | 固定 Case、评分、回归报告 |

先用 Trace 解释单次失败，再用 Evaluation 判断整体是否退化。它们不能互相替代：Trace 不是成绩单，Eval Report 也无法自动解释失败原因。

---

## 1. 从“护栏已存在”到“护栏可以被证明”

Stage 09 中，Tool 没有执行可能有很多原因：模型没有提出调用、参数校验失败、权限被拒绝、预算耗尽、Deadline 到期，或真正的外部依赖失败。只写一条 `tool failed` 日志，会把这些责任边界全部揉在一起。

因此，Stage 10 的起点不是选择某个监控产品，而是保留系统已有的边界：

```text
agent.run
├── context.build
├── model.generate
├── policy.authorize
├── tool.lookup_order
├── retrieval.search_policy
└── final response
```

这里的每一行是一个 **Span**：一次较小、职责明确的工作。由同一个 `run_id` 关联起来的所有 Span 是一条 **Trace**。

三个常见词的分工如下：

| 信号 | 回答的问题 | Agent 中的例子 |
| --- | --- | --- |
| Log | “发生了哪件离散事件？” | `permission denied for issue_refund` |
| Metric | “许多 Run 的总体趋势是什么？” | P95 延迟、Tool 成功率、平均 Tool 次数 |
| Trace | “这个 Run 按什么顺序走到了结果或失败？” | 此次检索到了什么、调用了哪些 Tool、在哪一步被拒绝 |

例如 `P95 延迟 = 820 ms` 的意思是：95% 的 Run 在 820 毫秒内完成，最慢的 5% 更慢。它比平均值更容易暴露“少数请求卡得很久”的问题。

真实工程中可继续学习 [OpenTelemetry 的 Observability Primer](https://opentelemetry.io/docs/concepts/observability-primer/)。OpenTelemetry 是用于统一记录和导出这类观测数据的一套开放标准。本章先手写一个小实现，目的不是替代 SDK，而是让 Trace 的数据结构和边界清楚可见。

---

## 2. 先追踪一个完整 Run，而不是只打印一行日志

[`code/tracing.py`](code/tracing.py) 中的 `Tracer` 会为每个 Span 保存名称、开始时间、耗时、属性、状态，以及 `span_id` / `parent_span_id`。后两个字段保证 Trace 真的是一棵树，而不只是几条恰好排在一起的日志。

下面是一个可直接运行的最小 Trace；它和 [`code/demo.py`](code/demo.py) 使用同一套 API：

```python
from tracing import CapturePolicy, Trace, Tracer, format_trace

trace = Trace("run-001")
tracer = Tracer(trace, capture_policy=CapturePolicy(capture_content=False))

with tracer.span("agent.run", workflow="refund_support"):
    with tracer.span("context.build", question="Can ORDER-42 be refunded?") as span:
        span["selected_items"] = 3

    with tracer.span("tool.lookup_order", tool="lookup_order") as span:
        span["status_code"] = 200

print(format_trace(trace))
```

输出的核心结构是：

```text
run-001
└── agent.run [ok]
    ├── context.build [ok]
    └── tool.lookup_order [ok]
```

`agent.run` 是父 Span；`context.build` 和 `tool.lookup_order` 是它的子 Span。Span 的名称描述职责；**属性（attribute）**是附在该步骤上的“键—值小纸条”，补充结构化事实，例如 `selected_items=3` 表示选了三条 Context，`status_code=200` 表示请求成功。不要把整段 Prompt 或整个 Tool Result 默认塞进属性里，下一节会说明原因。

Instrumentation 是旁观者，不应改变业务结果。如果 `with tracer.span(...)` 内部抛出异常，Tracer 会记录 `status="error"` 和异常类型，然后继续抛出原异常：

```python
from tracing import Trace, Tracer

trace = Trace("failed-run")
try:
    with Tracer(trace).span("tool.lookup_order"):
        raise RuntimeError("connection lost")
except RuntimeError:
    pass

span = trace.spans[0]
assert span.status == "error"
assert span.attributes["error_type"] == "RuntimeError"
```

这个片段刻意不保存 `connection lost` 的原始异常文本。对模型可见的安全错误、面向工程师的受控诊断，以及 Trace 属性应有不同的数据边界；这与 Stage 09 的 Safe Error 原则一致。

现在就可以运行并观察结构：

```bash
python stages/10-evaluation-observability/code/demo.py
```

---

## 3. Trace 是数据系统，先设计它能保存什么

Trace 很适合排查问题，也因此很容易收集到 Prompt、用户资料、检索文档、密钥或 Tool 参数。可以把它看作一次 Run 的“维修记录”：需要知道哪一步花了多久、是否成功，却不必默认把用户说过的每一句话复印进记录里。可观测性本身同样需要最小化、访问控制和保留策略。

`CapturePolicy` 就是写入这份维修记录前的过滤器。每个 Span 的属性先交给它处理，再保存到 Trace。

本章的默认 `CapturePolicy` 不保存字符串原文，而保存其长度和前 12 位 SHA-256 摘要：

```python
from tracing import CapturePolicy

policy = CapturePolicy(capture_content=False)
safe = policy.sanitize({"prompt": "private text", "selected_items": 3})

assert safe == {
    "prompt_sha256": "66c279b1e928",
    "prompt_chars": 12,
    "selected_items": 3,
}
```

`prompt_chars=12` 只是原文长度；`prompt_sha256` 则是 `private text` 计算出的固定“指纹”。不需要理解 SHA-256 的数学细节：同一段文字每次会得到同一个指纹，文字变化后指纹通常也会变化。因此我们能判断“两个 Run 是否用了同一段内容”或“某次 Context 是否改变”，但默认不会把原文写入 Trace。

Hash 不是隐私的万能解法。所谓**低熵值**，可以理解为候选很少、很容易枚举的值，例如 `yes/no`、国家代码或只有几个选项的状态；别人可以逐个计算候选值的 Hash 来猜原文。因此 Hash 是减少默认暴露的手段，不是绕过数据治理的理由。

确有受控排障需求时，才显式打开内容捕获，并给出硬长度上限：

```python
from tracing import CapturePolicy

policy = CapturePolicy(capture_content=True, max_text_chars=4)
assert policy.sanitize({"prompt": "abcdef"})["prompt"] == "abcd"
```

生产系统还需要确定谁可以看 Trace、保存多久、哪些字段必须**脱敏**（把密钥等内容替换成 `[REDACTED]`），以及怎样**采样**。采样指只记录一部分普通 Run，例如每 100 次保留 1 次；错误或高风险 Run 可以保留更多结构化信息，但这不等于放宽原文捕获规则。本章的内存列表没有替你解决这些运维问题，它只把“默认不抓全文”变成了一个可测试的起点。

---

## 4. Eval Case 先定义“正确行为”，再讨论分数

Evaluation 不是把用户问题再问一遍，而是为一个重要行为写下可重复检查的期望。一个 `EvalCase` 包含稳定 ID、问题、答案中必须出现的片段、期望的 Tool 序列，以及是否应当 abstain；一次 `AgentRun` 则是被测 Agent 实际产生的答案、Tool、检索来源和运行指标。

下面代码中的 `assert` 是 Python 的断言：条件为假时程序会报错。教学示例用它把“我们认为应当成立的结果”直接写成可运行检查。

下面的完整片段展示退款 Case 如何分别比较答案、轨迹和 abstention：

```python
from evaluation import AgentRun, EvalCase, score_case

case = EvalCase(
    id="refund-within-window",
    question="Can ORDER-42 be refunded to the original payment method?",
    expected_answer_contains=("30 days", "original payment method"),
    expected_tools=("lookup_order", "search_refund_policy"),
)
run = AgentRun(
    answer="Orders within 30 days may use the original payment method.",
    tools=("lookup_order", "search_refund_policy"),
    retrieved_ids=("refund-policy",),
    latency_ms=18,
)

score = score_case(case, run)
assert score.answer_ok
assert score.tool_trajectory_ok
assert score.abstention_ok
assert score.passed
```

`expected_tools` 在教学实现中是**有顺序且完全相等**的元组：多调、漏调、换序都会让 `tool_trajectory_ok=False`。这很适合动作路径本来就确定的退款流程。若业务允许两条都正确的路径，应为各路径分别建 Case，或在项目中写一个明确的自定义 Evaluator；不要偷偷放宽规则，让“任何路径都算对”。

`expected_answer_contains` 同样只是一个窄而稳定的确定性检查，不是对自然语言质量的完整判断。它的价值在于：当规则本来可以精确表达时，先让失败可复现、可解释。

---

## 5. 让报告同时看答案、过程、资源与检索组件

对每个 Case，`score_case()` 分别得到 `answer_ok`、`tool_trajectory_ok` 和 `abstention_ok`；三者同时为真，Case 才通过。于是“最后答案碰巧正确、但中间乱调 Tool”的 Agent 不会和正常路径得到同一分数。

[`code/evaluation.py`](code/evaluation.py) 的 `evaluate()` 再汇总为：

```python
EvalReport(
    scores=...,                       # 每个 Case 的三个独立结果
    pass_rate=...,                    # 通过 Case / 全部 Case
    unnecessary_tool_rate=...,        # 不必要 Tool 调用 / 全部 Tool 调用
    average_tool_calls=...,           # 每个 Case 的平均 Tool 数
    average_latency_ms=...,           # 每个 Case 的平均延迟
    average_estimated_cost_usd=...,   # 每个 Case 的估算成本
)
```

`unnecessary_tool_rate` 的分子是 Greeting 等“不应调用 Tool”的 Case 中的所有 Tool，以及其他 Case 超出期望数量的 Tool；分母是全部实际 Tool 调用。它不能代替轨迹评分：调用了错误 Tool 但次数恰好相同，仍会由 `tool_trajectory_ok` 失败。

不要只在端到端总分下降后猜原因。前几章已有可独立测量的组件，应分别保留其指标：

| 组件 | 可直接检查的内容 |
| --- | --- |
| Stage 02 Router | route accuracy |
| Stage 04 Retriever | Recall@K、MRR、关键来源是否被取回 |
| Stage 07 Context | 必需内容保留、无关内容比例、遗漏 |
| Stage 09 Tool / Guardrail | 参数、权限拒绝原因、Retry、Budget |
| Agent trajectory | Tool 顺序、步数、不必要动作 |
| Final answer | 正确性、证据约束、abstention |

例如 Retriever 的 `Recall@K` 只问一个明确问题：“前 K 条结果是否包含标注的相关文档？”

```python
from evaluation import recall_at_k

score = recall_at_k(["a", "b", "c"], {"b", "x"}, k=2)
assert score == 0.5
```

如果关键文档根本不在 Top-K，后面的模型回答再流畅也不能弥补这项检索失败。

`MRR`（Mean Reciprocal Rank，平均倒数排名）也衡量检索排序：相关文档排第 1 名得分为 `1`，排第 2 名得分为 `1/2`，排得越靠后得分越低；再对多个查询取平均。

本地回归检查在这里运行：

```bash
python stages/10-evaluation-observability/code/checks.py
```

---

## 6. 能确定的规则先用确定性 Evaluator

Evaluator 也需要选择。一个实用顺序是：先写能被明确判定的规则，再把真正开放的语义问题交给人工或 LLM Judge。

| 评测问题 | 优先方式 | 原因 |
| --- | --- | --- |
| 是否调用了正确 Tool、参数是否正确、是否超 Budget | 确定性规则 | 有精确答案，便宜且可重复 |
| 相关文档是否进入 Top-K | Recall@K / MRR | 有标注来源，可直接计算 |
| 证据不足时是否 abstain | Case 的布尔期望加答案边界 | 行为要求明确 |
| 开放式答案是否完整、表达是否清楚 | 人工评审或 LLM Judge | 难以写成单一字符串规则 |

LLM Judge 有用，但它也有成本、随机性和模型版本漂移。应记录 Judge 的提示、版本、温度和评分标准，并抽样与人工判断对照。不要让另一个概率模型去裁决原本可以用 `==` 或集合运算回答的问题。

Evaluator 只能观察和评分，不能在背后帮被测 Agent 调 Tool、补 Context 或修复答案。否则测到的是“Agent 加上作弊器”的组合系统。

---

## 7. Offline Eval 告诉你是否回归，Online Trace 帮你面对真实流量

固定 Dataset 在开发和 CI 中反复运行，叫 **Offline Eval**。它用于阻止已修复的 Bug 再次出现：一次真实的错误路径被修好后，应新增 Case，而不是只在 issue 里写一句“已修复”。

真实流量中的延迟、失败率、拒绝率、用户分布和成本，属于 **Online Signal**。它告诉你系统在生产中的实际状态，但不能替代受控对比，因为用户已经经历了失败。

当离线 Case 失败时，再取同一个 `run_id` 的 Trace：

```text
retrieval.search_policy [ok]  -> 找到 refund-policy
context.build [ok]            -> 没有把它放入模型上下文
model.generate [ok]           -> 回答“证据不足”
```

Eval 告诉你“退款 Case 回归了”；Trace 告诉你“问题发生在 Context 构建，而不是 Retriever 或模型”。同样，Stage 09 的 `policy.authorize`、`approval.review` 和 `tool.execute` 应放在不同 Span 中，才能区分未提议、参数无效、权限拒绝、审批拒绝和真正执行失败。

---

## 8. 真实 DeepSeek Run：记录轨迹，再对这一条运行评分

离线 Case 是稳定回归基线，但真实模型仍需被观察。[`code/deepseek_observability.py`](code/deepseek_observability.py) 提供了一个完整的 DeepSeek Tool Calling 示例：模型提出 `lookup_order` 和 `search_refund_policy`；Host 运行本地教学 Tool 并返回 Tool Result；Tracer 记录 `agent.run`、`model.generate` 和每个 `tool.*` Span；最后将实际答案和 Tool 序列转成 `AgentRun`，交给同一个 `score_case()`。

流程是：

```text
user task
    ↓
DeepSeek model.generate
    ↓ tool call
Host local Tool + tool.* span
    ↓ tool result
DeepSeek model.generate
    ↓
AgentRun + Trace + deterministic score
```

Tool Calling 的消息顺序可参考 [DeepSeek Tool Calls 官方指南](https://api-docs.deepseek.com/guides/tool_calls/)。示例中的订单和退款政策都在本地函数中，不会访问支付系统，也不会产生真实退款。

安装依赖：

```bash
python -m pip install -r stages/10-evaluation-observability/code/requirements.txt
```

Windows 命令提示符（CMD）：

```bat
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/10-evaluation-observability/code/deepseek_observability.py
```

PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/10-evaluation-observability/code/deepseek_observability.py
```

这次 live run 的分数用于检查当前模型的实际轨迹，并不应该直接充当 CI 的唯一 Gate：模型版本、服务状态和随机性都可能变化。把它当作“Trace 是否完整、Host 是否正确收集轨迹”的集成检查；长期回归判断仍以固定 Dataset、固定 Runner 和确定性 Case 为主。

---

## 9. 从教学代码走向生产：保留边界，替换存储与导出

本章的 `Trace` 是内存中的 Python 数据类，方便看清概念。生产环境通常需要把 Span 导出到 OpenTelemetry 兼容的 Collector 或观测平台：**exporter** 负责从应用发送 Span，**collector** 负责接收、处理并转发这些数据。随后可按 `run_id`、服务版本、模型版本、Tool 名称、错误类别和延迟查询。

替换实现时，前面的边界不应丢失：

```text
保留：明确 Span 边界、父子关系、默认最小化、错误不改变业务语义
替换：内存 Trace → SDK / exporter / collector / 查询界面
补充：访问控制、保留期限、采样、脱敏、成本与版本标签
```

不要为了遥测而记录所有 Prompt 和 Tool Result，也不要为了让仪表盘好看而吞掉业务异常。可观测性服务于系统质量，不能成为新的数据泄露面或行为改变点。

---

## 10. 现在才可以严肃讨论 Multi-Agent

到这里，我们既能观察一个 Agent 的路径，也能用数据集比较答案、轨迹、延迟、成本和拒绝行为。现在才有资格问：把一个 Agent 拆成多个 Agent，真的带来了收益，还是只增加了 Context 传递、调用次数和延迟？

Stage 11 会从这个问题开始，讨论 Delegation、Handoff、Context Projection 和有边界的团队执行：

> **什么时候确实需要第二个 Agent？**

这就是 [Stage 11：Multi-Agent Systems](../11-multi-agent/README.zh-CN.md)。
