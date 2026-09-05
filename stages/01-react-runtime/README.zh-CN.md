# Stage 01：把 Tool Loop 变成 Agent Runtime

> Language: [English](README.md) | **简体中文**

上一章我们故意停在了一个有点别扭的位置：程序已经能让模型请求一次 Tool，Python 也能执行，再把结果送回模型，但整个流程还是写死的。

这就像你请了一个助理，第一天的工作流程是：先去档案室查资料，回来以后做一次计算，然后向你汇报。你当然可以把三步写成三行固定流程。问题是第二天任务变了：有时根本不用查资料，有时要连续查两次，有时查完以后才知道下一步该做什么。你总不能每天早上先猜助理今天会走几步，再准备 `first_response`、`second_response`、`third_response`。

所以这章真正要解决的，不是“再加一个工具”，而是：

> **当模型每一轮都可能决定下一步时，应用怎样把这种不确定性装进一个可控的循环里？**

这个循环就是 Agent Runtime 的核心。

---

## 1. 先看看固定脚本哪里开始变笨

Stage 00 的工具示例，本质上是这样：

```python
first = call_model(user_request)
call = read_tool_call(first)
result = execute(call)
final = call_model(result)
return final.output_text
```

对于“一次工具调用就结束”的任务，这段代码完全没问题。甚至我会说，它比一上来就套一个庞大框架更好懂。

麻烦出现在任务路径不固定的时候。

比如用户说：

> 读取东京的教学天气，并把摄氏度换成华氏度。

模型可能先请求天气 Tool，拿到 `18.0°C` 后再请求温度换算 Tool，最后才给答案：

```text
user
  ↓
model: get_teaching_weather("Tokyo")
  ↓
application: 18.0°C, cloudy
  ↓
model: celsius_to_fahrenheit(18.0)
  ↓
application: 64.4°F
  ↓
model: final answer
```

也可能遇到另一个任务，模型第一轮就直接回答，根本不需要 Tool。

你会发现，程序真正知道的不是“总共有三轮”，而是一个重复规则：**每一轮先让模型决定下一步；如果它要调用工具，执行完再继续；如果它给出最终答案，就结束。**

先把这个想法写成伪代码：

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

这几行就是本章的主角。后面的所有类——`ToolCall`、`ModelTurn`、`ToolRegistry`、Adapter——都是为了让这段循环的职责更清楚，而不是为了把简单事情写复杂。

---

## 2. Agent 和普通 Workflow 到底差在哪

在继续写代码之前，我们先解决一个很容易越学越糊的问题：是不是只要程序里用了 LLM，就叫 Agent？

不是。

看一个普通的确定性流程：

```python
weather = get_weather("Tokyo")
fahrenheit = celsius_to_fahrenheit(weather["temperature_c"])
return format_answer(weather, fahrenheit)
```

这里下一步做什么，是程序员早就写好的。即使 `format_answer()` 内部调用了模型，整体路线仍然由代码决定。这样的系统更适合叫 Workflow。

Agent loop 的区别，不是代码里多了一个 `while`，而是**模型获得了有限的下一步决策权**：

```python
turn = model.generate(messages, available_tools)
```

模型可以决定“现在回答”“先查天气”“先做换算”。但别把“决策权”理解成“系统控制权”。它仍然只能从 Runtime 暴露给它的出口里选。

我习惯用一句话区分三者：

> **Model 提议下一步，Runtime 管理下一步，Tool 实现下一步。**

Runtime 像舞台监督，不负责演戏，却决定什么时候开场、哪个道具能上台、什么时候必须收工。模型像演员，可以根据现场情况做选择，但演员不能因为台词里写了“现在炸掉舞台”就真的获得炸药权限。

### 2.1 什么时候反而不该用 Agent

这个问题值得现在就说，因为很多教程会让人产生一种错觉：Agent 比 Workflow 更“高级”，所以能用 Agent 就尽量用 Agent。

实际工程里恰恰相反。如果下一步可以靠清楚的 `if/else`、状态机或固定流程决定，就优先使用确定性代码。它更容易测试、更容易估算成本，也更容易解释“为什么系统做了这一步”。

只有当任务确实需要模型理解开放语言、观察结果，并据此选择下一步时，Agent loop 才开始有价值。

换句话说，Agent 不是默认升级包，而是一种用复杂度换灵活性的工具。

---

## 3. ReAct：不要把它学成“打印 Thought”

你会经常看到 ReAct 这个词。它来自 Reasoning and Acting。历史上很多示例会写成：

```text
Thought: I need the weather first.
Action: get_weather
Observation: ...
Thought: Now I should convert the temperature.
```

