# Stage 01：查完天气，还要换算温度——让 Agent 一步一步把任务办完

> Language: [English](README.md) | **简体中文**

[上一章](../00-foundations/README.zh-CN.md)，小林的出行练习页面已经能显示 Tokyo 的教学天气。模型提出查询申请，Python 读取本地记录，再把结果送回模型。这个过程里，18°C 来自一次真正的函数调用，而不是模型碰巧猜中了。

页面刚能用，小林又补了一句：“有些读者习惯看华氏度，能不能把查到的温度也换算一下？”要求不大，却刚好碰到了上一版程序的边界：它只安排了一次查询，第二次模型调用就必须给答案。现在查完记录以后，还需要做一次计算。助手还没办完事，程序却已经准备下班了。

这一章就沿着这项要求往前走。先弄清怎样让程序继续，再为每一次继续定好规则；等天气查询、温度换算和最后回答能接起来，再试试小林不需要换算、甚至只打招呼的情况。我们要做的是让同一个控制程序容纳不同长度的任务，而不是为每一种情况再复制一套 API 调用。

## 1. 新要求多了一步，真正变化的是什么？

先不用想类和框架，只在纸上替小林办一次事。拿到请求时，我们知道城市，却还没有天气记录；查询返回 18.0°C 后，才有了换算的输入；算出 64.4°F 后，才凑齐回答所需的两种单位。沿途获得的信息不同，下一步能做的事也不同。

```text
小林：读取 Tokyo 的教学天气，并调用换算工具给出华氏度
    ↓
第一次决定：先查记录       → Python 返回 18.0°C、多云
    ↓
第二次决定：把 18.0°C 换算 → Python 返回 64.4°F
    ↓
第三次决定：材料齐了，回答 → 本次任务结束
```

这里有两次工具执行，却有三次决定。最后回答也占一次决定，只是它不再要求工具。如果小林只问摄氏温度，查询以后就可以回答；如果只是打招呼，第一轮直接回答就够了。因此需要改变的不是“固定安排三轮”，而是“每轮办完后，再判断该继续还是结束”。

当然，如果产品永远只有“查天气、换算、显示”这条固定路线，普通 Python 顺序调用两个函数就很好，没有必要请模型为每一行代码主持会议。我们现在研究另一种安排：允许模型结合请求和已经拿到的结果，提出下一步。它增加了灵活性，也增加了检查这些提议的责任，不能把它当成免费的升级。

**Runtime（运行时）** 在这里可以先理解成负责组织这段工作的程序。它询问下一步、检查工具申请、执行函数、记下结果，再决定是否需要询问下一轮。模型负责提出选择，工具负责具体工作，运行时负责把整个过程接住。先记住这三份工作，后面的类名只是给它们安放位置。

不过，程序要判断“继续还是结束”，不能靠猜模型一句话的语气。我们先给双方约定两种明确的回复。

## 2. 助手每次回来，要交申请，还是交答案？

如果模型返回“我想先看看天气”，人能理解它的意思，程序却还不知道应该调用哪个函数、传哪个城市。这正是上一章工具调用要解决的问题：把动作申请变成可检查的数据。现在我们把这种申请放进一个 Python 数据对象，便于运行时统一使用。

[`runtime.py`](code/runtime.py) 中的 `ToolCall` 保留三项信息：

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
```

`name` 是工具名，`arguments` 是参数字典，`call_id` 是这一次调用的关联编号。`@dataclass` 帮我们生成初始化方法等常用代码；`frozen=True` 不允许重新赋值这些字段，但并不会把里面的字典也变成不可修改的对象。类型注解说明预期形状，实际检查由类里的 `__post_init__()` 执行，比如调用编号不能空，参数必须是字典。

于是，“查 Tokyo”可以明确表达成：

```python
ToolCall("call-weather", "get_teaching_weather", {"city": self.city})
```

这里的 `self.city` 来自示例配置，默认是 `Tokyo`。这个对象仍然只是申请，不会因为创建了它就查到天气。它既没有调用处理函数，也没有取得查询结果。

模型也可能回来直接交答案。为了让运行时分清两种情况，我们用 `ModelTurn` 表示一次决定；控制流程只需要看下面两个字段：

```python
@dataclass(frozen=True)
class ModelTurn:
    final_text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
