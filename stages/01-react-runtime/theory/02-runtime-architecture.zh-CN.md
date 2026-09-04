# 02 — 从手写 loop 到 Core Runtime Architecture：每一层为什么存在？

> Language: [English](02-runtime-architecture.md) | 简体中文

上一章我们已经确认：当模型会根据 Tool observation 再决定下一步时，应用需要一个显式 loop。

现在的问题变成：

> **这个 loop 要不要就一直写在一个函数里？**

当然可以。

最开始你可能会写成：

```python
while True:
    response = openai_client.responses.create(...)

    if response_has_tool_call(response):
        if tool_name == "get_mock_weather":
            result = get_mock_weather(...)
        elif tool_name == "celsius_to_fahrenheit":
            result = celsius_to_fahrenheit(...)

        messages.append(...)
        continue

    return response.output_text
```

几十行时没问题。

但一旦加入：

```text
第二个 provider
十几个 Tools
Tool schema
错误处理
step limit
测试
日志
权限
```

这个函数就会开始同时知道：

```text
OpenAI 的 response 长什么样
Qwen 的 endpoint 怎么配
Tool 的 JSON Schema
Tool 名字如何路由
Python handler 怎么执行
循环什么时候停止
错误怎样变成 observation
```

这不是“代码还不够优雅”。

这是**职责开始互相污染**。

这一章我们不先背 architecture diagram，而是按痛点把它一层层拆开。

---

## 1. 第一个问题：Runtime 为什么不应该认识 provider 的 Response？

假设核心 loop 里直接写：

```python
for item in response.output:
    if item.type == "function_call":
        name = item.name
        arguments = json.loads(item.arguments)
```

那么 Runtime 已经知道了 OpenAI Responses API 的细节。

下一次换 provider，如果返回结构变成：

```text
tool_calls[0].function.name
```

或者参数字段、错误结构、usage 都不同，Runtime 就要跟着改。

所以第一步不是写 Runtime，而是先给 Runtime 定义自己的语言。

---

## 2. 先定义 Runtime 自己认识的 `ToolCall`

```python
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
```

这三个字段分别解决什么？

### `name`

告诉 Runtime：

```text
模型想使用哪个 capability？
```

例如：

```text
get_mock_weather
```

### `arguments`

告诉 Runtime：

```text
模型提出了哪些参数？
```

例如：

```python
{"city": "Tokyo"}
```

### `id`

告诉 Runtime：

```text
这一次 Tool 请求是谁？
```

它不是可有可无的装饰字段。

如果模型同一轮提出：

```text
call_A -> get_mock_weather(Tokyo)
call_B -> get_mock_weather(Paris)
```

单靠 Tool 名字无法把两个 observation 正确对应回去。

所以后面 provider 的 `call_id` 会被归一化为：

```python
ToolCall.id
```

这就是 correlation ID。

---

## 3. 再定义“一次模型决策”的统一结果

Runtime 不想知道：

```text
OpenAI Response
Qwen Response
FakeResponse
```

它只想知道：

> **这一轮模型是准备继续行动，还是已经回答完？**

所以我们定义：

```python
from dataclasses import field


@dataclass(slots=True)
class ModelResponse:
    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
```

现在 provider-specific 世界先被压成一个稳定边界：

```text
OpenAI Response ──┐
Qwen Response ────┼──> Adapter ──> ModelResponse
Fake Model ───────┘
                              │
                              ▼
                         AgentRuntime
```

这一步叫 **normalization**。

注意 normalization 不是“把所有 provider 功能削成一样”。

它的意思是：

> **核心 Runtime 只依赖自己真正需要的共同语义。**

provider 特有能力可以继续留在 adapter 或更高层配置中，但不应该污染最小 loop。

---

## 4. `Model` 为什么是 Protocol，而不是直接写 `OpenAIResponsesModel`？

接下来 Runtime 需要调用模型。

最直接可以写：

```python
class AgentRuntime:
    def __init__(self, model: OpenAIResponsesModel):
        self.model = model
```

但这样 Runtime 又绑定了具体实现。

更好的契约是：

```python
from typing import Protocol


class Model(Protocol):
    def generate(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ModelResponse:
        ...
```

Runtime 只要求：

```text
给你 messages + Tool schemas
你返回一个 ModelResponse
```

至于背后是：

```text
OpenAI
Qwen
本地模型
FakeModel
```

