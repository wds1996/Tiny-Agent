# 03 — Model Provider Adapter：把 Runtime 接到真实 LLM

Stage 01 已经有 Agent loop，但到目前为止一直由 scripted fake model 做 decision。

这一章要做的是：把**同一个 runtime** 接到真实 provider，同时不把 provider-specific logic 搬进 runtime。

核心工程思想：

> **Agent orchestration 与 model-provider protocol 是两种不同责任。**

一个干净的 Agent runtime 应该理解：

```text
ToolCall
Observation
stopping condition
execution state
```

它不应该需要理解每个 vendor 的 request object、response object、authentication rule 或 function-call wire format。

---

## 1. Adapter 位于哪里

Tiny-Agent 的依赖方向：

```text
                         provider-neutral boundary
                                  |
                                  v
User -> AgentRuntime -> Model protocol -> OpenAIResponsesModel -> OpenAI API
          |                            |
          |                            +-- request translation
          |                            +-- response parsing
          |                            +-- provider errors
          |
          +-> ToolRegistry -> Python handlers
```

`AgentRuntime` 只知道：

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelResponse:
        ...
```

它不 import OpenAI Python package。

所以未来可以是：

```text
AgentRuntime
    |
    +--> OpenAIResponsesModel
    +--> FutureAnthropicModel
    +--> FutureQwenModel
    +--> FakeModel
```

换 provider 不应该重写 Agent loop。

---

## 2. Adapter 不只是“包一下 API Call”

provider adapter 要做的是**双向 protocol translation**。

### Tiny-Agent -> Provider

把：

```text
Tiny-Agent message history
Tiny-Agent Tool schema
```

翻译成：

```text
provider input items
provider function definitions
provider configuration
```

### Provider -> Tiny-Agent

把 provider response item 翻译成：

```python
ModelResponse(
    tool_calls=[...]
)
```

或者：

```python
ModelResponse(
    final_answer="..."
)
```

完成 normalization 后，其余 component 都不需要理解 provider-specific type。

---

## 3. Responses API 的 Tool-Calling Lifecycle

本章编写时，OpenAI Responses API 的 current function-calling flow 概念上是：

```text
1. Send input + available Tool definitions
                 |
                 v
2. Model emits function_call item(s)
                 |
                 v
3. Application executes functions
                 |
                 v
4. Application sends function_call_output item(s)
                 |
                 v
5. Model decides again
```

provider function call 中对 runtime 最关键的是：

```text
call_id
name
arguments
```

例如：

```json
{
  "type": "function_call",
  "call_id": "call_123",
  "name": "multiply",
  "arguments": "{\"a\":23,\"b\":17}"
}
```

注意：`arguments` 是 **JSON-encoded string**，不是 Python dict。

adapter 需要：

```python
arguments = json.loads(item.arguments)
```

再 normalize 成：

```python
ToolCall(
    id="call_123",
    name="multiply",
    arguments={"a": 23, "b": 17},
)
```

---

## 4. 为什么 `call_id` 很重要

假设 model 同一 turn 请求两个 Tool：

```text
call_A -> get_weather(Tokyo)
call_B -> get_weather(Paris)
```

runtime 得到：

```text
Tokyo -> 31 C
Paris -> 24 C
```

provider 必须知道每个 result 对应哪个 model request。

这就是 `call_id` 的作用。

Tool result 返回时概念上：

```json
{
  "type": "function_call_output",
  "call_id": "call_A",
  "output": "31 C"
}
```

所以 `call_id` 不是装饰性 metadata，而是跨越：

```text
request
-> execution
-> observation
```

的 **correlation identifier**。

Tiny-Agent 把它保存为：

```python
ToolCall.id
```

随后写入 transcript：

```python
{
    "role": "tool",
    "tool_call_id": call.id,
    ...
}
```

adapter 再把它转换为 provider 需要的 `function_call_output`。

---

## 5. Tool Schema 是 Model Interface 的一部分

Python function：

```python
def multiply(a: float, b: float) -> float:
    return a * b
```

LLM 不会直接 inspect / invoke 这个 callable。

它看到的是 schema：

```python
{
    "name": "multiply",
    "description": "Multiply two numbers.",
    "parameters": {
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"},
        },
        "required": ["a", "b"],
        "additionalProperties": False,
    },
}
```

OpenAI adapter 再转成 provider format：

```python
{
    "type": "function",
    "name": "multiply",
    "description": "Multiply two numbers.",
    "parameters": {...},
    "strict": True,
}
```

所以 Tool design 不只是 Python programming。

model 会依据：

- Tool name；
- description；
- parameter name / description；
- schema constraint；
- surrounding instruction；

来决定选什么。

handler 完全正确但 schema 糟糕，Agent 仍然会糟糕。

---

## 6. Strict Function Schema

OpenAI 推荐 strict schema adherence。

对 strict object schema，尤其重要：

```text
additionalProperties = false
```

以及所有 property 都出现在：

```text
required
```

需要 optional 时可以使用 nullable type：

```python
{
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "units": {
            "type": ["string", "null"],
            "enum": [
                "celsius",
                "fahrenheit",
                None,
            ],
        },
    },
    "required": ["location", "units"],
    "additionalProperties": False,
}
```

Stage 01 的 `OpenAIResponsesModel` 默认启用 strict Tools。

后续还会把 schema validation 放到 Tiny-Agent 本地，使错误 schema 在 API request 发出前就 fail。

---

## 7. Adapter 只执行一个 Model Turn，不拥有 Agent Run

这是最重要的边界之一。

错误设计：

```text
AgentRuntime.run()
    |
    v