```

`final_text` 是最终文字，`None` 表示这轮还没有最终答案；`tool_calls` 是这一轮提交的工具申请，空元组表示没有申请。本章规定两者只能选一种：既不申请也不回答，程序无事可做；一边说“任务结束”，一边又要求执行工具，程序也不知道该听哪一句。

这条约定由下面的条件检查：

```python
has_final = self.final_text is not None
has_calls = bool(self.tool_calls)
if has_final == has_calls:
    raise InvalidModelTurnError("Return either final_text or tool_calls, not both or neither.")
```

两个布尔值相等，意味着两者都有，或者两者都没有，因此都拒绝。最终文字还必须是非空字符串。这不是声称每个模型接口都只能这样返回，而是应用为自己的控制程序选了一个简单、明确的内部约定。真实服务返回得更丰富时，会在接入处转换。

现在我们能读懂助手本轮要什么了。下一个问题随之出现：到了第二轮，它从哪里知道上一轮已经查到了 18°C？

## 3. 给下一轮带上一份工作记录

把查询结果存进当前 Python 变量，不会自动让远端模型看到它。就像同事上次打完电话，不会自动知道你挂电话之后又查了哪些资料。每次请它继续，都需要带上足够的经过：原来要做什么，已经申请过什么，实际拿回了什么。

运行时用 `messages` 保存这份记录。一次新任务开始时，只有小林的请求：

```python
messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
```

这里的 `role` 不是人物性格，而是消息来源：`user` 表示用户请求，`assistant` 表示模型回复，`tool` 表示应用执行工具后记录的结果。这是本章的内部表示，不要求和某个服务的网络格式完全相同。

第一次查询完成后，记录中会有下面三类内容。为看清关系，这里省去完整 JSON 的标点，只写出关键数据：

```text
user       读取 Tokyo 教学天气，并换算为华氏度
assistant  call-weather → get_teaching_weather({"city": "Tokyo"})
tool       call-weather → {"temperature_c": 18.0, "condition": "cloudy", ...}
```

为什么连申请也要留着？因为仅有一个 `18.0`，既不知道它是什么单位，也不知道来自哪个动作。保留工具名、参数和关联编号，才能把结果放回当时的问题里。上一章的 `call_id` 到了多轮流程中仍在发挥相同作用：申请和回执通过同一个编号配对，不能随手换成另一个编号。

这份记录由应用维护。下一次模型调用看到它，才有机会根据查询结果继续；所谓“模型记住了”，在这里实际是应用重新提供了相关记录。整个列表仍在当前进程内，退出程序后不会自动保存，也不能据此宣称已经有跨会话记忆。

我们会把记录的副本交给模型接口，避免普通适配代码不小心修改运行时持有的原记录。这是对象之间的数据管理，不是安全隔离：同一进程中的恶意 Python 代码并不会因此失去访问内存的能力。

工作记录有了，还需要能真正产出记录里的数值。现在回到小林新加的那项要求，把换算工具准备好。

## 4. 两项工具各做一件小事

天气工具继续使用上一章的固定记录：Tokyo 是 18.0°C、多云，Paris 是 12.0°C、小雨。它返回城市、摄氏温度、天气状况，以及 `source="fixed teaching record"`。这是教学数据，不随今天的真实天气变化。

换算工具则根本不用理解自然语言。摄氏温度乘以 `9/5`，再加 `32`，就是华氏温度；示例把结果保留一位小数。模型需要做的只是把查到的摄氏数值交过来，计算交给普通函数：

```python
def celsius_to_fahrenheit(arguments: TemperatureArguments) -> dict[str, float]:
    converted = round(arguments.temperature_c * 9 / 5 + 32, 1)
    return {"temperature_f": converted}
