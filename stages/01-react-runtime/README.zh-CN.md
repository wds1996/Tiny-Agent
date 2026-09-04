# Stage 01：把 Tool Loop 变成 Agent Runtime

> Language: [English](README.md) | **简体中文**

上一章完成了一个固定的 `model → tool → model` 往返：第一次调用模型，请求一个工具；Python 执行工具；第二次调用模型，根据结果生成最终回答。

它能工作，但程序把路线提前写死了：

```text
第一轮一定请求工具
工具一定只执行一次
第二轮一定结束
```

只要任务变成“先查教学天气，再把摄氏度换成华氏度”，代码就会自然长出 `first`、`second`、`third`。再多几步，变量名可能需要按族谱管理。

本章解决的核心问题是：

> **当模型可能进行零次、一次或多次工具调用时，应用怎样把这些决策组织成一个有边界、可验证、可替换的执行循环？**

我们会从零写一个小型 Agent Runtime。先用完全确定的模型替身离线验证，再通过 Adapter 接入 OpenAI Responses API。

完整实现只放在 [`code/`](code/) 中；正文按知识点展示局部代码，不重复整份源文件。这样既能像教材一样连续阅读，也不会让同一份代码在文档和文件中维护两遍。

---

## 1. 学习目标

完成本章后，你应该能够：

- 从控制权角度区分确定性 Workflow、Agent、Model、Tool 与 Runtime；
- 把 ReAct 理解为可观察的 `decision → action → observation` 循环；
- 说明为什么 Runtime 不应该直接依赖某家模型服务商的响应对象；
- 解释 `ToolCall`、`ModelTurn`、`Tool`、`ToolRegistry` 和 `RunResult` 的职责；
- 说明 Tool schema 与 Python handler 为什么必须同时存在；
- 区分 Provider 侧结构约束与 Runtime 侧执行前验证；
- 沿着 `AgentRuntime.run()` 追踪一次完整运行；
- 解释运行记录为什么是应用拥有的显式状态，而不是“模型自己记住了”；
- 说明 `max_steps`、唯一 `call_id` 和错误分类如何限制运行；
- 使用确定性的 Model Double 测试 Runtime，而不依赖网络；
- 解释 Adapter 如何翻译 Provider 协议，同时保持核心循环不变。

---

## 2. 固定脚本为什么不够

Stage 00 的控制流程可以抽象为：

```python
first = call_model(user_request)
call = read_function_call(first)
result = execute(call)
final = call_model(result)
return final.output_text
```

这不是错误代码。对于只需要一次工具调用的任务，它甚至非常清楚。问题在于，它把**任务轨迹**写进了**程序结构**。

模型可能直接回答：

```text
user → model → final answer
```

也可能需要两个动作：

```text
user
  → model requests weather
  → application returns weather
  → model requests conversion
  → application returns conversion
  → model returns final answer
```

还可能在得到 Observation 后改变下一步。应用无法预先知道应该准备几个叫作 `next_response` 的变量。

真正需要抽象的是重复规则：

```python
for step in range(max_steps):
    turn = model.generate(messages, tools)

    if turn.final_text is not None:
        return turn.final_text

    for call in turn.tool_calls:
        observation = execute(call)
        messages.append(observation)

raise MaxStepsExceeded
```

这段循环看起来短，却承担四项关键责任：

1. 根据当前状态向模型请求一次决策；
2. 把动作请求映射到应用能力；
3. 把执行结果写回状态；
4. 按规则继续、结束或失败。

当这些责任被清楚封装后，固定 Tool Loop 才真正变成 Runtime。

---

## 3. Workflow、Agent 与 Runtime：先问“谁决定下一步”

“使用了大模型”不自动等于 Agent。更有用的问题是：**下一步由谁决定？**

### 3.1 确定性 Workflow

```python
weather = get_weather("Tokyo")
converted = celsius_to_fahrenheit(weather["temperature_c"])
return format_answer(weather, converted)
```

步骤、顺序和分支都由程序员提前写好。即使某一步调用了模型，整体路线仍由代码决定。这是确定性 Workflow。

它的优势是：

- 行为容易预测；
- 测试简单；
- 成本和调用次数容易估计；
- 不需要模型承担不必要的控制责任。

### 3.2 Agent loop

```python
turn = model.generate(messages, available_tools)
```