这个形式帮助人理解，但工程实现里千万别误会成“Runtime 必须读取模型的隐藏思维链”。我们真正需要的是可观察、可校验的事件：模型请求了哪个 Tool、参数是什么、Tool 返回了什么、模型什么时候结束。

所以本章把 ReAct 理解成：

```text
Decision
   ↓
Action / Tool Call
   ↓
Application executes
   ↓
Observation
   ↓
Next Decision
```

如果 Runtime 依赖：

```python
if "Action:" in model_text:
    ...
```

那你的控制协议其实建立在标点符号上。模型少写一个冒号，系统就像门禁因为员工忘记说“芝麻开门”而彻底失灵。

结构化 Tool Call 的意义就在这里：我们让“动作请求”成为明确的数据，而不是一段需要猜格式的散文。

---

## 4. Runtime 先需要一套自己的“内部语言”

真实模型服务的响应对象往往很丰富。以某个 Provider 为例，你可能看到 `response.output`、`function_call`、`arguments`、`response.id` 等字段。

如果 Runtime 直接写：

```python
for item in response.output:
    if item.type == "function_call":
        ...
```

它当然能跑，但核心循环已经和某家 Provider 的 wire format 绑在一起了。以后字段变化，或者你接另一个 Provider，Runtime 也要跟着改。

我们先问一个更朴素的问题：**Runtime 真正需要知道多少？**

其实很少。

一个工具请求只需要：

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
```

一次模型决策则只有两种结果：

```python
@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
```

要么模型给最终文本，要么它给一个或多个 Tool Call。

### 4.1 为什么 `ModelTurn` 要强制二选一

本章的实现会检查：

```python
has_final = self.final_text is not None
has_calls = bool(self.tool_calls)

if has_final == has_calls:
    raise InvalidModelTurnError(
        "A model turn must contain exactly one of final_text or tool_calls"
    )
```

也就是说，不能两者都没有，也不能两者同时有。

真实 Provider 的输出形式可能比这复杂，但内部协议没必要照单全收。我们是在为 Runtime 设计一个容易推理的状态转移：

```text
ModelTurn(final_text=...)
    → 结束

ModelTurn(tool_calls=...)
    → 执行 → Observation → 下一轮
```

内部协议越清楚，Runtime 越容易测试。Adapter 的工作，就是把外部世界那些花花绿绿的字段翻译成这两种明确结果。

### 4.2 `call_id` 为什么要求唯一

`ToolCall` 还会检查 `call_id`、工具名和参数类型。Runtime 甚至会拒绝同一次 run 中重复出现的 `call_id`。

这是因为 Tool Call 和 Tool Output 的对应关系依赖这个 ID。重复使用同一个 ID，相当于快递公司给两件不同包裹贴同一个单号。简单例子里可能暂时看不出问题，等你开始有多轮调用，结果关联就会变得含糊。

---

## 5. Tool 不是“一个 Python 函数”这么简单

如果只写 Demo，我们可以准备一个字典：

```python
handlers = {
    "get_weather": get_weather,
    "convert": convert,
}
```

但只靠函数名还不够。模型需要知道这个能力是做什么的、参数长什么样；应用执行之前还需要验证参数。

所以本章的 `Tool` 把这几件事放在一起：

```python
@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments_model: type[BaseModel]
    handler: Callable[[Any], Any]
```

这四个字段刚好横跨两个世界。

给模型看的，是 `name`、`description` 和根据 `arguments_model` 生成的 JSON Schema。给应用执行的，是 `handler`。

### 5.1 为什么参数模型要在 Runtime 里再验证

我们用 Pydantic 定义天气工具参数：

```python
class WeatherArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: Literal["Tokyo", "Paris"]
```

然后 Tool 在真正调用 handler 前执行：

```python
arguments = self.arguments_model.model_validate(raw_arguments)
```

这里和 Stage 00 的思想一致：Provider 侧的 strict schema 能帮助模型生成正确结构，但**真正承担执行后果的是 Runtime**，所以 Runtime 仍然验证自己即将接收的参数。

这并不多余。想想 Web 开发：前端已经写了表单校验，后端还会不会校验？当然会。因为前端只是一个输入来源，真正写数据库的是后端。

### 5.2 `ToolRegistry` 到底解决什么

Runtime 不应该根据模型返回的任意名字去找 Python 函数，所以我们有一个 Registry：

```python
class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}
```

执行时只从已注册 Tool 中查找：

```python
tool = self._tools.get(call.name)
if tool is None:
    raise UnknownToolError(f"Unknown tool: {call.name}")