```

`TemperatureArguments` 不是新的模型服务，它是 Pydantic 定义的输入形状。沿用上一章的思路，我们先说明函数能接受什么，再调用它：

```python
class TemperatureArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    temperature_c: float
```

`temperature_c` 必须是数值；`strict=True` 不会把字符串 `"18"` 当成已经合格的数字；`extra="forbid"` 拒绝额外字段；`allow_inf_nan=False` 排除无穷大和 NaN。这里的浮点字段可以接受整数 `18`，并不要求输入一定写成 `18.0`。严格验证是按具体类型定义的规则，不是“所有类型都只能逐字相同”，可对照 [Pydantic 的严格模式说明](https://docs.pydantic.dev/latest/concepts/strict_mode/)。

天气参数的规则更简单：`city` 只能是 `Tokyo` 或 `Paris`。查询和换算有不同的参数约定，但运行时不必为它们写两个特殊分支。每项工具把说明、参数模型和处理函数放在一起：

```python
Tool(
    name="celsius_to_fahrenheit",
    description="Convert a supplied numeric Celsius value to Fahrenheit.",
    arguments_model=TemperatureArguments,
    handler=celsius_to_fahrenheit,
)
```

这里的 `handler` 就是真正干活的函数。发给模型的是名字、用途和从参数模型生成的 JSON Schema，不是函数对象。应用则持有函数对象，等检查通过后再调用。这仍是上一章工具的两面，只是现在有两项能力需要统一管理。

我们用 `ToolRegistry` 保存应用明确登记的工具。它首先解决一个朴素问题：模型说了一个名字，程序究竟去哪里找？答案不能是全局函数表，更不能是 `eval()`。只查这份登记表：

```python
def prepare(self, call: ToolCall) -> tuple[Tool, BaseModel]:
    tool = self._tools.get(call.name)
    if tool is None:
        raise UnknownToolError(f"Unknown tool: {call.name}")
    return tool, tool.validate(call.arguments)
```

返回值是“找到的工具”和“验证后的参数”。此时仍未执行函数。重复登记同名工具也会被拒绝，避免一个名字背后到底对应谁变得含糊。登记表限制了可调用能力，却不是完整的用户权限系统；它也不会判断“模型是否选对了当前用户要的城市”。参数合法和任务做对，是两种不同的检查。

经过这些准备，控制程序终于可以不关心具体的天气和换算细节，只负责让申请走完检查、执行和回传。接下来把这几步接成循环。

## 5. 把一轮做清楚，再让它重复

先看循环的入口。`Model.generate()` 接收工作记录和工具说明，返回刚才约定的 `ModelTurn`：

```python
for step in range(1, self.max_steps + 1):
    turn = self.model.generate(deepcopy(messages), self.registry.schemas())
```

`step` 是本次任务第几次询问模型，`max_steps` 是最多允许询问多少次。`schemas()` 只取工具说明，`deepcopy(messages)` 给出当前记录的独立副本。运行时还检查返回对象确实是 `ModelTurn`，不会把一个普通字符串误当成完整的决定。

先处理最容易理解的分支：模型交来了最终文字。运行时把它记下来并返回 `RunResult`。下面是返回结果的部分：

```python
return RunResult(
    answer=turn.final_text,
    model_turns=step,
    messages=tuple(deepcopy(messages)),
    tool_executions=tool_executions,
)
```

结果既有答案，也有轮数、实际进入处理函数的次数和工作记录。`return` 会离开整个 `run()`，不是只结束当前一轮。这保证模型已经交答案时，程序不会还在下面继续调用工具。

另一种分支是模型提交工具申请。运行时先把申请加入 `messages`，检查调用编号和预算，再准备参数；全部准备好后，逐个执行。真正执行和保存结果的核心部分是：

```python
observation = tool.execute(arguments)
messages.append({
    "role": "tool", "tool_call_id": call.call_id,
    "name": call.name, "content": observation,
})
```

`observation` 是已经执行出来的结果，不是模型预计会得到什么。`Tool.execute()` 调用处理函数，再把返回值编码成 JSON 文本。它使用 `allow_nan=False`，也没有使用 `default=str` 把任意 Python 对象硬凑成字符串。处理函数返回一个无法表达成 JSON 的对象，会明确失败，而不是把类似 `<object at ...>` 的文字交给模型充当答案。

这一轮没有 `return`，所以循环回到入口；这次 `messages` 已经多出刚才的申请和结果。第二轮拿到 18.0 后，可以提出换算；第三轮拿到 64.4 后，可以回答。控制程序没有写“第二轮必须换算”，它只是重复同一条规则。

这种用动作取得信息，再据新信息继续决定的方式，借鉴了 **ReAct** 的思路。[ReAct 原论文](https://arxiv.org/abs/2210.03629)研究了推理与动作交替进行。本章使用结构化工具调用来实现其中可执行、可观察的循环，并不是完整复现论文的提示格式。程序不需要寻找文本里的 `Thought:` 或 `Action:`，也不读取隐藏思维链来决定能否执行。

到这里，循环的职责已经说清楚了。先让一个按剧本办事的替身走一遍，看看我们有没有把线接错，再换真实模型。

## 6. 先排练一次，确认 18 是怎样走到换算工具里的

模型服务的真实回复会变化。第一次检查循环时，如果结果不对，我们希望先排除一个干扰：是控制程序没把结果传好，还是模型选了另一条路？因此，离线入口使用 `ScriptedWeatherModel`。它不是悄悄替代真实服务，而是明确的测试替身。

这个替身按 `--task` 和 `--city` 配置工作，不会理解任意自然语言。它看到没有天气结果，就申请查询；需要换算而还没有换算结果，就申请计算；材料齐全就回答。其中把天气结果交给换算工具的部分是：

```python
if self.task == "convert" and conversion is None:
    return ModelTurn(tool_calls=(
        ToolCall(
            "call-convert", "celsius_to_fahrenheit",
            {"temperature_c": weather["temperature_c"]},
        ),
    ))