Runtime 不关心。

这就是 dependency inversion 在 Agent Runtime 里的一个非常具体的落点。

### 你可以马上验证这个设计

```python
class ScriptedTravelModel:
    def generate(self, messages, tools) -> ModelResponse:
        ...
```

只要满足同一个接口，它就能替代真实模型。

所以测试 Runtime 时不需要 API Key。

---

## 5. Tool 为什么不能只是一个 Python 函数？

现在看旅行助手的 Tool：

```python
def get_mock_weather(city: str) -> dict:
    ...
```

Python 知道这个函数怎么执行。

但模型不知道。

模型需要看到的是：

```text
这个能力叫什么？
它是干什么的？
什么时候应该用？
参数有哪些？
参数类型是什么？
```

因此 Tool 至少有两张脸：

```text
模型看到的接口                  Runtime 拥有的实现
----------------              ----------------
name                           Python handler
description                    execute
parameter schema               error boundary
```

Tiny-Agent 用一个对象把它们绑在一起：

```python
@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
```

这也是为什么：

```text
Tool schema
!=
Python function
```

模型选择的是前者描述出来的 capability；Runtime 最后执行的是后者。

---

## 6. 为什么需要 `ToolRegistry`，而不是一串 `if`？

最初两三个 Tool 时，很容易写：

```python
if call.name == "get_mock_weather":
    ...
elif call.name == "celsius_to_fahrenheit":
    ...
```

问题不是 `if` 很丑。

问题是它让 Agent loop 同时承担了：

```text
Tool 注册
名字唯一性
schema 导出
名字查找
handler 执行
```

所以把它们收进：

```python
class ToolRegistry:
    def register(self, tool: Tool) -> None:
        ...

    def schemas(self) -> list[dict]:
        ...

    def execute(self, name: str, arguments: dict) -> Any:
        ...
```

Runtime 就可以写成：

```python
observation = self.tools.execute(
    call.name,
    call.arguments,
)
```

而不需要知道 handler 实际放在哪里。

### 更重要的是：Registry 是未来的治理入口

后面加入：

```text
permissions
approval
tracing
timeout
MCP-discovered Tools
Tool metadata
```

时，ToolRegistry / Tool execution boundary 会成为天然的挂载点。

所以 Registry 不是“为了少写几个 if”。

它是在建立一个**能力进入真实执行世界的边界**。

---

## 7. 现在终于可以写 `AgentRuntime`

到这里我们已经有：

```text
Model
ToolCall
ModelResponse
Tool
ToolRegistry
```

现在 Runtime 的代码反而变得很短：

```python
class AgentRuntime:
    def __init__(self, model, tools, max_steps=8):
        self.model = model
        self.tools = tools
        self.max_steps = max_steps

    def run(self, user_input: str):
        messages = [
            {"role": "user", "content": user_input},
        ]

        for step in range(1, self.max_steps + 1):
            response = self.model.generate(
                messages,
                self.tools.schemas(),
            )

            if response.tool_calls:
                for call in response.tool_calls:
                    observation = self.tools.execute(
                        call.name,
                        call.arguments,
                    )
                    # 把 action / observation 记录进 state
                continue

            if response.final_answer is not None:
                return response.final_answer

            raise RuntimeError("invalid model response")

        raise RuntimeError("max_steps exceeded")
```

注意一个很有意思的现象：

> **当边界拆清楚以后，Runtime 本身其实没有多神秘。**

Agent framework 看起来复杂，是因为生产系统会继续往这个 loop 周围加入 persistence、retry、approval、tracing、streaming、checkpoint 等能力。

最底层的控制骨架依然很朴素。

---

## 8. 真正的 `run()` 要比上面多做两件事

### 第一：记录 model action

模型发出 ToolCall 后，我们先把 action 放进 transcript：

```python
messages.append(
    {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call.id,
                "name": call.name,
                "arguments": call.arguments,
            }
            for call in response.tool_calls
        ],
    }
)
```

### 第二：记录 observation，并保留 `call_id`

```python
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.id,
        "name": call.name,
        "content": observation,
    }
)
```

为什么一定要同时保留 action 和 observation？

因为下一轮 provider adapter 需要重建：

```text
模型提出了哪个 function_call？
哪个 function_call_output 属于它？
```

如果只留下最终字符串：

```text
"18.0"
```

下一轮就失去了结构关系。