```

Registry 不是完整的权限系统，但它至少建立了一个很重要的事实：**模型只能请求应用明确提供的能力。** 模型生成 `delete_everything` 这个名字，并不会凭空让系统多出一个函数。

---

## 6. 现在来看 Runtime 的核心循环

完整实现位于 [`code/runtime.py`](code/runtime.py)。你可以先运行：

```bash
python stages/01-react-runtime/code/runtime.py
```

它使用一个确定性的 `ScriptedWeatherModel`，所以不需要 API Key。预期轨迹大概是：

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo's deterministic teaching record is 18.0°C (64.4°F), cloudy.
```

先别急着看所有类，我们沿着 `AgentRuntime.run()` 走一遍。

### 6.1 Runtime 先创建自己的运行记录

```python
messages: list[dict[str, Any]] = [
    {"role": "user", "content": user_input}
]
```

这个 `messages` 很重要，因为它明确说明“当前 run 发生过什么”。

模型第一次返回 Tool Call 后，Runtime 会把模型的动作请求记录下来：

```python
messages.append(
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [asdict(call) for call in turn.tool_calls],
    }
)
```

工具执行后，又追加 Observation：

```python
messages.append(
    {
        "role": "tool",
        "tool_call_id": call.call_id,
        "name": call.name,
        "content": observation,
    }
)
```

于是第二轮模型看到的不是“请继续猜”，而是一条明确轨迹：用户提了什么、模型请求过什么、程序实际返回了什么。

这里顺便澄清一个常见说法：“模型记住了上一轮。”从这个代码看，更准确的描述应该是：**应用把上一轮发生的事情放进下一轮输入，所以模型看到了它。**

### 6.2 每一轮只让模型做一次决定

循环中心是：

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(messages, self.registry.schemas())
```

如果模型给最终文本：

```python
if turn.final_text is not None:
    return RunResult(...)
```

如果模型给 Tool Call，就执行：

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

然后把结果放回 `messages`，进入下一轮。

注意 Runtime 并没有“替模型规划”。它只是维持规则：你可以回答，也可以请求已注册工具；请求工具以后，我来执行并把 Observation 给你；直到你回答或达到停止条件。

这就是 Runtime 控制权与模型决策权的区别。

### 6.3 一轮多个 Tool Call，不等于并发执行

`ModelTurn` 可以表示多个 `tool_calls`，但当前实现使用：

```python
for call in turn.tool_calls:
    result = self.registry.execute(call)
```

所以它们仍然按顺序执行。

这点非常容易被“parallel tool calls”几个字带偏。模型一次提出多个请求，只表示请求被一起产生；Runtime 是否并发执行，是另一件事。并发会牵涉共享状态、执行顺序、取消、部分失败等新问题，本章故意先保持同步顺序。

### 6.4 `max_steps` 到底数什么

如果模型永远不结束，Runtime 最后会：

```python
raise MaxStepsExceeded(
    f"The run did not finish within max_steps={self.max_steps} model turns"
)
```

这里的 `max_steps` 数的是**模型决策轮数**，不是 Tool 调用总数。因为一轮里可能有多个 Tool Call。

这个限制不是装饰参数。没有它，模型如果不停请求工具，Runtime 就会一直继续。无限 `while True` 在白板上很有自由精神，在真实账单里通常不太浪漫。

当然，`max_steps` 也不是万能预算。它不能等价于“最多花多少钱”或“最多运行几秒”。它只是本章最基本的停止边界。

---

## 7. 错误不要统统叫“Agent 出错了”

Agent 系统有一个特别容易养成的坏习惯：任何问题都描述成“模型没做好”。

但沿着刚才的调用链看，错误其实发生在不同层。

模型如果返回一个不符合内部协议的结果，是 `InvalidModelTurnError`。模型请求了 Registry 里没有的工具，是 `UnknownToolError`。工具参数没通过 Pydantic，是 `ToolArgumentsError`。参数合法，但 handler 自己执行失败，是 `ToolExecutionError`。

这些错误看起来都可能导致任务没完成，但责任完全不同。比如：

```text
UnknownToolError
    先检查模型是否请求了不暴露的能力，或 Tool 列表是否配置错误

ToolArgumentsError
    先检查参数 Schema、模型参数和应用输入边界

ToolExecutionError
    先检查真实 Python handler 或外部服务
```

把它们全吞进：

```python
except Exception:
    pass