```

关键不是 `call-convert` 这个名字，而是输入取自 `weather["temperature_c"]`，没有在第二轮偷偷写死 `18.0`。最后一句话里的城市、摄氏温度和天气状况也从观察结果读取。把记录改掉，后面的输入和答案应该一起变，而不是演一出查了资料却继续念预设台词的戏。

从仓库根目录安装依赖，然后运行。使用 Python 3.10 及以上版本；这条离线路径需要 Pydantic，不需要模型密钥：

```bash
python -m pip install -r stages/01-react-runtime/code/requirements.txt
python stages/01-react-runtime/code/runtime.py
```

程序开头会明确显示 `offline model double: no API request`。默认轨迹为：

```text
[1] ACTION  get_teaching_weather({'city': 'Tokyo'})
[1] OBSERVE {"city": "Tokyo", "temperature_c": 18.0, "condition": "cloudy", "source": "fixed teaching record"}
[2] ACTION  celsius_to_fahrenheit({'temperature_c': 18.0})
[2] OBSERVE {"temperature_f": 64.4}
[3] FINAL   Tokyo 的教学记录：18.0°C / 64.4°F，多云；这不是实时天气。
model_turns=3, tool_executions=2
```

再加 `--show-transcript`，就能看到用户消息、两次申请、两次回执和最后回答。输出的是应用观察到的动作，不是模型内心独白。注意第一轮只有申请和查询结果，第二轮才把这个结果作为参数；这种前后依赖，才是这次排练真正要观察的东西。

同一条线路能跑通以后，小林又问：如果这次不换算，程序会不会仍然自作主张再算一次？

## 7. 任务短一点，循环就应该早点结束

先用同一份运行时处理“只查天气”和“只打招呼”：

```bash
python stages/01-react-runtime/code/runtime.py --task weather
python stages/01-react-runtime/code/runtime.py --task greet
python stages/01-react-runtime/code/runtime.py --city Paris --language en
```

只查天气时，第一轮查询、第二轮回答；打招呼时，第一轮就结束，工具一次也不执行。最后一条仍然要求换算，只是换成 Paris 和英文回答，应该得到 `12.0°C / 53.6°F`，而不是一边写 Paris，一边继续报东京的温度。

| 排练任务 | 决定轮数 | 工具执行次数 |
| --- | ---: | ---: |
| 打招呼 | 1 | 0 |
| 只查天气 | 2 | 1 |
| 查天气并换算 | 3 | 2 |

变化发生在替身提出的决定里，`AgentRuntime.run()` 没有为三种任务换三套循环。真正接入模型后，也使用同一个入口契约。Python 用 `Protocol` 描述这份约定：

```python
class Model(Protocol):
    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelTurn: ...
