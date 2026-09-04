# 03 — Provider Adapter：让 Agent Runtime 不绑定某一家模型

> Language: [English](03-model-provider-adapter.md) | 简体中文

上一章我们已经得到一个很小的 Runtime contract：

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelResponse:
        ...
```

这句话看起来普通，但它其实规定了一个非常重要的 architecture boundary：

> **Agent Runtime 只认识 Tiny-Agent 自己的语义，不认识 OpenAI、Qwen 或其它 provider 的原生 Response object。**

Stage 00 已经解释过“为什么 provider-specific client 和 Runtime 应该分开”。

这一章不再停留在概念上，而是把 OpenAI Responses API 真正接进来，逐步看清 Adapter 到底翻译了什么。

---

## 1. 先看最终依赖方向

```text
User
  ↓
AgentRuntime
  ↓
Model Protocol
  ↓
OpenAIResponsesModel
  ↓
OpenAI Responses API
```

另一边：

```text
AgentRuntime
  ↓
ToolRegistry
  ↓
Python Tool
```

所以 `OpenAIResponsesModel` 的位置非常明确：

```text
provider-specific 世界
        │
        ▼
      Adapter
        │
        ▼
Tiny-Agent internal protocol
```

它不应该：

```text
执行 Tool
控制 Agent loop
决定 max_steps
做权限审批
偷偷再调用模型第二次
```

它只负责：

```text
把 Tiny-Agent request 翻译给 provider
把 provider response 翻译回 Tiny-Agent
```

---

## 2. 为什么 Adapter 不只是“包一层 API 调用”？

如果 Adapter 只是：

```python
def generate(prompt):
    return client.responses.create(...)
```

那 Runtime 最后还是要解析 provider Response。

真正的 Adapter 需要完成双向协议转换。

### Tiny-Agent -> OpenAI

Runtime 传入：

```text
messages
Tool schemas
```

Adapter 需要转换成：

```text
Responses input items
function tool definitions
provider configuration
```

### OpenAI -> Tiny-Agent

OpenAI 返回：

```text
message
function_call
reasoning item
...
```

Adapter 只把 Runtime 需要的语义归一化成：

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

所以 Adapter 本质上是：

> **协议翻译器 + normalization boundary。**

---

## 3. `generate()` 为什么只能做“一轮模型决策”？

先看错误设计：

```text
AgentRuntime.run()
      ↓
OpenAIAdapter.generate()
      ↓
模型
      ↓
执行 Tool
      ↓
模型
      ↓
再执行 Tool
      ↓
最终回答
```

如果 Adapter 把整个循环都做完，`AgentRuntime` 其实已经被架空了。

更严重的是，后面想加：

```text
permission
approval
retry
tracing
budget
checkpoint
```

时，你会发现真正的 loop 藏在 provider adapter 内部，所有治理逻辑都很难插进去。

所以 Tiny-Agent 的规则是：

```python
response = self.model.generate(...)
```

代表：

> **只执行一次 model turn。**

然后控制权必须回到 Runtime。

完整循环是：

```text
Runtime
  ↓
model.generate()      # 只一轮
  ↓
ModelResponse
  ↓
Runtime 执行 Tool
  ↓
Observation
  ↓
Runtime
  ↓
model.generate()      # 下一轮
```

这个边界非常重要。

---

## 4. OpenAI Tool Calling 的一轮到底返回什么？

当前 Responses API 中，一个 function call item 的关键字段是：

```text
call_id
name
arguments
```

概念上类似：

```json
{
  "type": "function_call",
  "call_id": "call_weather",
  "name": "get_mock_weather",
  "arguments": "{\"city\": \"Tokyo\"}"
}
```

注意一个细节：

```text
arguments
```

通常是 JSON 字符串，而 Tiny-Agent Runtime 希望得到 Python `dict`。

所以 Adapter 做：

```python
arguments = json.loads(item.arguments)
```

然后归一化成：

```python
ToolCall(
    id=item.call_id,
    name=item.name,
    arguments=arguments,
)
```

从这一刻开始，Runtime 不再需要知道：

```text
item.type
item.arguments 是 string
OpenAI Response.output
```

provider detail 到这里应该结束。

---

## 5. 为什么 `call_id` 必须穿过整个 Tool execution？

这是 Provider Adapter 最容易被初学者忽略、但非常关键的一点。

假设模型同一轮提出：

```text
call_A -> get_mock_weather(Tokyo)
call_B -> get_mock_weather(Paris)
```

Runtime 执行后得到：

```text
Tokyo -> 18°C
Paris -> 22°C
```

下一轮模型必须知道：

```text
18°C 属于 call_A
22°C 属于 call_B
```

所以 observation 不能只写：

```text
18°C
22°C
```

而要带 correlation ID：

```json
{
  "type": "function_call_output",
  "call_id": "call_A",
  "output": "18"
}
```

Tiny-Agent 内部用：

```python
ToolCall.id
```

保存它。

完整路径是：

```text
provider function_call
      │ call_id = X
      ▼
Tiny-Agent ToolCall.id
      │
      ▼