模型可以根据当前上下文选择：

- 直接返回最终文字；
- 请求天气工具；
- 请求换算工具；
- 根据工具结果选择下一步。

这时模型获得了有限的下一步决策权。但它并没有接管 Python 进程，只能从 Runtime 允许的出口中选择。

### 3.3 Runtime 是控制过程的承载层

Runtime 本身不“聪明”。它把模型决策变成一个可执行、可记录、可停止的过程：

```text
Model
    选择下一步语义动作

Runtime
    维护循环、状态、路由、执行与停止规则

Tool
    提供一个有说明和参数约束的外部能力
```

可以记住一句话：

> **Model 提议下一步，Runtime 管理下一步，Tool 实现下一步。**

舞台可以承载演员，但舞台不会突然开始背台词。同样，Runtime 可以承载 Agent 行为，但 Runtime 本身不是智能来源。

### 3.4 什么时候不需要 Agent

如果下一步可以由普通条件语句可靠决定，就优先使用确定性代码。

```text
能用清楚的 if/else 解决吗？
        ↓ 是
优先写 Workflow

        ↓ 否，需要理解开放语言和观察结果
再考虑让模型参与决策
```

Agent loop 不是“更高级的默认选项”。它用更多复杂度换取更开放的决策空间；只有任务确实需要这种空间时，交换才值得。

---

## 4. ReAct：编排可观察事件，而不是读取隐藏思维

ReAct 来自 Reasoning and Acting。对本章实现而言，最实用的工程含义是：

```text
Model Decision
      ↓
Action / Tool Call
      ↓
Application Execution
      ↓
Observation
      ↓
Next Model Decision
```

Runtime 只需要处理可观察、可记录的对象：

- 模型是否请求工具；
- 工具名与参数是什么；
- 应用执行后得到什么；
- 模型是否返回最终文字。

本章不依赖模型输出 `Thought:` 字符串，也不要求暴露私有 Chain-of-Thought。若控制器写成：

```python
if "Action:" in model_text:
    ...
```

程序就开始依赖自然语言格式。模型少写一个冒号，Runtime 会像把门禁系统建立在员工标点习惯上一样脆弱。

因此，本章使用结构化 `ToolCall` 表示动作，用 Tool message 表示 Observation。循环围绕协议对象运行，而不是围绕一段散文运行。

### 4.1 Reasoning 不等于执行权

模型可以进行复杂判断，但它影响应用的方式仍受到输出协议限制。本章只接受两种语义出口：

```text
final_text
或
tool_calls
```

模型能力影响它如何选择；Runtime 协议决定这种选择可以怎样进入系统。

---

## 5. 三个角色：Model、Runtime、Tool

最小结构可以画成：

```text
                   ┌──────────────┐
                   │    Model     │
                   │ decide next  │
                   └──────┬───────┘
                          │ ModelTurn
                          ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  messages    │◀─▶│   Runtime    │──▶│     Tool     │
│  run state   │   │ control loop │   │ validate/run │
└──────────────┘   └──────────────┘   └──────┬───────┘
                                             │
                                             ▼
                                        Observation
```

**Model** 接收当前运行记录和工具说明，返回一次与服务商无关的决策。

**Tool** 把模型可见的能力说明、参数契约和应用内部处理函数连接起来。

**Runtime** 拥有循环。它调用模型、检查返回值、路由工具、执行处理函数、追加 Observation，并决定何时停止。

把三者混在一个函数里，Provider 响应格式一变，循环和工具路由也会一起受伤；错误发生时，所有问题只剩一个模糊标签：“AI 逻辑”。这对调试没有任何帮助。

---

## 6. 先定义内部协议，再连接模型服务

完整离线 Runtime 位于 [`code/runtime.py`](code/runtime.py)。安装依赖并运行：

```bash
python -m pip install -r stages/01-react-runtime/code/requirements.txt
python stages/01-react-runtime/code/runtime.py
```

我们先定义 Runtime 真正需要的数据，不让 OpenAI Response 对象直接进入核心循环。