```

先把它读成“这个对象要能提供一个 `generate` 方法”即可。`...` 在这里表示接口声明，没有实际方法体；不是需要读者补齐的示例步骤。真实模型适配器和测试替身都提供这个方法，循环就能调用它们。类型注解帮助开发者检查接口，不会自动验证网络回复，所以前面的运行时检查仍然必要。

但是，能够灵活继续还不够。如果助手永远说“我再查一下”，小林就永远等不到页面上的一句话。下一步，我们要给“继续”一个尽头。

## 8. 没办完时，要停在哪里、留下什么？

最容易理解的上限，是最多让模型决定几轮。故意把三轮任务的额度减到两轮：

```bash
python stages/01-react-runtime/code/runtime.py --max-steps 2 --show-transcript
```

你会看到天气已经查到，64.4°F 也已经算出，但随后得到 `MaxStepsExceeded`，进程以退出码 1 结束。这里不是计算失败，而是没有额度再问第三轮模型，也就没有最终回答。运行时不会把最后一份工具结果冒充模型已经回答，也不会偷偷追加一轮来“把演示做漂亮”。

已经成功的两次工具观察仍保留在异常对象的 `messages` 中，`--show-transcript` 会把它们打印出来。停止意味着不继续执行，不意味着时间倒流：前面发生过的查询和计算仍然发生过。换成会写文件的工具时，同样不能以为抛异常就撤销了文件写入。

轮数和工具次数还不完全相同。模型一轮可能提交两项申请；只限制轮数，不能单独表达“总共最多运行一个工具”。因此本例另设 `max_tool_calls`，在任何一批工具开始前检查：

```python
if tool_executions + len(turn.tool_calls) > self.max_tool_calls:
    raise ToolBudgetExceeded("This batch would exceed the tool-call budget.")