```

不会让系统更健壮，只会让错误从“报出来”升级成“消失了”。

### 7.1 为什么本章 Tool 失败就停止

你可能想到另一种设计：Tool 失败后，把错误作为 Observation 再交给模型，让它改参数后重试。

这当然可以，而且很多系统会这么做。但一旦加入自动重试，就必须回答：这个动作能安全重复吗？已经产生了一半副作用怎么办？最多重试几次？

这些问题会迅速把一章基础 Runtime 拖进另一整套可靠性策略里。

所以本章选择一个容易推理的规则：**Tool 执行失败，本次 run 直接失败。** 这样你能准确知道 handler 执行了几次。先把简单语义弄明白，再谈更复杂的恢复策略。

---

## 8. 为什么先用 `ScriptedWeatherModel`，不直接上真实模型

如果你第一次测试 Runtime 就接真实模型，一旦轨迹不对，会遇到一个很烦的问题：到底是 Runtime 写错了，还是模型这次选择变了？

所以 `runtime.py` 里准备了一个确定性的模型替身：

```python
class ScriptedWeatherModel:
    ...
```

它没有语言智能，只按观察结果数量决定下一步：没有 Observation 时请求天气；有一次 Observation 时请求换算；有两次时返回最终答案。

这听起来“不智能”，但对于测试控制器来说恰恰是优点。我们希望输入一样，轨迹就一样。

这里 `Model` 定义成 Protocol：

```python
class Model(Protocol):
    def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        ...
```

只要对象满足这个接口，它可以是真实 Provider Adapter，也可以是 `ScriptedWeatherModel`。Runtime 不需要知道区别。

这是一种很重要的工程习惯：**测试控制逻辑时，尽量把模型随机性从测试里拿掉。**

---

## 9. 测试的重点不是“最后一句话对不对”

运行本章检查：

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

完整测试代码在 [`code/runtime_checks.py`](code/runtime_checks.py)。

先看成功路径。测试不仅检查最终答案里有 `64.4°F`：

```python
self.assertIn("64.4°F", result.answer)
```

还检查了 Tool Observation 的调用编号：

```python
self.assertEqual(
    [message["tool_call_id"] for message in tool_messages],
    ["call-weather", "call-convert"],
)
```

为什么要多此一举？因为 Agent 系统里“最终答案碰巧对了”和“执行轨迹正确”不是一回事。

想象一个系统本来应该先查数据库再回答，但模型凭空猜中了一次。如果测试只看最后字符串，它会通过；如果测试检查是否真的发生了 Tool Call，就会发现问题。

测试还故意制造了未知 Tool、非法参数、handler 报错、重复 `call_id` 和永不结束的模型。这些坏例子不是为了难为代码，而是为了把 Runtime 的边界变成可执行规则。

一条很实用的判断是：**如果你无法写出一个确定性的反例测试，那你可能还没说清楚这个 Runtime 到底承诺什么。**

---

## 10. 最后再接真实 Provider：Adapter 只做翻译

现在核心 Runtime 已经能离线工作，我们再把 OpenAI Responses API 接进来。

运行前配置：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

然后执行：

```bash
python stages/01-react-runtime/code/openai_runtime.py
```

完整代码在 [`code/openai_runtime.py`](code/openai_runtime.py)。

关键类是：

```python
class OpenAIResponsesModel:
    ...
```

它满足 `Model.generate(...) -> ModelTurn`，所以对 Runtime 来说，它和 `ScriptedWeatherModel` 没区别。

Adapter 做的事情大致是三种翻译：

```text
Runtime Tool schema
      ↓
OpenAI function tool

OpenAI function_call
      ↓
ToolCall

Runtime tool observation
      ↓