### 6.1 `ToolCall`：一次动作提案

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
```

Runtime 只需要回答三件事：

```text
call_id    这是哪一次调用？
name       请求哪个能力？
arguments  给这个能力什么参数？
```

`__post_init__` 会检查 ID 和名称是否为非空字符串，参数是否为字典。

使用 `frozen=True` 是为了让已经形成的调用对象不被后续代码随手修改。不可变对象不能解决全部状态问题，但能减少“日志里看到的调用”和“最后执行的调用”悄悄变成两份内容。

### 6.2 `ModelTurn`：一次模型决策只有一个出口

```python
@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
```

本章规定一次模型决策必须二选一：

```text
A. final_text：结束运行
或
B. 一个或多个 tool_calls：执行后继续
```

核心不变量是：

```python
has_final = self.final_text is not None
has_calls = bool(self.tool_calls)
if has_final == has_calls:
    raise InvalidModelTurnError(
        "A model turn must contain exactly one of final_text or tool_calls"
    )
```

两个都没有，Runtime 不知道下一步做什么；两个同时出现，Runtime 不知道应先执行工具还是直接结束。

真实 Provider 可能支持更复杂的混合输出，但内部协议不必原样复制外部系统的全部复杂度。好的内部模型只保留应用明确愿意支持的语义。

`tool_calls` 使用 tuple，也是在表达：这是本轮已经形成的一组调用，而不是等待其他代码继续追加的工作列表。

### 6.3 `call_id` 必须唯一

`ModelTurn` 拒绝同一轮重复 ID，Runtime 还会拒绝整个 run 中复用 ID：

```python
repeated = [
    call.call_id for call in turn.tool_calls if call.call_id in seen_call_ids
]
if repeated:
    raise InvalidModelTurnError(
        f"Tool call IDs must be unique within a run: {repeated}"
    )
```

Observation 依靠 `call_id` 关联动作。若一个 ID 可以指向两次调用，运行记录就无法唯一回答“这份结果属于哪个请求”。

### 6.4 `Model` Protocol：依赖行为，不依赖具体类

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        ...
```

只要对象满足这个接口，它就可以驱动 Runtime：

- 确定性的测试替身；
- 本地模型 Adapter；
- OpenAI Responses Adapter；
- 其他模型服务的 Adapter。

Runtime 不需要写 `isinstance(model, OpenAI...)`。这个 Protocol 的价值不是多写一层形式，而是让控制器可以脱离网络独立测试。

---

## 7. Tool 是接口、验证与实现的组合

本章的 Tool 定义如下：

```python
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]
```

四个字段服务于不同边界：

| 字段 | 主要使用者 | 作用 |
|---|---|---|
| `name` | Model 与 Registry | 标识能力 |
| `description` | Model | 说明何时、为何使用 |
| `arguments_model` | Model 与 Runtime | 生成 schema，并在执行前验证 |
| `handler` | Runtime | 真正执行 Python 逻辑 |

### 7.1 同一份参数模型服务两个位置

Pydantic 参数模型既能生成模型可见的 JSON Schema，也能验证真正进入执行边界的数据：

```python
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: Literal["Tokyo", "Paris"]
```

这里：

- `extra="forbid"` 拒绝额外字段；
- `strict=True` 避免不必要的隐式类型转换；
- `Literal` 把值域限制在教学数据支持的城市。

Tool schema 来自：

```python
def schema(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "parameters": self.arguments_model.model_json_schema(),
    }
```

执行前再次验证：

```python
arguments = self.arguments_model.model_validate(raw_arguments)
```

两步并不重复：

```text
schema 告诉上游“应该生成什么”
validation 检查本地“实际收到了什么”
```

Provider 侧 strict schema 是生成约束，Runtime 侧 validation 是执行边界。真正调用 handler 的是应用，因此最终输入检查必须属于应用。

### 7.2 Handler 接收验证后的对象

```python
def celsius_to_fahrenheit(
    arguments: TemperatureArguments,
) -> dict[str, float]:
    converted = round(arguments.temperature_c * 9 / 5 + 32, 1)
    return {"temperature_f": converted}
```

Handler 不需要再从原始字典中猜字段和类型，可以专注业务逻辑。

### 7.3 Tool description 会影响模型选择

下面的描述几乎没有信息：

```text
Convert stuff.
```

本章使用：

```text
Convert a Celsius value to Fahrenheit.
```

清楚的 Tool 说明应交代：

- 返回什么；
- 什么时候适用；
- 参数含义；
- 重要限制。

描述越含糊，模型越需要猜。单纯换一个更强模型，往往只会得到更流畅的猜测。