OpenAI adapter
    |
    +-> model
    +-> execute Tools
    +-> model again
    +-> execute Tools
    +-> final answer
```

如果 adapter 自己拥有整个 loop，`AgentRuntime` 就几乎失去意义。

Tiny-Agent 采用：

```text
AgentRuntime.run()
    |
    +-> model.generate()       # exactly one model decision
    |
    +-> execute Tool(s)
    |
    +-> append observation(s)
    |
    +-> model.generate()       # next decision
    |
    ...
```

因此：

```python
OpenAIResponsesModel.generate()
```

只执行一次 provider request。

后续的 retries、permission、tracing、HITL、budget、checkpoint、evaluation，都应该围绕 Agent loop，而不是藏进 provider wrapper。

---

## 8. Tiny-Agent Message 到 Responses Input Item 的映射

### User Message

Tiny-Agent：

```python
{
    "role": "user",
    "content": "Calculate 23 * 17",
}
```

Responses input：

```python
{
    "role": "user",
    "content": "Calculate 23 * 17",
}
```

### Assistant Function Call

Tiny-Agent：

```python
{
    "role": "assistant",
    "tool_calls": [
        {
            "id": "call_123",
            "name": "multiply",
            "arguments": {"a": 23, "b": 17},
        }
    ],
}
```

Responses：

```python
{
    "type": "function_call",
    "call_id": "call_123",
    "name": "multiply",
    "arguments": '{"a": 23, "b": 17}',
}
```

### Tool Observation

Tiny-Agent：

```python
{
    "role": "tool",
    "tool_call_id": "call_123",
    "name": "multiply",
    "content": "391",
}
```

Responses：

```python
{
    "type": "function_call_output",
    "call_id": "call_123",
    "output": "391",
}
```

translation 位于：

```text
src/tiny_agent/models/openai.py
```

---

## 9. Tool 之间的 Serial Dependency

考虑：

```text
(23 * 17) + 41
```

dependency：

```text
multiply(23, 17)
       |
       v
      391
       |
       v
add(391, 41)
       |
       v
      432
```

第二个 ToolCall 必须等第一个 observation 出现后才能正确构造。

自然 trajectory：

```text
Model turn 1
  -> multiply(23, 17)

Runtime
  -> 391

Model turn 2
  -> add(391, 41)

Runtime
  -> 432

Model turn 3
  -> final answer
```

这是典型 iterative Agent pattern：environment 每次 action 后都贡献新信息。

---

## 10. Multiple ToolCall 与 Physical Parallel Execution 不同

另一个问题：

```text
What is the weather in Tokyo and Paris?
```

两条 operation 相互独立：

```text
              +-> weather(Tokyo)
User question |
              +-> weather(Paris)
