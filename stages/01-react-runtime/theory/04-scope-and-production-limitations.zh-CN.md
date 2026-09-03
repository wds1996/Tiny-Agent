# 04 — Stage 01 Scope 与 Production Limitations

Stage 01 故意实现一个**小而可检查的 Agent runtime**。

它的目标是把 control loop 与 provider boundary 讲清楚，而不是让学习者误以为：几十行 runtime 已经可以直接作为 production system。

高质量教程必须明确说明：一个 implementation **保证什么**，以及**不保证什么**。

## Stage 01 正确保证了什么

当前 implementation 正确展示：

- model 提议 ToolCall，但不会自己执行 Python function；
- runtime 拥有 Tool execution 与 Agent loop；
- Tool observation 会在下一次 decision 前返回给 model；
- provider-specific request / response object 被隔离在 adapter 后面；
- `call_id` 用来关联 provider Tool request 与对应 observation；
- 同一 model turn 可以表示多个 ToolCall；
- `max_steps` 防止 loop 无界执行；
- unit test 可以使用 fake model / fake provider client。

这些是后续 Stage 必须保留的 architecture principle。

## Stage 01 刻意没有解决什么

### 1. Tool Exception 目前暴露得过于直接

teaching runtime 当前可能把 handler exception 转成：

```text
ToolError[ValueError]: detailed message
```

再返回给 model。

它适合展示 recovery，但 production 不能无脑暴露 raw exception，因为 exception 可能包含：

- file path；
- internal service name；
- SQL detail；
- stack-specific information；
- sensitive value。

production runtime 通常应该：

```text
classify failure
-> expose sanitized model-facing error
-> keep detailed diagnostics in governed log / trace
```

这会在 Stage 07 系统处理。

### 2. Tool Argument 还没有做本地 Schema Validation

Tiny-Agent 当前在 provider 支持时依赖 strict function schema，然后直接：

```python
handler(**arguments)
```

runtime 还没有先根据 Tool JSON Schema 本地验证 generated argument。

production boundary 仍然应该本地 validate，以防：

- provider 差异；
- future adapter；
- manually constructed ToolCall；
- malformed test fixture；
- schema drift。

provider constraint 很有用，但不替代 application validation。

### 3. Multiple ToolCall 能一起表示，但目前顺序执行

model 可以同一 turn 返回：

```text
weather(Tokyo)
weather(Paris)
```

Stage 01 会保存两个 call，但使用普通 Python loop 执行。

所以：

```text
multiple ToolCalls in one model turn
```

**不等于**：

```text
concurrent physical execution
```

真正 concurrency 还需要：

- async / task execution layer；
- cancellation semantics；
- error aggregation；
- concurrency limits。

### 4. OpenAI Adapter 刻意保持 Stateless

`OpenAIResponsesModel` 每次根据 Tiny-Agent visible transcript 重建 provider request。

Stage 01 默认：

```python
reasoning_effort="none"
```

这一阶段尚不讲：

- `previous_response_id`；
- provider-native conversation state；
- persisted reasoning context；
- checkpoint / resume；
- session ownership。

它们属于 Stage 03 / Stage 06 的 stateful orchestration 主题。

### 5. Mixed Text + ToolCall Output 被简化

provider response 可能同时包含多种 output item。

当前 normalized contract 刻意简化成：

```text
ModelResponse
= ToolCalls OR final answer
```

如果 provider turn 中含 function call，`OpenAIResponsesModel` 优先保留 function call，不保留同一 response 中 incidental / intermediate text。

对教学 runtime 这是可接受 simplification；更完整 production transcript 可能需要显式建模多个 output-item type。

### 6. 目前只有 Step Budget

`max_steps` 能阻止最简单的无限 loop，但 production 通常还需要：

- wall-clock timeout；
- maximum Tool calls；
- retry budget；
- token / cost budget；
- per-Tool quota；
- loop / repetition detection；
- cancellation。

### 7. 还没有 Permission / Approval Layer

当前只要 Tool 已注册，model 提议后就可以执行。

真实应用往往需要区分：

```text
read-only Tool
    -> automatic

low-risk write
    -> policy dependent

high-impact side effect
    -> human approval

forbidden capability
    -> blocked
```

当 Tool 可以发消息、改文件、写数据库、花钱或执行代码时，这一层是必需的。

### 8. 还没有 Tracing / Evaluation

当前 message transcript 适合教学 inspection，但不是完整 observability system。

后续会加入：

- spans / traces；
- latency / token usage；
- Tool success / failure metrics；
- trajectory evaluation；
- task-success evaluation；
- regression datasets。

## 为什么不在第一阶段一次性修完？

教程有两种相反的失败方式。

### 失败 1：工程太少

```text
10-line demo
-> 被包装成 production-ready Agent
```

这是误导。

### 失败 2：工程太多、太早

第一条 loop 就同时混入：

```text
retry
async
persistence
security
observability
```

初学者反而看不见核心机制。

Tiny-Agent 选择 progressive disclosure：

```text
Stage 00  Tool use
   ↓
Stage 01  explicit Agent runtime
   ↓
Stage 02  workflow / routing / planning
   ↓
Stage 03+ state, persistence, reliability, evaluation, production
```

early code 不需要 feature-complete，但每一个 simplification 都应该：

> **被明确写出来、命名，并在后续 Stage 中真正补齐。**

## Review Checkpoint

离开 Stage 01 前，你应该能回答：

1. 哪些是 Stage 01 应保留的 architecture principle，哪些只是 teaching simplification？
2. 为什么 raw exception text 直接返回 model 有风险？
3. 为什么 provider-side strict schema 不能替代 runtime validation？
4. 为什么同一 turn 有多个 ToolCall 不代表 concurrent execution？
5. 为什么 production Agent 需要比 `max_steps` 更多的 stopping control？