---

## 8. `ToolRegistry`：能力白名单与路由表

模型返回的是字符串名称。Runtime 不能因此动态执行任意同名对象，而应只在应用显式注册的 Tool 中查找：

```python
class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool
```

执行时：

```python
def execute(self, call: ToolCall) -> Any:
    tool = self._tools.get(call.name)
    if tool is None:
        raise UnknownToolError(f"Unknown tool: {call.name}")
    return tool.invoke(call.arguments)
```

这建立了一个最小能力边界：只有应用明确注册的 Tool 才能进入执行路径。模型生成 `move_the_moon`，不会让 Runtime 突然获得天体工程预算。

需要精确一点：Registry 是**能力白名单**，但还不是完整的用户身份授权系统。它回答“这个应用进程是否拥有并暴露该能力”，不回答“当前用户是否有权在当前资源上使用它”。本章只实现前一个边界。

重复 Tool 名称会在初始化时失败。否则一个名字对应两个 handler，执行语义会依赖注册顺序，调试会变成“今天这个名字到底指谁”。

Registry 的 `schemas()` 只向 Model 暴露接口说明，不暴露 handler：

```python
def schemas(self) -> list[dict[str, Any]]:
    return [tool.schema() for tool in self._tools.values()]
```

模型看到能力描述，Runtime 保留真正的执行实现。

---

## 9. 一轮一轮阅读 `AgentRuntime.run()`

完整实现仍在 [`code/runtime.py`](code/runtime.py)。现在沿着一次运行追踪控制权。

### 9.1 建立显式运行状态

```python
messages: list[dict[str, Any]] = [
    {"role": "user", "content": user_input}
]
seen_call_ids: set[str] = set()
```

`messages` 是本次运行的 transcript（运行记录）。它由应用维护，不是“模型脑内自动保存的记忆”。

本章使用三种消息角色：

```text
user
    用户任务

assistant
    模型给出的最终文字或 Tool Call

tool
    应用执行后返回的 Observation
```

`seen_call_ids` 则保护调用与结果的关联不变量。

### 9.2 每轮只请求一次模型决策

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(messages, self.registry.schemas())
```

Model 能看到当前运行记录和允许的工具说明。它返回 `ModelTurn`，但它不拥有 Python 的循环；下一轮是否发生，由 Runtime 决定。

Runtime 还检查实际返回对象：

```python
if not isinstance(turn, ModelTurn):
    raise InvalidModelTurnError(
        "Model.generate() must return a ModelTurn"
    )
```

即使 Adapter 声称遵守接口，边界仍应验证实际结果。

### 9.3 最终文字分支：写入记录并结束

```python
if turn.final_text is not None:
    messages.append({"role": "assistant", "content": turn.final_text})
    return RunResult(
        answer=turn.final_text,
        model_turns=step,
        messages=tuple(messages),
    )
```

最终答案也写入 transcript。`RunResult` 不只返回一个字符串，还保留模型轮数和完整轨迹，便于测试与审查。

### 9.4 Tool Call 分支：先记录请求，再执行

Runtime 先写入 assistant Tool Call：

```python
messages.append(
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [asdict(call) for call in turn.tool_calls],
    }
)
```

随后逐个执行：

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

先记录请求、再记录 Observation，运行轨迹才具有完整因果关系。若只保存结果，审查者会看到“程序突然得到天气”，却不知道是谁基于什么参数发起了动作。

### 9.5 Tool Output 作为 Observation 回到状态

```python
observation = json.dumps(result, ensure_ascii=False, default=str)
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.call_id,
        "name": call.name,
        "content": observation,
    }
)
```

下一轮 Model 能使用工具结果，不是因为函数执行后产生了心灵感应，而是 Runtime 明确把 Observation 放回输入状态。

完整轨迹如下：

```text
user request
    ↓
assistant requests call-weather
    ↓
tool(call-weather) returns weather
    ↓
assistant requests call-convert
    ↓
tool(call-convert) returns Fahrenheit
    ↓
assistant returns final text
```

### 9.6 多个 Tool Call 不等于并发执行

`ModelTurn` 可以容纳多个调用，但当前 Runtime 使用普通 `for` 循环顺序执行：

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

因此必须区分：

```text
一轮可以表示多个调用
        ≠