function_call_output
```

核心 Runtime 不需要 import Provider SDK，也不需要知道 `response.output` 里是什么对象。这就是 Adapter 的价值：不是“为了面向对象多写一个类”，而是把容易变化的外部协议挡在核心控制逻辑外面。

### 10.1 为什么 Adapter 保存 `previous_response_id`

第一次 Provider Response 如果包含 Tool Call，工具执行以后，下一轮需要继续同一条响应链。

Adapter 保存：

```python
self._previous_response_id: str | None = None
```

后续请求会带上：

```python
request["previous_response_id"] = self._previous_response_id
```

这样 Provider 可以理解“这次 Tool Output 是在继续上一轮”。

因此当前 `OpenAIResponsesModel` 实例实际上带有 run 级状态。教程会明确约定：**一个 Adapter 实例只服务一条 Runtime run。** 如果你拿同一个实例处理两个完全无关的用户任务，它可能把第二个任务接到第一个响应后面。

这不是“所有 Adapter 永远都必须这样设计”，只是当前代码的真实规格。高质量教程应该把这种限制说出来，而不是等读者踩到以后再解释。

### 10.2 为什么只发送“新的” Tool Output

Runtime 的 `messages` 保存整条轨迹。第二轮、第三轮以后，旧的 Tool Output 仍然留在里面。

如果 Adapter 每轮都把所有 Tool Output 重发，Provider 会再次收到之前已经提交过的结果。于是 Adapter 维护：

```python
self._submitted_tool_call_ids: set[str] = set()
```

只有新的 Tool Output 才进入下一次 Provider 请求。

这个细节看起来很小，其实正好说明 Provider Adapter 为什么值得单独存在：Runtime 关心的是“我有一条 Tool Observation”；Provider 关心的是“这个 Observation 用什么 wire format、是否已经提交过、怎样继续上一份 Response”。两边的问题不一样。

### 10.3 为什么真实示例关闭 parallel tool calls

Adapter 设置：

```python
"parallel_tool_calls": False,
```

不是因为 Runtime 永远只能处理一个 Tool Call，而是因为本章想让真实 Provider 示例保持单线、好观察。内部 `ModelTurn` 仍然允许多个 `ToolCall`。

这是教学代码很重要的一种取舍：**别为了展示“我什么都支持”而一次把所有复杂度打开。** 先让一条轨迹清楚，再扩展并发，比一开始就把失败顺序、共享副作用和取消语义全混进来更容易学明白。

---

## 11. 到这里，一个最小 Runtime 已经具备什么

现在回头看，Runtime 已经不只是“一个 while 循环”。它把几类职责放到了明确的位置：模型通过统一协议返回决策；Tool 有清晰的描述、Schema 和 handler；Registry 限制可调用能力；Runtime 维护运行记录并控制继续或结束；参数在执行前被验证；错误有明确类型；`max_steps` 防止无限决策；确定性模型替身让控制逻辑可以离线测试；Provider Adapter 把外部格式挡在核心循环之外。

这些东西组合起来以后，才算真正有了一个“小而完整”的 Agent Runtime。

但它仍然很小。当前实现同步、顺序执行 Tool；状态只存在当前进程内；Tool 失败直接结束；没有自动重试，没有并发调度，也没有额外的持久化机制。

这不是“还没来得及补的 TODO 列表”，而是本章的边界。先让读者清楚系统现在确切会做什么，比用一堆“生产级”“企业级”形容词包住 Demo 更有价值。

---

## 12. 用几个实验把 Runtime 真正拆开

读完代码后，最有效的练习不是再抄一遍，而是故意改变一个假设。

你可以让 `ScriptedWeatherModel` 在同一轮返回两个不同的 Tool Call，观察 Runtime 会按什么顺序执行。然后试着给两个调用使用相同的 `call_id`，看看内部协议在哪一步拒绝它。

也可以加一个第三个工具，比如 `describe_temperature`，把华氏温度分类成 `cold`、`mild`、`hot`。只修改 Tool 和模型替身，不要改 `AgentRuntime.run()`。如果为了多一个工具就必须改核心循环，那说明抽象还不够稳定。

再试一个更有意思的：让 handler 主动抛异常，然后思考“失败就终止”和“把错误作为 Observation 交给模型”两种设计有什么差别。别急着选一个“更高级”的答案，先问：如果 Tool 有副作用，自动重试会不会重复执行？

最后，尝试把 `max_steps` 改成 1。你会看到 Runtime 不是“模型想走几步就走几步”，而是模型决策始终被应用的执行预算包在外面。

---

## 13. 本章结束时，你应该能讲清楚一条完整轨迹

假设我现在问你：“东京教学天气是多少，并换算成华氏度？”

你应该能从程序角度讲出：用户输入进入 Runtime；Runtime 把消息和 Tool Schema 交给 Model；Model 返回 `ToolCall`；Runtime 用 Registry 找到 Tool；Pydantic 验证参数；handler 执行；结果被序列化成 Tool Observation；下一轮 Model 看见 Observation，再请求换算 Tool；第二个 Observation 返回；最终 Model 返回 `final_text`；Runtime 停止并返回 `RunResult`。

如果你能顺着这条轨迹解释每一步“谁拥有控制权”，那你已经理解了本章最重要的内容。

你不需要背“Agent = LLM + Tools + Memory + Planning”这种公式。真正有用的理解，是打开代码时知道：模型在哪儿做决策，应用在哪儿执行，状态在哪儿保存，错误在哪儿被挡住，循环在哪儿停止。

---

## 14. 本章代码

```text
stages/01-react-runtime/
├── README.md
├── README.zh-CN.md
└── code/
    ├── runtime.py
    ├── openai_runtime.py
    ├── runtime_checks.py
    └── requirements.txt
```

完整实现只维护在 `code/` 中；正文中的代码片段用于解释具体机制。
