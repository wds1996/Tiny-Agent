# Provider Adapter 专项练习：把“换模型不改 Runtime”真正练会

> Language: [English](provider-adapter-exercises.md) | 简体中文

这一组练习只盯住一件事：

> **Provider-specific protocol 应该停在 Adapter 边界，不能渗进 `AgentRuntime`。**

如果你完成练习时不得不修改 `AgentRuntime.run()`，先不要急着继续写。问自己：

> “我是在补一个真正 provider-neutral 的 Runtime capability，还是只是让 Runtime 知道某家 provider 的细节？”

---

## Exercise 1 — 手工做一次 protocol translation

Tiny-Agent transcript：

```python
[
    {"role": "user", "content": "查询东京课程模拟天气"},
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_weather",
                "name": "get_mock_weather",
                "arguments": {"city": "Tokyo"},
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "call_weather",
        "name": "get_mock_weather",
        "content": "18.0",
    },
]
```

请手工写出对应的 Responses API input items。

然后回答：

1. 哪个字段负责把 Tool result 与原始 function call 对应起来？
2. 为什么 Tool name 不能代替 `call_id`？
3. 为什么 Tiny-Agent 内部存 `dict`，而 provider wire format 中 arguments 可能是 JSON string？
4. 如果未来 provider 的 ToolCall 字段完全不同，哪一层应该变化？

---

## Exercise 2 — 自己实现 `_extract_tool_calls`

不要看 `src/tiny_agent/models/openai.py`。

给定一个 fake provider response，其中：

```text
response.output
```

可能同时包含：

```text
message
function_call
reasoning item
function_call
```

实现：

```python
def extract_tool_calls(response) -> list[ToolCall]:
    ...
```

要求：

- 只提取 `function_call`；
- `arguments` 必须 `json.loads`；
- JSON 解析失败明确报 protocol error；
- JSON 解码后不是 `dict` 也必须拒绝；
- 保留 `call_id`；
- 同一轮多个 call 全部提取。

写至少四个 deterministic tests。

---

## Exercise 3 — 故意制造 malformed JSON

Fake provider 返回：

```text
{city: Tokyo}
```

而不是：

```json
{"city": "Tokyo"}
```

验证：

```text
Adapter 失败
Runtime 不执行 Tool
handler 从未被调用
```

然后解释为什么这属于：

```text
provider/protocol boundary
```

而不是 Tool handler failure。

---

## Exercise 4 — JSON 合法，但 shape 错了

Fake provider 返回：

```json
["Tokyo"]
```

`json.loads` 会成功。

但 function arguments 应该是 object。

验证 Adapter 仍然拒绝。

这个练习专门让你区分：

```text
syntactically valid JSON
!=
valid normalized ToolCall arguments
```

---

## Exercise 5 — 证明 `generate()` 只做一个 model turn

写一个 FakeClient，并记录：

```text
client.responses.create
```

被调用多少次。

执行一次：

```python
model.generate(messages, tools)
```

断言只发生一次 provider request。

然后让 provider response 返回 ToolCall。

确认：

```text
Adapter 没有执行 Tool
Adapter 没有再次调用 provider
Adapter 只是返回 ModelResponse(tool_calls=[...])
```

最后回答：

> 如果 Adapter 偷偷跑完整 loop，permission / tracing / checkpoint 为什么会变难？

---

## Exercise 6 — Tool schema translation

给定 Tiny-Agent Tool：

```python
{
    "name": "get_mock_weather",
    "description": "Return course mock weather for one city.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
        },
        "required": ["city"],
        "additionalProperties": False,
    },
}
```

手工写成 OpenAI function Tool definition。

然后故意删除：

```python
"additionalProperties": False
```

讨论：

1. provider-side strict schema 带来什么价值？
2. 为什么 Runtime 以后仍应该做 local validation？
3. schema correctness 属于 Tool design、Adapter 还是 Runtime validation？为什么这三个层次不能混为一谈？

---

## Exercise 7 — 把 OpenAI 换成 Qwen，但不改 Runtime

Stage 00 已经演示过 Qwen 的 OpenAI-compatible 调用。

现在重新做一次，但要求更严格：

```text
AgentRuntime
ToolRegistry
Tool handlers
```

全部不允许修改。

你只能新增或配置：

```text
Qwen Adapter
provider config
provider-specific tests
```

目标接口仍然是：

```python
class Model(Protocol):
    def generate(
        self,
        messages,
        tools,
    ) -> ModelResponse:
        ...
```

完成后写一段说明：

```text
哪些 provider 差异被 Adapter 吸收？
哪些能力确实应该提升成 Runtime 的通用 capability？
```

如果你发现自己写：

```python
if provider == "qwen":
```

到 `AgentRuntime.run()` 里，请解释为什么。

---

## Exercise 8 — Provider compatibility 不是 provider identity

假设 OpenAI 和 Qwen 都能通过类似：

```python
client.responses.create(...)
```

调用。

列出至少八种它们仍可能不同的地方，例如：

```text
API Key
base_url
model IDs
supported parameters
Tool Calling details
Structured Output support
error semantics
rate limits
usage metadata
provider extensions
```

然后回答：

> 为什么“OpenAI-compatible”降低 Adapter 实现成本，却没有让 Adapter 这个 architecture layer 失去意义？

---

## Exercise 9 — Serial dependency vs same-turn multiple calls

场景 A：

```text
get_mock_weather(Tokyo)
        ↓
      18°C
        ↓
celsius_to_fahrenheit(18)
```

场景 B：

```text
get_mock_weather(Tokyo)
get_mock_weather(Paris)
```

画出 dependency graph。

回答：

1. 为什么 A 通常需要多个 model turns？
2. 为什么 B 可能一轮返回两个 ToolCall？
3. `parallel_tool_calls=True` 到底允许了什么？
4. 为什么它没有自动让 Python Tool 并发执行？

---

## Exercise 10 — FakeClient unit test vs live integration test

设计两套测试。

### Unit test

使用 FakeClient 验证：

```text
request translation
Tool schema translation
JSON decoding
call_id preservation
multiple calls
invalid role
empty provider response
```

### Live integration

使用真实模型验证：

```text
真实 provider 接口仍兼容
模型会合理选择 Tool
真实 trajectory 能完成任务
延迟 / usage 在合理范围
```

然后解释：

> 为什么这两类 test 谁都不能代替谁？

---

## Completion Challenge — 写一个真正 provider-neutral 的双 Provider Demo

目标：

```text
同一个 AgentRuntime
同一个 ToolRegistry
同一组 travel Tools
```

只通过配置切换：

```text
OpenAI
Qwen
```

要求最终都能处理：

```text
查询课程模拟东京天气
→ 得到 Celsius
→ 使用转换 Tool 得到 Fahrenheit
→ 最终解释
```

记录两次 trajectory，并比较：

```text
Tool selection
arguments
step count
final answer
provider latency
```

最后写一段架构总结：

> **哪些变化属于 provider substitution，哪些变化才应该推动 core Runtime contract 演化？**

如果你能把这个问题答清楚，就真正理解了 Adapter，而不只是会写一个包装类。