这些调用正在并发执行
```

顺序执行让完成顺序和副作用更容易推理。本章没有实现并发，也不会给普通 `for` 循环戴一顶写着“parallel”的大帽子。

### 9.7 `max_steps`：模型想继续，系统不必无限同意

如果模型始终返回 Tool Call，Runtime 最终执行：

```python
raise MaxStepsExceeded(
    f"The run did not finish within max_steps={self.max_steps} model turns"
)
```

这里的 step 是**模型决策轮数**，不是工具调用总数。若一轮包含多个 Tool Call，仍只消耗一个 model step。

`max_steps` 是逻辑执行预算。它不等于超时器，也不保证固定费用，但至少防止控制流无限继续。没有停止条件的 `while True` 很有冒险精神，账单通常也会受到鼓舞。

---

## 10. 显式状态为什么重要

模型每一轮只能根据本次传入的数据做决定。Runtime 必须明确维护：

- 用户请求；
- 模型提出的每次 Tool Call；
- 每次 Tool Output；
- 最终答案；
- 已使用的调用编号。

这份运行记录有三个作用。

### 10.1 给下一轮提供必要信息

没有 Observation，模型无法基于工具结果继续。

### 10.2 给程序提供可检查轨迹

测试可以断言消息角色顺序、调用编号和模型轮数，而不只检查最后一句话。

### 10.3 给错误定位提供上下文

若结果错误，可以区分：模型选错 Tool、参数错误、handler 错误，还是最终总结错误。

当前 transcript 只属于一次 `run()`，保存在内存中。它不是跨任务长期记忆，也不会自动在进程重启后恢复。本章只建立一条原则：**运行状态必须由应用显式拥有。**

---

## 11. 为什么先使用确定性的 `ScriptedWeatherModel`

直接接真实模型看起来更“AI”，却不适合先测试控制器。失败时你很难判断：

```text
Runtime 循环写错了？
还是模型这次选择了不同路径？
```

`ScriptedWeatherModel` 的行为完全固定：

```python
observations = [m for m in messages if m.get("role") == "tool"]

if not observations:
    return ModelTurn(tool_calls=(weather_call,))

if len(observations) == 1:
    return ModelTurn(tool_calls=(conversion_call,))

return ModelTurn(final_text="...")
```

它不是在模拟语言智能，而是在提供一个确定性的 Model Double：

```text
0 个 Observation → 请求天气
1 个 Observation → 请求换算
2 个 Observation → 返回最终答案
```

这样可以独立验证 Runtime 状态转移：

- 不需要 API Key；
- 每次轨迹相同；
- 不会因为模型换一种合理表达而随机失败；
- 失败时可以先检查控制器，而不是猜模型今天的心情。

运行：

```bash
python stages/01-react-runtime/code/runtime.py
```

预期轨迹类似：

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's deterministic teaching record is 18.0°C (64.4°F), cloudy.
```

| 模型轮次 | Model 返回 | Runtime 行为 |
|---|---|---|
| 1 | 天气 Tool Call | 验证并执行，追加天气 Observation |
| 2 | 换算 Tool Call | 验证并执行，追加换算 Observation |
| 3 | `final_text` | 写入最终消息并返回 `RunResult` |

---

## 12. 错误要按责任层分类

本章定义五类 Runtime 错误：

| 错误 | 含义 | 首先检查哪里 |
|---|---|---|
| `InvalidModelTurnError` | Model 返回不满足内部协议 | Model / Adapter 边界 |
| `UnknownToolError` | 请求名称不在 Registry | Tool 路由 |
| `ToolArgumentsError` | 参数未通过 Pydantic | Tool 输入契约 |
| `ToolExecutionError` | handler 在合法输入后执行失败 | Tool 实现或外部依赖 |
| `MaxStepsExceeded` | 达到轮数上限仍未结束 | Model 行为与控制预算 |

### 12.1 参数错误与执行错误不同

```text
{"city": "Atlantis"}
```

应在 handler 之前失败，属于 `ToolArgumentsError`。

合法参数进入 handler 后，若访问服务或执行逻辑失败，属于 `ToolExecutionError`。

两者修复位置不同：前者可能需要修正参数或 schema，后者可能需要修复实现或外部依赖。把它们都吞成 `except Exception: return "error"`，只是让错误从“有分类”升级成“下落不明”。