```

model 可能同一 turn 返回：

```python
ModelResponse(
    tool_calls=[call_a, call_b]
)
```

Stage 01 runtime 能表示它们，但目前用普通 Python loop 顺序执行 handler。

所以必须区分：

```text
multiple ToolCalls in one model decision
```

与：

```text
concurrent physical execution of Python handlers
```

前者是 model response shape；后者需要 async execution、cancellation、error aggregation 与 concurrency limit。

---

## 11. 为什么 Stage 01 默认 Reasoning Effort = `none`

现代 Responses workflow 可以跨 turn 保存 provider-native reasoning state。

对 GPT-5.6，OpenAI 推荐在手动维护 history 时保留 model output items，或者适当使用 response chaining 等 provider mechanism。

但这会一次引入很多新概念：

- provider-native response ID；
- persisted reasoning item；
- manual history replay；
- conversation state；
- concurrency / session ownership。

Stage 01 的目标更窄：

> **先把 Agent runtime / provider boundary 学清楚。**

所以 initial adapter 默认：

```python
reasoning_effort="none"
```

每轮重建 visible transcript，使 adapter 保持 stateless。

这样可以验证：

```text
adding a real provider
!= modifying AgentRuntime
```

provider-native state 放到后面的 Stateful Orchestration stage 再系统比较。

---

## 12. 为什么 Example 默认 GPT-5.6 Luna

model 是可配置的：

```python
OpenAIResponsesModel(
    model="gpt-5.6-luna"
)
```

学习仓库没必要让每次简单 arithmetic example 都跑最昂贵 model。

GPT-5.6 family 提供不同 cost/capability trade-off：Luna 偏成本敏感，Terra 是中间层，Sol 是旗舰层。

真正要学习的是：换 model 不应该要求修改：

```text
AgentRuntime
Tool
ToolRegistry
```

---

## 13. Error Boundary

### A. Provider Request Failure

例如：

```text
invalid API key
rate limit
network failure
model unavailable
```

provider SDK 抛 exception。

Stage 01 故意不隐藏，Stage 07 再讨论 retry policy。

### B. Model 返回 Malformed JSON Arguments

例如：

```text
"arguments": "not valid json"
```

adapter 无法构造合法 `ToolCall`，因此这是 protocol / adapter error。

### C. JSON 能解析，但 Shape 错误

Function argument 应是 object：

```json
{"a": 1, "b": 2}
```

而不是：

```json
[1, 2]
```

adapter 也必须检查。

### D. Tool Handler Failure

这不属于 provider adapter：

```text
AgentRuntime -> ToolRegistry -> Tool handler
```

当前 runtime 可以把这类 failure 转成 observation，让 model 尝试 recover。

所以：

```text
provider / protocol error
    -> adapter layer

execution error
    -> Tool / runtime layer
```

---

## 14. 为什么 Test 要注入 Fake Client

`OpenAIResponsesModel` 接受：

```python
client=...
```

这是 dependency injection。

production：

```python
OpenAIResponsesModel()
```

使用真实 SDK client。

unit test：

```python
OpenAIResponsesModel(
    client=FakeOpenAIClient(...)
)
```

可以 deterministic 验证：

- request translation；
- strict Tool configuration；
- JSON decoding；
- `call_id` preservation；
- multiple function calls；
- final answer normalization；

而不依赖 internet、API key、token cost 和 sampling randomness。

---

## 15. End-to-End Example

`code/openai_multi_tool_agent.py`

用户：

```text
Calculate (23 * 17) + 41 and explain the result.
```

可能 trajectory：

```text
USER
  Calculate (23 * 17) + 41

MODEL ACTION
  multiply(a=23, b=17)

OBSERVATION
  391

MODEL ACTION
  add(a=391, b=41)

OBSERVATION
  432

FINAL
  23 * 17 = 391, and 391 + 41 = 432.
```

exact wording 与 trajectory 是 model decision；runtime 不应该硬编码。

---

## 16. 哪些是 Deterministic，哪些是 Agentic？

### Deterministic Application Logic

```text
ToolRegistry lookup
JSON decoding
Python multiplication / addition
max_steps stopping
message bookkeeping
```

### Model-Driven Decision

```text
是否需要 Tool
选择哪个 Tool
arguments 是什么
是否还需要下一个 Tool
什么时候 final
```

整个 Tiny-Agent 都会反复使用这条原则：

> **正确行为已经知道时用 ordinary software control flow；真正需要 semantic judgment 时才使用 model。**

---

## 17. 面试级问题

1. 为什么 `AgentRuntime` 不应该直接 import OpenAI SDK？
2. provider adapter 到底 normalize 什么？
3. 为什么 function-call arguments 通常在 adapter 中 JSON decode？
4. `call_id` 解决什么问题？为什么必须穿过 Tool execution？
5. Tool schema 与 Python handler 有什么区别？
6. 为什么 `generate()` 只表示一个 model turn，而不是整个 Agent run？
7. serially dependent ToolCall 与 multiple independent ToolCall 有什么区别？
8. multiple function calling 是否自动意味着 Python handler 并发执行？
9. fake provider client 为什么适合 unit test？
10. 哪些 error 属于 adapter，哪些属于 Tool/runtime？
11. 为什么 introductory adapter 刻意避免复杂 persisted reasoning state？
12. 如何增加另一个 provider 而不重写 `AgentRuntime`？

---

## 18. 下一步阅读

依次读：

```text
src/tiny_agent/models/openai.py
```

然后：

```text
tests/test_openai_adapter.py
```

最后运行：

```text
stages/01-react-runtime/code/openai_multi_tool_agent.py
```

你应该能完整解释：

```text
Tiny-Agent Tool schema
       |
       v
OpenAI function definition
       |
       v
function_call
       |
       v
Tiny-Agent ToolCall
       |
       v
ToolRegistry execution
       |
       v
Tiny-Agent Tool observation
       |
       v
function_call_output
       |
       v
next model decision
```

## References

- OpenAI Function Calling guide: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI model guidance: https://developers.openai.com/api/docs/guides/latest-model
- OpenAI model catalog: https://developers.openai.com/api/docs/models
- OpenAI Python SDK: https://github.com/openai/openai-python