```

运行 `runtime.py --max-tool-calls 1` 时，天气查询可以发生，第二轮的换算申请会被拒绝。这个计数在进入处理函数前增加，因此处理函数执行失败也算一次尝试；参数检查没通过则不计为执行。同一轮的一整批申请如果会超限，就整批不启动，不会随意挑前半批来做。

这些上限数的是次数，不是运行秒数。一个 Python 函数卡住，并不会因为 `max_steps=3` 就在三秒后被终止；同样，三次模型请求花多少钱取决于具体服务和输入输出。这一版只提供明确的轮数与工具次数边界，不承诺总时长、总费用或任意代码的隔离。

上限解决“做太久”，接下来还要处理“申请本身就不对”。这两种情况都让任务停下，但不能混成同一个原因。

## 9. 申请错了和工具坏了，不是同一种失败

先假设模型申请 `move_the_moon`。登记表里没有这个能力，应该在查表时得到 `UnknownToolError`，任何处理函数都不执行。再假设它申请的是天气工具，却写 `city="Atlantis"`，这回名字对了，参数不对，会得到 `ToolArgumentsError`。这和工具真的连接数据源后失败，是不同位置的问题。

本章在接到一批申请后，先把整批名字和参数准备好：

```python
prepared = [self.registry.prepare(call) for call in turn.tool_calls]
```

只有这一行全部成功，才进入执行循环。这样，第一项参数合法、第二项参数明显错误时，不会先执行第一项再发现第二项根本不能接受。不过，这不构成事务：如果两项都通过检查，第一项执行成功，第二项在运行中失败，第一项已经产生的结果仍然保留，第三项不会再启动。我们没有自动撤销，也没有自动重试。

工具处理函数失败时，`ToolExecutionError` 报告失败边界，并保留原异常作为原因，供受控调试使用；终端提示不会直接拼接原始异常中的任意内容。模型接口返回不完整响应或调用失败，则由适配器报告 `ProviderResponseError`。这使“程序没拿到完整回复”和“函数运行失败”不必都被诊断成“模型今天心情不好”。

还有一种不起眼的错误是重复调用编号。本章要求一次运行内每份申请有不同的 `call_id`。上一轮用了 `call-weather`，这一轮又把它用作新申请，会被拒绝。反过来，相同工具和参数配上新编号，本章允许再次执行，并继续消耗预算。编号检查只解决结果关联的歧义，不负责识别业务上是否重复，更不提供幂等保证。

同一轮多个调用也不表示并发。代码使用普通 `for` 循环逐一执行；这一批返回值一起记好后，模型才有下一次决定。更重要的是，**同一批请求的参数是在任何一个结果返回之前就生成的**。因此不能把“先查天气”和“使用未知查询结果换算”塞在同一批，然后期待运行时自动把 18 填进后一个请求。它没有实现变量引用或参数替换。依赖前一步结果时，先得到观察，再提下一次申请。

最后别忘记上一章的区别：格式和结构都对，内容仍可能错。换算参数是一个合法的 `99.0`，不代表它就是刚查到的温度；模型直接回答一个错数字，也可能完全符合 `ModelTurn` 的形状。通用运行时不会自动证明所有数据的来源或所有句子的正确性。我们能检查流程边界，任务是否做对仍要结合请求和实际轨迹判断。

排练到这里，控制程序该接什么、拒绝什么已经比较清楚。现在把按剧本工作的替身换成真实 DeepSeek，让它根据请求决定下一步。

## 10. 换成真实模型，循环不用重写

上一章直接使用 DeepSeek Responses API。这里继续使用同一个接口，但把它放进 [`DeepSeekResponsesModel`](code/deepseek_runtime.py)，让它提供 `generate(messages, tools)`。这种把一边的格式转换成另一边格式的小层，叫作 **Adapter（适配器）**。它像翻译，负责传达意思，不负责替工具查天气。

一次调用主要做两件事：把内部工作记录转换成服务需要的输入，把服务回复转换成 `ModelTurn`。发送的核心字段如下：

```python
request = {
    "model": self.model,
    "instructions": self.instructions,
    "input": self._to_deepseek_input(messages),
    "tools": [self._to_deepseek_tool(tool) for tool in tools],
    "tool_choice": "auto",
    "max_output_tokens": 4096,
}
```

与上一章固定一次工具往返不同，这里的 `tool_choice="auto"` 让模型可以回答，也可以请求工具。应用规则要求先读取教学记录；需要华氏度时，再把观察到的摄氏值交给换算工具；只打招呼则不查询。规则帮助模型选择，但不是程序保证它永远选对。收到的每项申请仍要经过运行时检查。

服务回复的 `status` 必须是 `completed`；不完整响应里的部分调用不会被执行。函数参数先从 JSON 字符串解析为字典，再构造 `ToolCall`。适配器拒绝重复 JSON 字段、非对象参数、异常调用编号等情况，不把解析不清楚的东西送入执行层。

如果同一回复既有说明文字，又有工具申请，本章把它视为“仍需执行”的一轮，不把那段文字当作最终答案。没有工具申请且确实有非空文字时，才转换为 `final_text`。这解释了前面内部“二选一”的约定如何容纳外部更丰富的回复。

### 10.1 下一次请求，仍然带上原来的经过

DeepSeek 当前的 [Responses 兼容性说明](https://api-docs.deepseek.com/zh-cn/guides/responses_api/)明确要求客户端在多轮请求中携带历史；不能依靠 `previous_response_id` 从服务端续接。这和 Stage 00 的处理一致，适配器每次都从本次运行的 `messages` 构建输入，不另存一份跨任务共享的响应编号。

模型输出可能带有续接需要的额外项目，所以适配器不仅提取工具调用，还保留完整的原始输出项：

```python
provider_items = tuple(item.model_dump(mode="json", exclude_none=True) for item in output)
```

这些项目附在产生它们的那轮记录里。`ModelTurn` 除了控制用的两个字段，还用 `provider_items` 承载这份协议数据；运行时把它带着走，不根据其中的推理文字选择工具。下一轮由适配器原样转回输入。我们没有为了一个简化内部表示而丢掉服务续接信息，也不在普通终端记录里展示推理内容。

工具观察则被转换成服务要求的回执：

```python
items.append({
    "type": "function_call_output",
    "call_id": message["tool_call_id"],
    "output": message["content"],
})
```

第二次请求因此包含“用户请求、第一次模型输出、天气结果”；第三次再包含换算申请和换算结果。每次都在同一份工作记录上增加内容，而不是只发送一句“继续”。也正因为数据跟着当前运行走，同一个适配器被顺序用于两项独立任务时，不会自动把前一项的历史混进去。

当前 DeepSeek 会忽略 `parallel_tool_calls` 和服务侧 `max_tool_calls` 参数，所以代码没有把它们当执行限制。前面的 `max_tool_calls` 是我们自己在 Python 中检查的；不要因为两个参数名字相同，就以为保证来自同一层。[函数调用接口说明](https://api-docs.deepseek.com/zh-cn/api/create-response/)也要求应用在调用函数前验证参数。

### 10.2 接上服务，再观察一遍相同任务

在当前终端配置密钥和账户可用的模型。以下模型名是示例，需要与你的账户和当前服务支持一致；密钥不要写进源文件：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/01-react-runtime/code/deepseek_runtime.py --show-transcript
```