### 12.2 当前策略是“失败即停止”

`Tool.invoke()` 包装 handler 异常后抛出：

```python
try:
    return self.handler(arguments)
except Exception as exc:
    raise ToolExecutionError(
        f"Tool {self.name!r} failed with {type(exc).__name__}"
    ) from exc
```

当前 Runtime 不自动重试，也不把错误交给 Model 自行修复。这是刻意选择的简单语义：你可以准确推断 handler 执行了几次。

自动重试不是免费的可靠性开关。对有副作用的 Tool，重复执行可能比第一次失败更糟。没有明确策略时，“再试一次”只是把希望包在循环里。

### 12.3 错误文本也属于边界设计

包装后的异常保留类型，并用 `raise ... from exc` 保留 Python 因果链，但不会把任意内部异常内容直接塞回模型上下文。本章遇错终止，而不是让模型恢复。

---

## 13. 确定性测试：验证轨迹，而不只验证最后一句

运行章节检查：

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

完整测试位于 [`code/runtime_checks.py`](code/runtime_checks.py)，使用标准库 `unittest`，不访问网络。

### 13.1 正常路径检查了什么

```python
result = AgentRuntime(
    ScriptedWeatherModel(), build_tools(), verbose=False
).run("weather then conversion")

self.assertEqual(result.model_turns, 3)
self.assertIn("64.4°F", result.answer)
```

测试还检查 Tool message 中的调用编号：

```python
self.assertEqual(
    [message["tool_call_id"] for message in tool_messages],
    ["call-weather", "call-convert"],
)
```

最终文字正确但轨迹错误，仍可能意味着重复执行、错误关联或绕过验证。Agent 系统不能只看最后一句话像不像答案。

### 13.2 反例更能说明边界

测试还构造：

- 永不结束的 Model；
- 请求未知名称的 Model；
- 返回非法城市参数的 Model；
- 重复使用 `call_id` 的 Model；
- handler 必然抛错的 Tool；
- 伪造的 Provider 客户端。

例如未知工具：

```python
with self.assertRaises(UnknownToolError):
    runtime.run("request an unregistered tool")
```

这条断言保护的架构契约是：**模型生成一个名字，不能让 Registry 之外的能力自动出现。**

### 13.3 为什么不用真实模型做 Runtime 单元测试

真实模型适合端到端实验，不适合验证每条确定性不变量。单元测试需要回答：给定明确输入，Runtime 是否必然执行某条状态转移？

如果测试失败后的第一句话是“也许模型今天换了表达”，它就没有隔离被测对象。

---

## 14. Adapter：把 Provider 协议挡在 Runtime 外面

离线 Runtime 已经成立。现在接入真实模型：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
python stages/01-react-runtime/code/openai_runtime.py
```

完整 Adapter 位于 [`code/openai_runtime.py`](code/openai_runtime.py)。核心目标是：**不修改 `AgentRuntime.run()`。**

```text
OpenAI Response
      ↓
OpenAIResponsesModel
      ↓
ModelTurn / ToolCall
      ↓
AgentRuntime
```

### 14.1 Adapter 负责三种翻译

第一，将内部 Tool schema 转成 Provider function tool：

```python
@staticmethod
def _to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool["description"],
        "parameters": tool["parameters"],
        "strict": True,
    }
```

第二，把 Provider `function_call` 转成内部 `ToolCall`：

```python
calls.append(
    ToolCall(
        call_id=item.call_id,
        name=item.name,
        arguments=arguments,
    )
)
```

第三，把 Runtime 的 Tool message 转成 `function_call_output`：

```python
outputs.append(
    {
        "type": "function_call_output",
        "call_id": call_id,
        "output": str(message.get("content", "")),
    }
)
```

OpenAI 字段停留在 Adapter 内，核心循环只认识内部协议。这就是 Adapter 的价值：不是为了多写一个类，而是为了阻止外部格式扩散到控制逻辑。

### 14.2 `previous_response_id` 连接响应链

Adapter 保存最近一次 Provider Response ID：

```python
self._previous_response_id: str | None = None
```

后续请求加入：

```python
if self._previous_response_id is not None:
    request["previous_response_id"] = self._previous_response_id
