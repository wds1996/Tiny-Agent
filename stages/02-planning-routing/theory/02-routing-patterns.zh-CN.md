# 02 — Routing Pattern：把一个 Semantic Decision 放在 Explicit Code 前面

Routing 是 fixed workflow 与 fully autonomous Agent 之间最实用的 pattern 之一。

Router 只回答一个窄问题：

> **这个 request 应该交给哪个预定义 path 处理？**

它不应该悄悄变成一个可以发明 arbitrary destination 并执行它们的 unconstrained Agent。

---

## 1. 基础模式

```text
                         +--> Route A -> handler A
Request -> Router -------+--> Route B -> handler B
                         +--> Route C -> handler C
```

有两种 responsibility：

### Router

选择一个 route。

### Application Dispatcher

把 route 映射到 allowed handler。

Tiny-Agent 保持分离：

```python
decision = router.route(request)
handler = handlers[decision.route]
output = handler(request)
```

LLM 可以帮忙做 semantic classification，但 Python 仍然拥有 allowlist / dispatch。

---

## 2. Routing 为什么有价值

没有 Routing 时，一个 giant prompt 可能同时处理：

```text
billing
refunds
technical errors
account recovery
general questions
enterprise sales
...
```

这会产生 competing instructions 和过大的 action space。

Routing 可以把问题收窄：

```text
request
   |
   v
router
   |
   +--> billing specialist
   +--> technical specialist
   +--> general specialist
```

每个 downstream component 都能拥有：

- 更小 prompt；
- 更少 Tool；
- 更窄 permission；
- 更简单 evaluation criteria。

所以 Routing 同时是 accuracy benefit 与 governance benefit。

---

## 3. 第一选择：Deterministic Routing

如果 code 已经能可靠识别 route，就直接用 code。

```python
if event.type == "payment_failed":
    return "billing"

if error_code in KNOWN_TECHNICAL_CODES:
    return "technical"
```

不要让 LLM 重新发现 request 中已经明确存在的 field。

### 适合 Deterministic 的 Signal

- API event type；
- HTTP status；
- database enum；
- authenticated user tier；
- product SKU；
- known command prefix；
- exact form selection；
- regulated business rule。

糟糕理由：

```text
"event_type 明明已经是 REFUND，
但我们再问 LLM 看它像不像 refund。"
```

只增加 cost / uncertainty，没有增加 information。

---

## 4. 什么时候 LLM Router 有价值

当 route 依赖 unstructured language 中的 meaning：

```text
"I was charged twice and I can't figure out why."
-> billing
```

```text
"The desktop client closes immediately after I sign in."
-> technical
```

稳定 keyword 可能覆盖不了所有 paraphrase，这时 model 做 semantic classification 才有价值。

---

## 5. 不要解析 Free-Form Routing Prose

弱设计：

```text
LLM:
"This seems mostly technical,
although billing could also be relevant."
```

然后 Python 从 prose 猜 route。

更好的 contract：

```json
{
  "route": "technical",
  "reason": "The user describes a client crash after authentication."
}
```

schema：

```json
{
  "type": "object",
  "properties": {
    "route": {
      "type": "string",
      "enum": ["billing", "technical", "general"]
    },
    "reason": {"type": "string"}
  },
  "required": ["route", "reason"],
  "additionalProperties": false
}
```

control flow 应该是 data，而不是 prose parsing。

---

## 6. 为什么 Enum 重要

如果 application 只支持：

```text
billing
technical
general
```

model 就不能返回：

```text
route = "run_shell_as_admin"
```

allowed route set 属于 application policy。

正确结构：

```text
Model semantic judgment
          |
          v
allowed enum value
          |
          v
application-owned dispatch
```

而不是：

```text
model-generated string
          |
          v
arbitrary dynamic execution
```

---

## 7. Route Description 是 Interface 的一部分

只给：

```text
route_a
route_b
route_c
```

model 很难可靠理解边界。

更清楚：

```text
billing:
refunds, invoices, duplicate charges, payment failures

technical:
bugs, crashes, error messages, product malfunction

general:
ordinary product information and questions
```

它和 Tool Description 是同一个原则：

> model 只有在 interface 自身可理解时，才可能稳定地做正确选择。

---

## 8. Route Overlap 是 Taxonomy / Data Design 问题

例如定义：

```text
account: any account-related question
billing: subscription and payment questions
```

那么：

```text
"How do I update the card attached to my account?"
```

天然 overlap。

改善方式：

- category 尽量 mutually exclusive；
- define precedence；
- 增加 examples；
- 更清楚拆 responsibility；
- 必要时增加 `uncertain` / `human_review` route。

不要期待换一个更强 model 自动修复一套本身自相矛盾的 taxonomy。

---

## 9. Hybrid Routing 往往更好

```text
Request
   |
   v
Deterministic checks
   |
   +-- certain match --> handler
   |
   +-- ambiguous ------> LLM Router
                            |
                            v
                          handler
```

例如：