Runtime executes Tool
      │
      ▼
Tool observation
      │ tool_call_id = X
      ▼
Adapter
      │
      ▼
provider function_call_output(call_id=X)
```

如果中间把 ID 丢掉，多 ToolCall 场景很快就会错乱。

---

## 6. Tool schema 怎样从 Tiny-Agent 变成 provider function definition？

Tiny-Agent 内部 Tool schema：

```python
{
    "name": "get_mock_weather",
    "description": "Return course mock weather for a city.",
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

OpenAI Responses API 需要 function Tool definition：

```python
{
    "type": "function",
    "name": "get_mock_weather",
    "description": "Return course mock weather for a city.",
    "parameters": {...},
    "strict": True,
}
```

所以 Adapter 里会有：

```python
def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
        "strict": True,
    }
```

这说明 Tool schema 有两层意义：

```text
Tiny-Agent 内部 capability contract
            ↓
Provider-specific wire format
```

不要把 provider 格式直接当成 Runtime 的永久内部数据结构。

---

## 7. messages 怎样翻译成 Responses input items？

Tiny-Agent 当前用一个简单 transcript：

### 用户消息

```python
{
    "role": "user",
    "content": "查询东京课程模拟天气"
}
```

OpenAI 可以直接接收类似结构。

### Assistant ToolCall

Tiny-Agent：

```python
{
    "role": "assistant",
    "tool_calls": [
        {
            "id": "call_weather",
            "name": "get_mock_weather",
            "arguments": {"city": "Tokyo"},
        }
    ],
}
```

Adapter 转成：

```python
{
    "type": "function_call",
    "call_id": "call_weather",
    "name": "get_mock_weather",
    "arguments": '{"city": "Tokyo"}',
}
```

### Tool observation

Tiny-Agent：

```python
{
    "role": "tool",
    "tool_call_id": "call_weather",
    "name": "get_mock_weather",
    "content": "18.0",
}
```

Adapter 转成：

```python
{
    "type": "function_call_output",
    "call_id": "call_weather",
    "output": "18.0",
}
```

这就是为什么前一章反复强调：

> **Action 和 Observation 的结构信息必须保留下来。**

否则 Adapter 下一轮无法正确重建 provider protocol。

---

## 8. 真正的 `OpenAIResponsesModel.generate()` 在做什么？

把 `src/tiny_agent/models/openai.py` 简化后，核心大致是：

```python
response = self.client.responses.create(
    model=self.model,
    input=self._to_openai_input(messages),
    tools=[self._to_openai_tool(tool) for tool in tools],
    reasoning={"effort": self.reasoning_effort},
    parallel_tool_calls=self.parallel_tool_calls,
)

tool_calls = self._extract_tool_calls(response)

if tool_calls:
    return ModelResponse(tool_calls=tool_calls)

if response.output_text:
    return ModelResponse(
        final_answer=response.output_text
    )

raise RuntimeError(
    "provider returned neither ToolCall nor final text"
)
```

你可以把它拆成三步：

```text
1. Tiny-Agent -> provider request
2. provider inference
3. provider response -> Tiny-Agent ModelResponse
```

注意，它没有任何：

```text
while True
Tool execution
max_steps
permission
```

这正说明职责分离成功了。

---

## 9. 为什么 Provider Adapter 也要做 protocol validation？

假设 provider 返回：

```text
arguments = "{city: Tokyo}"
```

这不是合法 JSON。

Adapter 应该在构造 `ToolCall` 之前失败：

```python
try:
    arguments = json.loads(raw_arguments)
except json.JSONDecodeError as exc:
    raise RuntimeError("invalid provider tool arguments") from exc
```

再假设 JSON 是合法的：

```json
["Tokyo"]
```

但 function arguments 应该是 object。

所以还要检查：

```python
if not isinstance(arguments, dict):
    raise RuntimeError(
        "Function-call arguments must decode to an object"
    )
```

这里有一条很好的责任判断规则：

```text
provider wire format 错了
    -> Adapter boundary

Tool 参数语义不合法
    -> Runtime / Tool validation boundary

Tool handler 自己执行失败
    -> Tool execution boundary
```

错误发生在哪一层，就尽量在哪一层被识别。

---

## 10. 同一轮多个 ToolCall 和串行依赖有什么区别？

### 串行依赖

旅行助手：

```text
get_mock_weather(Tokyo)
        ↓
      18°C
        ↓
celsius_to_fahrenheit(18)
```

第二个 call 的参数必须等第一个 observation。

因此至少需要两个 model turns。

### 独立调用

如果用户问：

```text
查询东京和巴黎的天气
```

模型可能一次返回：

```text
call_A -> get_weather(Tokyo)
call_B -> get_weather(Paris)
```

这是：

```text
multiple ToolCalls in one model turn
```

当前 Runtime 仍会：

```python
for call in response.tool_calls:
    execute(call)
```

顺序执行。

所以 `parallel_tool_calls=True` 只影响模型是否可以在一个决策里提出多个 call，**不等于 Python handler 已经并发运行**。

这是后面 async / production 部分必须继续处理的边界。

---

## 11. 接入真实 OpenAI 后，旅行助手代码应该有多简单？

Stage 01 的真实 example 会做到：

```python
model = OpenAIResponsesModel(
    model="gpt-5.6-luna",
    reasoning_effort="none",
)

runtime = AgentRuntime(
    model=model,
    tools=travel_tools,
    max_steps=6,
)

result = runtime.run(
    "查询东京课程模拟天气，换算成华氏度并解释体感。"
)
```

核心 Runtime 代码不需要出现：

```text
OpenAI()
response.output
function_call
json.loads(item.arguments)
```

因为这些都应该留在 Adapter。

### 一个合理的运行轨迹

由于真实模型有随机性，具体 wording 和 Tool trajectory 不保证逐字一致，但一个符合预期的结果应该类似：

```text
ACTION      get_mock_weather({'city': 'Tokyo'})
OBSERVATION {"temperature_c":18.0,"condition":"cloudy"}
ACTION      celsius_to_fahrenheit({'temperature_c':18.0})
OBSERVATION 64.4
FINAL       东京课程模拟天气为 18°C，约 64.4°F……
```

如果模型没有按完全相同顺序调用 Tool，不要第一反应就认为 Runtime 错了。

先区分：

```text
Runtime deterministic policy
vs
Model stochastic decision
```

---

## 12. 那 Qwen 呢？为什么 Stage 01 不需要改 Runtime？

Stage 00 已经用真实代码演示过 Qwen 可以通过 Model Studio 的 OpenAI-compatible API 使用 OpenAI SDK。

Stage 01 现在有了更强的边界：

```python
class Model(Protocol):
    def generate(...) -> ModelResponse:
        ...
```

所以无论你选择：

```text
OpenAIResponsesModel
QwenResponsesModel
OpenAICompatibleResponsesModel(base_url=...)
LocalModelAdapter
```

只要最终返回 Tiny-Agent 的：

```python
ModelResponse
```

下面这些都不应该改变：

```text
AgentRuntime
ToolRegistry
Tool handlers
max_steps logic
trajectory semantics
```

如果某个 provider 提供特殊能力，可以在 Adapter/configuration 层扩展；不要为了一个 provider 特性，把核心 Runtime 改成到处 `if provider == ...`。

---

## 13. 为什么要给 Adapter 注入 Fake Client？

真实 OpenAI client 会带来：

```text
网络
API Key
费用
模型随机性
provider outage
```

但很多 Adapter 行为其实完全可以确定性测试：

```text
Tool schema 是否翻译正确？
JSON arguments 是否 decode？
call_id 是否保留？
多个 function_call 是否全部提取？
空 response 是否报错？
不支持的 role 是否拒绝？
```

所以 `OpenAIResponsesModel` 支持：

```python
OpenAIResponsesModel(
    client=FakeOpenAIClient(...)
)
```

然后运行：

```bash
pytest -q \
  tests/test_openai_adapter.py \
  tests/test_openai_adapter_edges.py
```

这类 test 不在评估“GPT-5.6 会不会正确规划”。

它只在验证：

> **我们写的协议翻译器是不是确定地遵守契约。**

---

## 14. 为什么 Stage 01 暂时不用 provider-native conversation state？

OpenAI Responses API 可以使用 `previous_response_id` 等机制保持 provider-managed continuity。

Stage 00 已经介绍过这个概念。

但 Stage 01 的目标是让你看清：

```text
Runtime state
Adapter translation
ToolCall correlation
```

如果现在同时加入：

```text
previous_response_id
provider-managed sessions
persisted reasoning items
checkpoint/resume
```

你会很难判断“这次模型为什么还记得前面”到底是谁的责任。

所以当前 Adapter 故意保持简单、stateless transcript translation，并默认使用低复杂度 reasoning 配置。

这不是说 provider-native state 不重要。

而是：

> **一个知识点应该在它能被清楚比较的时候再引入。**

Stage 03 / 06 会专门比较 transcript、checkpoint、thread state、provider conversation state 和 long-term memory。

---

## 15. 本章最后，请把 Adapter 理解成“边缘翻译器”

完整依赖图：

```text
                 AgentRuntime
                      │
                Model Protocol
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
 OpenAIResponsesModel       Other Adapter
          │                       │
          ▼                       ▼
 OpenAI Responses API       Qwen / local / ...
```

Runtime 世界里说：

```text
ToolCall
ModelResponse
Observation
```

Provider 世界里说：

```text
function_call
function_call_output
response.output
call_id
```

Adapter 的工作就是让这两个世界彼此理解，而不让任何一边吞掉另一边的职责。

如果你已经能看着 `src/tiny_agent/models/openai.py` 解释每一次 translation，下一章我们就可以反过来问：

> **这套 Runtime 虽然已经“架构正确”，为什么仍然远远不能叫 production-ready？**

---

## 官方参考

- OpenAI Function Calling：<https://developers.openai.com/api/docs/guides/function-calling>
- OpenAI Responses API：<https://developers.openai.com/api/reference/resources/responses>
- OpenAI Python SDK：<https://github.com/openai/openai-python>