# Provider Adapter 练习

这些练习的目标是把 provider / runtime boundary 真正做实。不要通过“把 provider-specific logic 搬进 `AgentRuntime`”来完成它们。

## Exercise 1 — 手动追踪 Protocol

给定 Tiny-Agent message history：

```python
[
    {"role": "user", "content": "What is 9 * 8?"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_9x8",
                "name": "multiply",
                "arguments": {"a": 9, "b": 8},
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_9x8",
        "name": "multiply",
        "content": "72",
    },
]
```

手工写出等价 Responses API input items。

然后回答：

1. 哪个 field 把 Tool result 与原始 model request 关联起来？
2. 为什么仅靠 Tool name 不足以 correlation？
3. 为什么 provider 侧 arguments 用 JSON 编码，而 Tiny-Agent 内部存 Python dict？

---

## Exercise 2 — 增加 `subtract` Tool

在 `code/openai_multi_tool_agent.py` 中增加：

```python
def subtract(a: float, b: float) -> float:
    ...
```

测试：

```text
Calculate (80 - 17) * 3 + 5.
```

运行前先预测一个合法 Tool trajectory，再与实际结果比较。

思考：

- model 是否选择了与你相同的 grouping？
- trajectory 不同但 final answer 是否仍然正确？
- 哪些步骤 deterministic，哪些属于 model decision？

---

## Exercise 3 — 故意破坏 Strict Schema

从某一个 Tool schema 删除：

```python
"additionalProperties": False
```

同时保持：

```python
strict_tools=True
```

观察 provider behavior，然后恢复 strict-compatible schema。

解释：为什么 schema correctness 属于 Agent reliability？

---

## Exercise 4 — Fake Provider 返回 Invalid JSON

在 `tests/test_openai_adapter.py` 增加一个 fake response，其 arguments 是：

```text
{a: 1, b: 2}
```

而不是合法 JSON：

```json
{"a": 1, "b": 2}
```

验证 adapter 在 runtime 尝试 Tool execution **之前**就 raise error。

解释为什么这个 error 属于 provider / protocol boundary，而不是 Tool handler。

---

## Exercise 5 — JSON 合法，但 Shape 错误

构造 fake provider call，decoded arguments 是：

```json
[1, 2]
```

JSON 语法合法，但 Function arguments 应该是 object。

验证 Tiny-Agent 会拒绝它。

这个练习展示：

```text
valid JSON
```

与：

```text
valid function-call arguments
```

不是一回事。

---

## Exercise 6 — Multiple Independent ToolCalls

创建两个 read-only Tool：

```text
get_city_temperature(city)
get_city_population(city)
```

提出一个可能同时需要两者的问题，观察 model 是否在同一 turn 发出 multiple calls。

然后设置：

```python
parallel_tool_calls=False
```

比较 trajectory。

最重要的问题：

> `parallel_tool_calls=True` 是否表示 Tiny-Agent 当前会并发执行 Python handler？

答案：**不是。**

它只允许 model 在一次 decision 中请求多个 ToolCall；当前 runtime 仍然同步循环执行 handler。

physical parallel execution 属于另一层 runtime concern。

---

## Exercise 7 — Serial Dependency

用 arithmetic Tool 完成：

```text
Calculate (23 * 17) + 41.
```

解释为什么 `add` 必须依赖 `multiply` 的 observation。

再与：

```text
Find the temperatures of Tokyo and Paris.
```

比较，分别画出 dependency graph。

---

## Exercise 8 — Provider Substitution 思考实验

假设增加：

```python
class QwenModel:
    ...
```

列出理想情况下需要修改的 files。

一个好的 architecture 应该允许新增 provider adapter + tests，而不修改以下 core semantics：

```text
AgentRuntime
ToolRegistry
Tool handlers
```

如果你认为 runtime 必须修改，请明确指出：到底缺少了哪一个 **provider-independent capability**。

---

# 面试题

1. Agent runtime 与 model provider adapter 有什么区别？
2. 为什么 Tiny-Agent 要把 provider output normalize 成 `ModelResponse`？
3. `call_id` 解决什么问题？
4. 为什么 `generate()` 表示一个 model turn，而不是完整 Agent run？
5. strict function calling 约束什么？
6. malformed JSON 与 semantically invalid Tool arguments 有什么区别？
7. 为什么一个 model turn 可以包含多个 ToolCall？
8. 为什么 multiple ToolCall 不等于 concurrent Tool execution？
9. 为什么 unit test 使用 fake OpenAI client？
10. live integration test 应测试哪些 unit test 无法证明的事情？
11. provider-neutral transcript 有什么价值？
12. provider-native reasoning / session state 变重要后，会暴露哪些当前 adapter limitation？

# Completion Challenge

构建一个三 Tool calculator：

```text
add
multiply
subtract
```

至少展示三种 trajectory：

1. direct one-Tool task；
2. serial two-or-more-Tool task；
3. model 正确判断不需要 Tool 的 task。

每次 run 记录：

```text
user input
model action(s)
Tool arguments
observation(s)
final answer
step count
```

不要只看 final answer。**同时检查 trajectory。**