```python
if request.event_type == "refund_requested":
    return "billing"

if request.error_code in CRASH_CODES:
    return "technical"

return llm_router.route(request.message)
```

把 cheap / reliable path 保留，把 model intelligence 用在真正有增益的地方。

---

## 10. Hierarchical Routing

大系统不一定应该一次把 80 个 route 都塞进 prompt：

```text
                  top-level router
                 /       |        \
                /        |         \
            support    sales      ops
              |
         support router
         /     |      \
    billing technical account
```

收益：

- smaller decision set；
- clearer boundary；
- lower context；
- 更容易 permission partition。

代价：

- 多 routing turn；
- early wrong branch 会影响 downstream。

是否值得，要测。

---

## 11. Task Routing != Model Routing

“Routing”常用于两个不同问题。

### Task Routing

```text
request
-> billing / technical / general workflow
```

### Model Routing

```text
easy request -> cheap model
hard request -> strong model
```

model routing 可能考虑：

- task complexity；
- latency target；
- cost budget；
- modality；
- Tool support；
- context size。

不要无意间把 task category 与 model tier 耦合。

---

## 12. Self-Reported Confidence 不是 Probability

很诱人的 schema：

```json
{
  "route": "billing",
  "confidence": 0.97
}
```

这个数字看起来很科学，但 model 生成的 `0.97` 不能自动解释成“正确率 97%”。

如果 confidence 真正影响 control flow，必须基于 labeled dataset 做 empirical calibration，例如：

- route-specific metrics；
- confusion matrix；
- held-out threshold；
- deterministic uncertainty rule；
- 高价值场景的人审。

> model 说“我有 97% 把握”，本身并不是 evaluation system。

---

## 13. Consequential Routing 应 Fail Closed

如果 route A 是 read-only，route B 能 refund，不要设计：

```text
unknown route -> most powerful handler
```

应该：

```text
unknown / invalid / unsupported route
        -> safe fallback / human review / reject
```

Router 属于 control plane，必须 predictable fail。

即使 provider schema 已经限制 route，Tiny-Agent `LLMRouter` 仍会在 application 侧再次检查 route 是否在 configured map 中。

---

## 14. Routing 可以缩小 Permission / Tool Surface

不要一个 giant Agent 拿着：

```text
refund
send email
reset password
query logs
modify infrastructure
sales CRM
...
```

可以：

```text
Router
  |
  +-> billing Agent
  |     Tools: invoice lookup, refund request
  |
  +-> technical Agent
  |     Tools: logs, diagnostics
  |
  +-> sales Agent
        Tools: CRM lookup
```

更容易 govern，也更容易让 model 正确理解 action space。

---

## 15. Routing Evaluation

Router 本质是 classifier。

准备 labeled examples：

```text
input                             expected route
"charged twice"                  billing
"app crashes after login"        technical
"what languages are supported?"  general
```

测：

- overall accuracy；
- per-route precision / recall；
- confusion pairs；
- high-impact error；
- fallback rate；
- latency；
- token cost。

不同错误的代价可能不同：

```text
billing -> general
```

可能只是回答不够好；而：

```text
general -> refund-capable flow
```

可能是 governance risk。

---

## 16. Routing Workflow vs ReAct Agent

### Routing Workflow

```text
one route decision
      |
      v
fixed downstream process
```

### ReAct Agent

```text
model repeatedly decides next action
      |
      v
observation
      |
      v
model decides again
```

如果主要 uncertainty 只存在于流程**入口**，Routing 更合适。

如果 execution 全程都持续不确定，ReAct 更合适。

---

## 17. Tiny-Agent Implementation

```python
@dataclass
class RouteDecision:
    route: str
    reason: str
```

### RuleRouter

```python
RuleRouter(
    rules=[
        ("billing", is_billing),
        ("technical", is_technical),
    ],
    fallback="general",
)
```

### LLMRouter

```python
LLMRouter(
    model=structured_model,
    routes={
        "billing": "Refund and payment problems.",
        "technical": "Bugs and failures.",
        "general": "General questions.",
    },
)
```

两者都满足：

```python
router.route(request) -> RouteDecision
```

因此切换 routing strategy 不需要修改 downstream workflow code。

---

## 面试级回答

> 我会先检查 stable deterministic rules 是否能处理 high-confidence case；语义模糊时才使用 schema-constrained LLM Router，并把 route 限制在 application-owned allowlist。Model 选择 route，application code 做 dispatch。我会用 labeled dataset 测 routing，分析 category confusion，并为 invalid / high-risk ambiguous case 设置 safe fallback，而不是把 model 自己生成的 confidence 当 calibrated probability。

---

## 自检

1. 为什么 Router 比 Agent 更窄？
2. 为什么 downstream dispatch 应保持 application code？
3. 什么情况下 RuleRouter 优于 LLMRouter？
4. 为什么 route value 必须 schema-constrained？
5. 动态执行 arbitrary model-generated route 有什么风险？
6. route definition overlap 为什么会伤害 routing？
7. generated confidence 为什么不是 calibrated probability？
8. routing 如何缩小 downstream Tool / permission surface？