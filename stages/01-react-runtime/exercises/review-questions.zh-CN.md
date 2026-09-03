# Stage 01 复习题与练习

## 概念复习

1. repeated Function Calling 在什么条件下变成 Agent loop？
2. action 与 observation 有什么区别？
3. 为什么 `AgentRuntime` 应该依赖 provider-neutral `Model` interface？
4. 为什么要把 provider response normalize 成 internal `ToolCall` / `ModelResponse`？
5. `ToolRegistry` 在保护 runtime 避免什么问题？
6. 为什么 model-generated ToolCall 应该视为 proposal，而不是 unconditional command？
7. 为什么 Agent 必须有 stopping condition？
8. `max_steps` 可以防什么？又不能防什么？
9. 哪些情况下把 Tool exception 转成 observation 是合理的？
10. 为什么 deterministic unit test 应使用 fake / scripted model？
11. unit test 与 real-model evaluation 有什么区别？
12. 为什么实现 ReAct 不需要暴露完整 hidden chain-of-thought？

## Coding Exercise 1 — Real Model Adapter

实现一个 provider adapter，满足：

```python
class Model(Protocol):
    def generate(
        self,
        messages,
        tools,
    ) -> ModelResponse:
        ...
```

要求：

- provider-specific SDK object 必须留在 adapter 内；
- ToolCall 必须转换成 Tiny-Agent `ToolCall`；
- plain final text 转成 `ModelResponse(final_answer=...)`；
- **不能修改 `AgentRuntime`**。

测试：

```text
Calculate (23 * 17) + 41 and explain the result.
```

使用：

```text
multiply(a, b)
add(a, b)
```

Tool sequence 应由 model 自己决定。

## Coding Exercise 2 — 从 Invalid ToolCall 恢复

构造 fake model：

```text
turn 1 -> add(a="bad", b=2)
turn 2 -> 看到 ToolError 后 add(a=3, b=2)
turn 3 -> final answer
```

验证 runtime 不会因为第一轮 recoverable Tool error 直接 crash。

然后思考：如果这是 permission error 或 internal secret-bearing exception，还应该用同样方式交给 model 吗？Stage 07 会正式回答这个问题。

## Coding Exercise 3 — Step-Limit Failure

构造一个 fake model，每一轮都请求同一个 Tool。

预期：

```text
Agent exceeded max_steps=...
```

回答：

- 为什么这比 unlimited loop 更合理？
- production 还需要哪些 additional limit？

至少应想到：

```text
timeout
Tool-call budget
retry budget
token / cost budget
cancellation
loop detection
```

## Coding Exercise 4 — One Model Turn 中 Multiple Calls

让一个 `ModelResponse` 返回两个 independent ToolCall，验证：

- 两个 Tool 都执行；
- 两个 observation 都正确 append；
- `call_id` 不混淆。

再思考下一阶段问题：

> independent calls 应该 sequential 还是 concurrent execution？

注意：model 在一个 turn 返回多个 call，只定义了**决策形态**；physical concurrency 仍然需要 runtime 另外实现。

## 面试题

1. 从 model output 到下一次 model input，完整解释一个 ToolCall lifecycle。
2. 如果公司从一个 LLM provider 切换到另一个，理想情况下哪些 code 应该变化？
3. 如何防止 Agent 进入 infinite loop？
4. 为什么把 every exception 原样返回给 model 可能不安全或不正确？
5. 什么情况下你会选择 deterministic workflow，而不是 ReAct？
6. 在称这个 runtime 为 production-ready 之前，还缺哪些 capability？

## 最终自检

你应该能不看代码解释：

```text
ReAct
    = decide -> act -> observe -> decide again

AgentRuntime
    = owns loop / execution / stopping

Provider Adapter
    = translates one model turn

ToolRegistry
    = registered execution boundary

call_id
    = request / observation correlation

multiple ToolCalls
    != concurrent handler execution

teaching simplification
    != production guarantee
```

如果这些边界已经清楚，再进入 Stage 02。