```

这样，后续模型调用可以只发送新产生的 Tool Output，而不必手工重建 Provider 的全部历史输出项。

需要注意：使用 `previous_response_id` 时，新请求仍显式传入 `instructions`。不要假设上一轮的 instructions 会自动成为下一轮请求的一部分。

### 14.3 只提交尚未发送的 Tool Output

Runtime 每轮向 Model 传入完整 transcript。如果 Adapter 每次把所有 Tool message 都重新发送，同一个 `call_id` 会被重复提交。

因此它维护：

```python
self._submitted_tool_call_ids: set[str] = set()
```

`_next_input()` 只挑选尚未提交的 Tool Output。Provider 返回合法完成响应后，才更新内部状态：

```python
self._previous_response_id = response_id
self._submitted_tool_call_ids.update(pending_call_ids)
```

先验证响应，再提交 Adapter 状态，可以避免失败请求被误记成成功。

### 14.4 一个 Adapter 实例对应一条 run

`_previous_response_id` 和 `_submitted_tool_call_ids` 都属于一条运行轨迹。因此本章约定：

```text
一个 OpenAIResponsesModel 实例
        ↔
一次 AgentRuntime.run(...)
```

不要把同一个实例同时交给多个用户任务，否则响应链可能串在一起。这个限制是当前 Adapter 的明确设计，不是对所有模型客户端的普遍结论。

### 14.5 Provider Response 仍然要验证

Adapter 检查：

- `status` 是否为 `completed`；
- Response ID 是否为非空字符串；
- 函数参数是否为合法 JSON object；
- 没有 Tool Call 时是否存在非空最终文字。

例如：

```python
try:
    arguments = json.loads(item.arguments)
except json.JSONDecodeError as exc:
    raise ProviderResponseError(
        f"Arguments for function {item.name!r} are not valid JSON"
    ) from exc