PowerShell 写法为：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/01-react-runtime/code/deepseek_runtime.py --show-transcript
```

客户端仍从 `openai` 包导入，但 `base_url="https://api.deepseek.com"` 决定请求发送给 DeepSeek。它设置了 `timeout=30.0` 和 `max_retries=0`，避免 SDK 的自动重试把一次显式请求变成多次尝试；这个客户端超时不是整个 Agent 任务的总截止时间。

这一入口会显示 `live DeepSeek: API usage applies`，需要网络并产生服务用量。缺少配置或 SDK 时会报错，不会悄悄退回离线替身。`--city Paris`、`--task weather`、`--task greet` 和 `--language en` 同样可用，它们改变发给真实模型的请求。

不要要求真实模型逐字复述离线脚本，也不要预先宣布它必定恰好三轮。观察它实际调用了什么、换算参数是否来自查询、最终数字是否一致。如果它多查了一次，运行时会如实记录和计数；如果它直接答错，运行时不会替它补画两次没有发生的调用。如果查询成功后第二次模型请求失败，异常记录里仍有查询结果，但本次任务没有最终答案。

现在我们既能控制流程，也能看到模型如何使用它。最后再用几次小实验，确认这些不是只在默认例子里碰巧成立。

## 11. 把“应该如此”变成能运行的检查

最值得检查的不只是最后字符串里有没有 `64.4`。还要检查第二次申请带入的参数，是不是第一次查询返回的温度。比如把 Tokyo 的固定记录临时改成 22.0°C，后续应该使用 22.0，并得到 71.6°F；如果最终仍报 18.0，说明程序只是读了一遍资料，却没真正使用它。

[`runtime_checks.py`](code/runtime_checks.py) 就包含这个实验，还检查 Paris、仅查询、仅问候、整批参数错误、重复编号、处理函数失败、次数耗尽和真实接口适配。关于小林的默认任务，检查会直接取出第二次申请：

```python
call = result.messages[3]["tool_calls"][0]
self.assertEqual(call["arguments"], {"temperature_c": 18.0})
self.assertEqual(result.messages[4]["tool_call_id"], call["call_id"])
```

两项检查分别验证参数传递与回执配对。它们不是对模型智能的评分，而是对这条执行线路的检查。适配器的伪客户端测试会检查后续请求确实包含前面的申请、结果和协议项目；可选的 SDK 测试使用模拟 HTTP，不会向真实服务发送请求。

运行：

```bash
python stages/01-react-runtime/code/runtime_checks.py
```

测试中还有一个故意保留的反例：模型不调用工具，直接回答“99 度”，运行时能够正常返回这段非空文字。这个检查不是奖励乱答，而是提醒我们不要夸大保证：运行时让过程可组织、可拒绝、可观察，并不自动验证每一句最终答案。

读完后可以再让小林提出一项新要求：“只查 Paris，不换算。”先预测会有几轮、几次工具，再运行观察。接着把工具预算改成零，分别执行问候和天气任务。前者应该正常结束，后者应该在工具执行前停止。能够解释为什么两条结果不同，比背出每个类名更接近真正理解这段程序。

## 12. 助手能继续了，但每一步都需要它决定吗？

回到小林的页面，我们已经把一条固定的“查询一次再回答”扩展成了一个有边界的过程。它能多走一步，也能早点结束；参数不对就不开始，工具出错就不冒充成功；每轮依据的结果留在记录里，真实模型和测试替身使用同一个控制程序。

小林这时又提出一个很实际的问题：“页面上已经有一个‘同时显示华氏度’的开关。既然开关都确定了，为什么还要每次问模型要不要换算？”这个问题并不否定刚写出的循环。它提醒我们：允许模型选择，和所有选择都值得交给模型，是两件事。

下一章就从这里继续：[Stage 02：别让模型什么都决定——Workflow、Routing 与 Planning](../02-workflows-routing-planning/README.zh-CN.md)。