所以这份 `messages` 既是当前最简单的 state，也是最原始的执行 trajectory。

Stage 08 会再把 tracing 正式拆出来，但这里先让执行事实可见。

---

## 9. 一轮多个 ToolCall，Runtime 应该怎样看？

模型可能一轮返回：

```python
ModelResponse(
    tool_calls=[call_a, call_b]
)
```

例如：

```text
get_weather(Tokyo)
get_weather(Paris)
```

Runtime 可以在同一个 model turn 下记录两个 action 和两个 observation。

但当前 Stage 01 是：

```python
for call in response.tool_calls:
    execute(call)
```

也就是**顺序执行 Python handler**。

所以必须区分：

```text
模型一次决策提出多个 ToolCall
!=
Tool handler 物理并发执行
```

真正并发还需要：

```text
async task
cancellation
concurrency limit
partial failure handling
result aggregation
```

Stage 10 再系统处理。

---

## 10. `AgentResult` 为什么应该保留 trajectory？

如果 Runtime 最后只返回：

```python
return "64.4°F"
```

我们会丢掉很多调试信息。

因此 Tiny-Agent 返回：

```python
@dataclass(slots=True)
class AgentResult:
    output: str
    steps: int
    messages: list[dict[str, Any]]
```

这让测试可以检查：

```text
第几步结束？
模型提出了什么 ToolCall？
Tool observation 是否真的进入历史？
call_id 是否保留？
```

这也是为什么“只评价最终答案”经常不够。

两个 Agent 都回答 64.4°F：

```text
Agent A：查 Tool -> 换算 Tool -> 正确回答
Agent B：完全没查 Tool，凭参数记忆猜了一个答案
```

最终文本可能一样，但 trajectory 完全不同。

Stage 08 会把这种 trajectory evaluation 做成正式体系。

---

## 11. 为什么单元测试应该先用 `ScriptedModel`？

看真实测试里的思路：

```python
class ScriptedModel:
    def generate(self, messages, tools):
        if first_turn:
            return ModelResponse(
                tool_calls=[...]
            )

        assert messages[-1]["role"] == "tool"
        return ModelResponse(
            final_answer="..."
        )
```

这个测试真正验证的是：

```text
Runtime 有没有执行 Tool？
Tool observation 有没有回到下一轮？
step count 对不对？
trajectory role 顺序对不对？
```

运行：

```bash
pytest -q tests/test_runtime.py
```

预期：

```text
1 passed
```

再运行边界测试：

```bash
pytest -q tests/test_runtime_edges.py
```

这里会覆盖：

```text
EndlessToolModel -> max_steps 强制停止
ErrorAwareModel  -> Tool failure 成为安全 observation
EmptyModel       -> contract violation
```

这就是“测试也是教程”的地方：

> 看 assertion，你能看到 Runtime 对外承诺的行为。

---

## 12. 教学版和 `src/` 版为什么故意不同？

`minimal_react_runtime.py` 把当前机制放在一个文件里。

而现在真正的 library 已拆成：

```text
src/tiny_agent/types.py
src/tiny_agent/tool.py
src/tiny_agent/runtime.py
src/tiny_agent/models/openai.py
```

另外后续 Stage 已经让 `Tool` 支持 async execution，让 runtime 的 unexpected error observation 做安全脱敏。

所以阅读顺序应该是：

```text
先读 stage snapshot
    ↓
理解最小机制
    ↓
再读 src/
    ↓
观察后续工程能力怎样围绕同一个 boundary 生长
```

不要反过来一开始就扎进最终 `src/`，否则你很难区分“Stage 01 必需”与“Stage 07/10 后来加的”。

---

## 13. 本章真正建立的是 dependency direction

最终依赖关系应该是：

```text
              AgentRuntime
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
      Model             ToolRegistry
        ▲                   │
        │                   ▼
 Provider Adapter       Tool handler
```

而不是：

```text
AgentRuntime
  ├── import OpenAI
  ├── if Qwen ...
  ├── if tool == weather ...
  ├── if tool == search ...
  └── provider-specific parsing ...
```

一个简单的检验方法是：

> **如果新增一个 provider，必须修改 `AgentRuntime.run()`，那 Model boundary 很可能设计错了。**

下一章，我们就真正把 OpenAI Responses API 接到这个边界上，看看 provider-specific 数据怎样被翻译成 Tiny-Agent 的 `ModelResponse`。