```

Provider 是外部系统。Adapter 不只负责“换字段名”，还负责阻止坏数据进入内部协议。

### 14.6 为什么关闭 parallel Tool Calls

真实示例请求中设置：

```python
"parallel_tool_calls": False,
```

这样每个 Provider turn 保持单个调用，便于和离线模型的线性轨迹对应。内部 `ModelTurn` 仍然能够表示多个调用，但当前 Adapter 主动收窄行为。

这体现了一个有用的设计方法：**内部协议可以保留合理能力，具体接入可以根据当前教学目标选择更窄的策略。**

---

## 15. 控制权清单：模型究竟能做什么

在本章实现中，Model 可以：

- 根据 transcript 与 Tool schema 选择最终回答或 Tool Call；
- 选择已暴露的 Tool 名称；
- 生成 Tool 参数；
- 在得到 Observation 后改变下一步选择。

Model 不能直接：

- 调用任意 Python 对象；
- 绕过 Registry；
- 绕过 Pydantic 参数验证；
- 修改 `max_steps`；
- 复用 `call_id` 而不被拒绝；
- 决定异常是否被吞掉；
- 在返回最终文字后要求 Runtime 继续执行。

所谓 Agent 自主，并不是一个总开关，而是一组被协议分配的决策权限。系统越清楚地写出模型可以决定什么、应用保留什么，行为越容易推理。

---

## 16. 当前 Runtime 的准确规格

这个实现已经具备：

```text
Provider-neutral Model contract
Tool schema + handler
Runtime-side argument validation
Tool Registry routing
Decision → Action → Observation loop
Explicit transcript
Call/result correlation
Unique call IDs
Model-step budget
Separated error types
Deterministic Model Double
Offline tests
OpenAI Responses Adapter
```

它有意没有实现：

- 异步或并发 Tool 执行；
- 自动重试；
- 错误 Observation 后的模型恢复；
- 持久化运行状态；
- 进程重启后的恢复；
- 完整用户身份授权与副作用策略；
- 时间、费用和 Token 的组合预算；
- 流式输出；
- 多用户并发下的 Adapter 生命周期管理。

列出“没有做什么”不是自我否定，而是在给代码写准确规格。一个 Demo 能跑，只能证明一条路径走通；可靠设计还需要知道其他路径会怎样停止。

---

## 17. 常见误区

### 误区一：“Runtime 就是一个 while 循环”

循环只是外壳。真正重要的是内部协议、状态所有权、工具路由、验证、错误分类和停止规则。

### 误区二：“模型返回 Tool Call，Runtime 就应该执行”

Runtime 仍需检查内部协议、调用 ID、Registry 名称和参数模型。Tool Call 是提案，不是命令特权。

### 误区三：“Fake Model 没有智能，所以测试没意义”

测试目标是 Runtime 控制逻辑，不是模型能力。确定性替身正是为了隔离被测对象。

### 误区四：“支持多个 Tool Call 就等于支持并发”

数据结构可以表示多个调用；是否并发执行由 Runtime 实现决定。本章仍是顺序执行。

### 误区五：“最终答案正确就说明 Agent 成功”

正确文字可能来自重复执行、错误关联或绕过验证的轨迹。结果质量与轨迹质量需要分别检查。

### 误区六：“Adapter 只是多余的字段转换”

Adapter 同时负责协议翻译和外部输入验证。它保护 Runtime 不被 Provider 细节绑死。

---

## 18. 动手练习

### 练习一：同一轮返回两个 Tool Call

让 `ScriptedWeatherModel` 在第一轮同时请求东京和巴黎天气，使用不同 `call_id`。观察当前 Runtime 的执行顺序和 transcript 顺序。

### 练习二：故意复用调用编号

让第二轮再次使用 `call-weather`。确认 Runtime 在执行 handler 之前拒绝，并解释它保护了什么因果关系。

### 练习三：增加第三个 Tool

新增 `describe_temperature`，输入华氏度并返回 `cold`、`mild` 或 `hot`。只修改 Tool 集合和 `ScriptedWeatherModel`，不要改 `AgentRuntime.run()`。

若新增普通 Tool 必须修改核心循环，说明任务细节已经泄漏进 Runtime。

### 练习四：比较参数错误与执行错误

分别制造：

```text
参数为 {"city": "Atlantis"}
合法参数进入一个必然抛异常的 handler
```

确认得到不同错误类型，并说明修复位置为什么不同。

### 练习五：把 Tool 错误改成 Observation

在副本中把错误序列化后交回 Model。必须同时设计最大修复次数，并记录 handler 是否可能重复执行。比较这种策略与当前“失败即停止”的可推理性。

### 练习六：删除 Adapter 去重集合

移除 `_submitted_tool_call_ids`，使用测试中的 `FakeResponsesAPI` 记录后续请求。观察旧 Tool Output 是否被重复发送。

### 练习七：为 Adapter 增加重用保护

让同一个 `OpenAIResponsesModel` 在一次 run 结束后拒绝第二个新用户任务，并为这个约束写测试。

### 练习八：写一份确定性 Workflow 对照

用普通 Python 写“天气 → 换算 → 回答”。比较它与 Agent loop 的代码量、可预测性和适用条件。不要默认 Agent 版本更高级，先说明额外复杂度换来了什么。

---

## 19. 本章自检

尝试不看代码回答：

1. 固定两轮脚本为什么不能处理一般 Tool loop？
2. Workflow 与 Agent loop 的关键控制差别是什么？
3. ReAct 在本章中指什么，为什么不依赖 `Thought:` 文本？
4. `ModelTurn` 为什么要求 `final_text` 与 `tool_calls` 二选一？
5. Tool schema、Pydantic validation 和 handler 分别位于哪个边界？
6. Registry 为什么既是路由表，也是最小能力白名单？
7. 为什么先记录 assistant Tool Call，再记录 Tool Observation？
8. `max_steps` 计算什么，又不能保证什么？
9. 确定性 Model Double 为什么适合单元测试 Runtime？
10. Adapter 为什么保存 `previous_response_id` 与已提交 `call_id`？
11. 为什么一个 Adapter 实例只对应一条 run？
12. 最终文字正确但轨迹错误，为什么仍可能是失败？
13. 哪类任务应该继续使用普通 Workflow，而不是 Agent loop？

能够沿着数据流和控制流回答这些问题，说明你不只“运行了一个 Agent”，而是真正理解了 Runtime 如何工作。

---

## 20. 本章代码目录

```text
stages/01-react-runtime/
├── README.zh-CN.md
├── README.md
└── code/
    ├── runtime.py          # 与 Provider 无关的 Runtime 与离线示例
    ├── runtime_checks.py   # 确定性边界测试
    ├── openai_runtime.py   # OpenAI Responses Adapter
    └── requirements.txt
```

完整实现只在 `code/` 中维护；正文中的代码块只用于解释当前知识点。
