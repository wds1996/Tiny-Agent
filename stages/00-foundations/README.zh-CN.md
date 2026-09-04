# Stage 00：从一次模型调用开始，搭好 Agent 的地基

> Language: [English](README.md) | **简体中文**

很多 Agent 教程一开场就端上框架、插件、记忆、工作流和多智能体，像是刚学会切菜，就被要求独立承办满汉全席。本章先把锅放稳：**一次普通的大模型调用究竟发生了什么？**

我们会沿着一条连续的因果链前进：

```text
让模型生成文字
        ↓
让程序稳定地读取模型结果
        ↓
让模型请求一个外部工具
        ↓
由应用执行工具，并把结果送回模型
```

学完本章，你不会得到一个“无所不能的 Agent”，但会得到更重要的东西：一套不会轻易混淆的边界。

> **模型负责生成提案；应用程序负责验证、执行和承担后果。**

模型说“邮件已发送”，不等于邮件真的发出；模型返回一段合法 JSON，也不等于里面的事实正确。它可以提出动作，但不能靠语气坚定获得系统权限。

本章完整可执行代码只保存在 [`code/`](code/) 中。正文会按照知识点展示局部代码片段，帮助你理解每个机制；不会把整份源文件重复粘贴一遍。需要通读或运行时，请直接打开对应文件。

---

## 1. 学习目标

完成本章后，你应该能够：

- 解释 Python 程序、模型服务和响应对象分别负责什么；
- 区分 `instructions`、`input` 与一次调用中的上下文；
- 说明为什么自然语言适合给人读，却不适合作为稳定的程序接口；
- 使用 Pydantic 定义 Structured Output（结构化输出）；
- 区分“语法正确”“结构正确”和“事实正确”；
- 解释 Tool schema、Tool Call、Python 处理函数和 Tool Output 的关系；
- 说明 `call_id` 与 `previous_response_id` 分别关联什么；
- 在执行模型提出的工具请求前，完成名称、参数和允许范围检查。

本章只要求你具备基础 Python 能力：能看懂函数、字典、异常和命令行即可。

---

## 2. 准备运行环境

本章使用 Python 3.10 或更高版本、OpenAI Python SDK 与 Pydantic。请在仓库根目录执行：

```bash
python -m pip install -r stages/00-foundations/code/requirements.txt
```

然后配置 API Key 与模型名称：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_MODEL="your-model-id"
```

不要把 API Key 写进源代码或提交到 Git。示例也没有硬编码某个模型名称，因为模型目录与项目权限会变化。显式要求 `OPENAI_MODEL`，可以让配置问题在程序启动时立即出现，而不是在教程进行一半时突然上演“模型去哪儿了”。

三个示例都使用相同的环境变量检查函数：

```python
def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()
```

这是一条很普通但很重要的工程原则：**尽量在输入边界处暴露错误。**

---

## 3. 第一次模型调用：把模型当作远程计算服务

运行：

```bash
python stages/00-foundations/code/first_llm_call.py
```

完整代码位于 [`code/first_llm_call.py`](code/first_llm_call.py)。核心调用如下：

```python
response = client.responses.create(
    model=model,
    instructions=(
        "You are a patient programming teacher. Explain the idea accurately, "
        "use one concrete analogy, and avoid unexplained jargon."
    ),
    input=(
        "In no more than 120 words, explain why a language model response is "
        "a proposal produced by a model rather than an action performed by my "
        "Python program."
    ),
)
```

从应用程序视角看，这次调用是一个清楚的请求—响应过程：

```text
Python 构造请求
      ↓
模型服务根据输入生成输出
      ↓
SDK 返回 Response 对象
      ↓
Python 检查并使用结果
```

这里有两个行为主体：

- **模型服务**负责根据上下文生成输出；
- **应用程序**负责发起请求、读取结果、执行函数和改变外部世界。

它们不能混为一谈。模型像一位隔着玻璃办公的聪明同事：你把材料递进去，它可以给出建议；至于是否开门、是否操作真实系统，钥匙仍在程序手里。

### 3.1 模型会生成内容，但不会自动获得外部能力

一次普通文本调用不会自动：

- 读取你没有提供的本地文件；
- 查询私有数据库；
- 获取实时天气；
- 发送邮件；
- 修改订单；
- 证明它生成的事实一定正确。

如果输出中出现“订单已取消”，唯一可以确认的是：响应里出现了这几个字。订单系统是否发生变化，要看应用有没有执行真实操作。

### 3.2 概率生成意味着什么

语言模型不是传统意义上的纯函数。同一输入重复调用，措辞和细节可能不同。由此得到两条直接结论：

1. 不要让关键程序逻辑依赖某句话必须逐字出现；
2. 程序必须读取的内容，应尽量通过结构化契约表达和验证。

Agent 工程不是消灭不确定性，而是把不确定性限制在合适的位置。

### 3.3 `instructions` 与 `input` 不是同一个东西

可以先这样理解：

```text
instructions
    应用希望模型遵守的行为与回答要求

input
    当前这次调用真正需要处理的任务或数据
```

不要把所有来源都拼成一条巨型字符串：

```python
prompt = policy + user_question + documents + tool_result
```

这种写法短期很省事，长期会失去来源边界。程序很难再回答：哪部分是应用规则？哪部分是用户输入？哪部分只是外部文档中的数据？

本章先采用一个足够实用的定义：

> **Context（上下文）是某次模型调用实际能够看到的全部输入。**

`instructions` 和 `input` 都会进入上下文，但上下文不等于长期存储，也不只是一个叫作“Prompt”的字符串。

### 3.4 Response 不是一段裸字符串

示例先检查状态和文本：

```python
if response.status != "completed":
    raise RuntimeError(f"The response did not complete: {response.status}")
if not response.output_text.strip():
    raise RuntimeError("The response completed without text output.")
```

随后才读取：

```python
print(response.output_text)
```

`output_text` 是 SDK 提供的便捷文本视图。完整 `response` 还可能包含：

```text
Response
├── id
├── status
├── model
├── output items
├── output_text
└── usage
```

“请求没有抛异常”和“应用得到可用结果”并不是同一件事。显式检查可以阻止空结果继续流入后面的代码，避免它在十公里外才摔倒。

### 3.5 Token 用量不是质量评分

示例读取使用量：

```python
usage = response.usage
if usage is not None:
    print("input_tokens:", usage.input_tokens)
    print("output_tokens:", usage.output_tokens)
    print("total_tokens:", usage.total_tokens)
```

Token 数量有助于估算上下文规模、延迟和成本，但不能证明答案正确。输出更长，有时只是模型把同一个错误解释得更有耐心。

现在我们已经能让模型生成文字。下一个问题来自普通软件工程：**如果读取结果的是程序，而不是人，怎么办？**

---

## 4. Structured Output：让模型输出遵守数据契约

假设程序需要把用户请求整理成任务卡。模型返回：

```text
This seems important. We probably need current weather data first.
```

人类可以理解，但程序很难稳定读取。你当然可以写：

```python
if "important" in answer.lower():
    priority = "high"
```

但这相当于让程序靠猜词办案。模型把 `important` 换成 `urgent`，接口就悄悄坏了。

程序真正希望得到的是明确对象：

```json
{
  "goal": "compare current weather in Tokyo and Paris",
  "priority": "medium",
  "needs_external_data": true,
  "reason": "current weather must be retrieved"
}
```

Structured Output 的目标不是“让输出看起来像 JSON”，而是让模型输出符合**机器可验证的数据结构**。

运行：

```bash
python stages/00-foundations/code/structured_output.py
```

完整代码位于 [`code/structured_output.py`](code/structured_output.py)。

### 4.1 先定义应用需要什么，再让模型填写

本章使用 Pydantic 定义任务卡：

```python
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    priority: Priority
    needs_external_data: bool
    reason: str = Field(min_length=1)
```

这份定义同时表达：

- 字段名称；
- 字段类型；
- 允许的枚举值；
- 必填约束；
- 是否允许额外字段。

设计顺序很重要：

```text
先确定应用需要的数据
        ↓
把需求写成 schema
        ↓
再让模型按 schema 生成
```

反过来先让模型自由发挥，再从结果里捞字段，通常会把应用接口变成移动靶。

### 4.2 SDK 将响应解析为 Pydantic 对象

核心调用如下：

```python
response = client.responses.parse(
    model=model,
    instructions=(
        "Turn the request into a task card. Describe only the request itself; "
        "do not guess the weather or pretend that external data was retrieved."
    ),
    input=(
        "Compare the current weather in Tokyo and Paris and tell me which city "
        "is warmer."
    ),
    text_format=TaskCard,
)
```

然后检查解析结果：

```python
task = response.output_parsed
if task is None:
    raise RuntimeError("The response contained no parsed TaskCard.")
```

此时 `task` 已经是 `TaskCard`。普通代码可以直接访问 `task.priority`，不必在散文里寻找关键词。

### 4.3 三层“正确”必须分开

Structured Output 最容易制造一种错觉：既然通过了校验，结果就一定正确。实际上至少有三层：

| 层次 | 要回答的问题 | Schema 能否保证 |
|---|---|---|
| 语法 | JSON 能否解析？ | 可以约束 |
| 结构 | 字段、类型和值域是否正确？ | 可以约束 |
| 语义与事实 | 判断是否合理、事实是否真实？ | 不能单独保证 |

例如下面的对象可能完全符合结构：

```json
{
  "goal": "compare current weather",
  "priority": "high",
  "needs_external_data": false,
  "reason": "the model already knows it"
}
```

字段都合法，但对“当前天气”而言，`needs_external_data=false` 很可能是错误判断。

因此请记住：

> **结构化输出解决“程序怎样可靠读取”，不自动解决“内容为什么可信”。**

Schema 像门卫，能检查表格是否填齐；它不会顺便调查填写者讲的故事是否属实。

### 4.4 适用范围

Structured Output 适合：

- 分类结果；
- 参数提取；
- 路由决定；
- 表单化数据；
- 程序后续需要读取的计划或判断。

它不等于：

- 外部事实来源；
- 执行权限；
- 数据库事务；
- 对结论真实性的证明。

“比较当前天气”恰好暴露了下一层问题：模型需要应用提供外部能力。

---

## 5. Tool Calling：模型请求，应用执行

当用户要求查询天气、读取订单、调用计算器或修改文件时，单纯生成文字不够。应用需要向模型描述可请求的能力。

一个 Tool 有两个面：

```text
模型看到的接口
├── name
├── description
└── parameters（JSON Schema）

应用拥有的实现
└── Python handler
```

模型通常只看到接口说明，不会直接拿到 Python 函数的控制权。

本章使用固定教学天气：

```python
TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}
```

它不是实时天气。固定数据保证每次结果一致，让我们只观察 Tool Calling 的控制流程，而不是同时排查网络、认证、限流和气象变化。教学实验里少一个随机变量，就少一位临时演员抢戏。

运行：

```bash
python stages/00-foundations/code/tool_calling.py
```

完整代码位于 [`code/tool_calling.py`](code/tool_calling.py)。

### 5.1 Tool schema 是给模型看的使用说明

天气 Tool 的核心定义如下：

```python
WEATHER_TOOL = {
    "type": "function",
    "name": "get_teaching_weather",
    "description": (
        "Return the deterministic teaching weather record for Tokyo or Paris. "
        "Use this function whenever the user asks about those teaching records."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "enum": sorted(TEACHING_WEATHER),
            }
        },
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}
```

Tool description 不是普通注释。模型会根据名称、描述和参数结构判断何时调用以及怎样填写参数。

一份清楚的说明至少应回答：

- 工具返回什么；
- 什么时候使用；
- 参数表示什么；
- 有哪些明确限制。

如果描述只写 `query things`，模型不是获得了自由，而是被迫猜测。

### 5.2 Handler 才是真正执行的程序

真正读取数据的是 Python 函数：

```python
def get_teaching_weather(city: str) -> dict[str, Any]:
    try:
        record = TEACHING_WEATHER[city]
    except KeyError as exc:
        raise ValueError(f"Unsupported city: {city}") from exc
    return {"city": city, **record}
```

这里必须区分三个事件：

```text
工具被描述给模型
        ≠
模型请求调用工具
        ≠
应用执行 Python 函数
```

前两个事件不会自动触发第三个。

### 5.3 第一轮：模型生成调用提案

示例为了稳定演示，强制模型请求指定工具：

```python
first = client.responses.create(
    model=model,
    instructions=(
        "Use the supplied function to read teaching weather records. A function "
        "call only requests an action; never claim a result before the function "
        "output is returned."
    ),
    input=(
        "Read Tokyo's deterministic teaching weather record and report the "
        "temperature and condition."
    ),
    tools=[WEATHER_TOOL],
    tool_choice={"type": "function", "name": "get_teaching_weather"},
    parallel_tool_calls=False,
)
```

- `tools` 描述可请求的能力；
- `tool_choice` 强制本例调用指定函数；
- `parallel_tool_calls=False` 让本轮只保留单个调用，便于观察最小闭环。

第一轮返回 `function_call` 时，函数仍未执行。它更像一张动作申请单。

### 5.4 模型参数仍然是外部输入

应用先提取并检查调用：

```python
calls = [item for item in first.output if item.type == "function_call"]
if len(calls) != 1:
    raise RuntimeError(...)

call = calls[0]
if call.name != "get_teaching_weather":
    raise RuntimeError(...)
```

随后解析和验证参数：

```python
arguments = parse_arguments(call.arguments)
city = validate_weather_arguments(arguments)
result = get_teaching_weather(city)
```

顺序不能颠倒：

```text
读取提案
  ↓
解析 JSON
  ↓
检查字段、类型和值域
  ↓
调用明确允许的 Python 函数
```

不要把模型返回的名称直接交给 `eval()`、`exec()`、`globals()` 或任意动态导入。模型输出是外部数据，不是自动获得执行资格的代码。

示例同时保留两层约束：

```text
Provider 侧 strict schema
    尽量约束模型生成的参数形状

应用侧显式验证
    检查真正准备交给 handler 的数据
```

真正执行函数的是应用，所以应用必须对最终接受的数据负责。

### 5.5 `call_id` 保存动作与结果的因果关系

工具执行后，应用返回：

```python
{
    "type": "function_call_output",
    "call_id": call.call_id,
    "output": json.dumps(result, ensure_ascii=False),
}
```

`call_id` 表示这份结果属于哪一次请求。即使两个调用使用同一个工具名，它们仍是两个不同动作：

```text
call_A → get_teaching_weather(Tokyo)
call_B → get_teaching_weather(Paris)
```

工具名回答“调用什么”，调用编号回答“是哪一次”。丢掉 `call_id`，就像餐厅把两桌客人的点菜单都写成“牛肉面”，然后宣布关联信息不重要。

### 5.6 第二轮：模型根据真实 Tool Output 回答

第二次请求把工具结果接到第一次响应之后：

```python
final = client.responses.create(
    model=model,
    instructions=(
        "Answer only from the returned function output. Make clear that this is "
        "a deterministic teaching record, not live weather."
    ),
    previous_response_id=first.id,
    input=[
        {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(result, ensure_ascii=False),
        }
    ],
    tools=[WEATHER_TOOL],
    tool_choice="none",
)
```

两个编号关联的对象不同：

```text
previous_response_id
    当前模型响应接在哪次模型响应之后

call_id
    当前工具结果属于哪个工具请求
```

第二轮使用 `tool_choice="none"`，要求模型不再请求工具，而是根据已经返回的结果生成文字。

完整时间线如下：

```text
用户提出任务
    ↓
模型生成 Function Call
    ↓
应用检查名称和参数
    ↓
应用执行 Python 函数
    ↓
应用返回 Function Call Output
    ↓
模型根据观察结果生成最终文字
```

这就是第一个完整的 `model → tool → model` 往返。

---

## 6. 四个相似概念，职责完全不同

| 概念 | 它是什么 | 它不是什么 |
|---|---|---|
| 普通文本输出 | 模型生成的语言 | 已发生的现实动作 |
| Structured Output | 符合数据契约的模型结果 | 事实真实性证明 |
| Tool Call | 模型提出的结构化动作请求 | Python 函数已经执行 |
| Tool Output | 应用执行后返回的观察结果 | 模型自己的猜测 |

可以用办事流程类比：

```text
Structured Output  像填写规范的表格
Tool Call           像提交动作申请
Tool Execution      像工作人员真正办理
Tool Output         像办理结果回执
```

表格填得再工整，也不会自己跑去盖章。

---

## 7. 什么时候开始需要 Runtime

本章最后的代码仍是固定脚本：

```text
第一次模型调用
→ 执行一次工具
→ 第二次模型调用
→ 结束
```

如果任务变成：

```text
查询东京教学天气
→ 把摄氏度换算成华氏度
→ 根据两个结果回答
```

程序可能需要两个 Tool Call。继续手写 `first`、`second`、`third`，很快会得到一份按辈分命名的控制流。

真正需要抽象的是：

```python
while 运行尚未结束:
    让模型决定下一步
    如果是 Tool Call:
        应用执行并记录结果
    否则:
        返回最终答案
```

下一章会构建这层 Runtime。本章在这里停下，不提前把后续所有术语塞给读者。此刻只需要牢牢记住：**模型调用、工具请求、工具执行和结果回传是四个独立步骤。**

---

## 8. 常见误区

### 误区一：“模型知道函数名，所以它能调用函数”

模型只能生成名称和参数。应用必须拥有实现、允许该能力、验证输入并显式调用。

### 误区二：“strict schema 已经验证过，应用不用再检查”

Provider 侧约束帮助生成规范数据；应用侧验证保护真正的执行边界。它们位于不同位置。

### 误区三：“JSON 能解析，所以内容可信”

JSON 只能证明语法和结构。事实正确性需要真实数据来源或业务规则。

### 误区四：“返回 Tool Call，说明工具已经成功或失败”

Tool Call 只表示模型请求执行。成功与失败要等应用实际运行 handler 后才能知道。

### 误区五：“模型语气很确定，所以一定有依据”

语气是生成风格，不是证据等级。应检查数据来源和执行轨迹，而不是句号有多坚定。

### 误区六：“把所有历史都传进去，模型就会更聪明”

模型根据本轮可见上下文生成结果。更多文本不一定更相关，也不自动更可靠。本章只建立上下文边界，不展开复杂的上下文选择策略。

---

## 9. 失败应该在哪一层被发现

| 失败 | 首先负责处理的边界 |
|---|---|
| 环境变量缺失 | 应用启动边界 |
| Provider 响应未完成 | API 调用代码 |
| 最终文本为空 | 输出检查边界 |
| Structured Output 无法解析 | 结构化输出边界 |
| Tool 参数不是合法 JSON | 参数解析边界 |
| Tool 名称未知 | 工具路由边界 |
| 字段、类型或值域错误 | 应用验证边界 |
| Python handler 抛异常 | 工具执行边界 |

把错误放回真正所属的层，调试才不会只剩一句万能诊断：“Agent 好像不太聪明。”

---

## 10. 动手练习

### 练习一：证明自然语言接口很脆弱

让模型分别使用 `important`、`urgent`、`high priority` 表达优先级，再尝试用字符串规则解析。记录需要多少补丁才能覆盖。

### 练习二：给任务卡增加置信度

在 `TaskCard` 中加入 0 到 1 的 `confidence` 字段。验证范围约束后回答：`confidence=0.99` 能证明结论真实吗？

### 练习三：制造结构正确但语义错误的对象

让请求明确需要当前数据，却引导模型输出 `needs_external_data=false`。观察 schema 为什么仍可能接受它。

### 练习四：查询巴黎教学天气

只修改用户输入，不改 handler。追踪 `Paris` 如何经过 Tool Call 参数、应用验证、Python 函数和 Tool Output。

### 练习五：破坏 `call_id`

在纸上画两个同名工具调用，再删掉调用编号。尝试判断每份结果属于哪次请求。

### 练习六：让参数验证失败

分别尝试：

```json
{}
{"city": 42}
{"city": "Atlantis"}
{"city": "Tokyo", "debug": true}
```

说明每种输入应在哪一步被拒绝。

### 练习七：区分措辞与执行

让模型生成“工具已经执行成功”，但不要运行 handler。检查程序状态，说明为什么这句话不构成执行证据。

---

## 11. 本章自检

尝试不用背定义，直接回答：

1. 为什么 `response.output_text` 不是完整 Response？
2. `instructions` 与 `input` 的职责有什么差别？
3. Structured Output 能保证哪两层正确，不能保证哪一层？
4. Tool schema 与 Python handler 分别给谁使用？
5. Tool Call 在什么时刻才真正变成 Python 执行？
6. 为什么 Tool 参数需要在应用侧再次验证？
7. `call_id` 与 `previous_response_id` 各自关联什么？
8. 为什么固定教学数据比实时天气更适合本章？
9. 固定两轮脚本为什么还不是通用 Agent Runtime？

能够沿着数据流回答这些问题，就已经搭好了继续学习的地基。

---

## 12. 本章代码目录

```text
stages/00-foundations/
├── README.zh-CN.md
├── README.md
└── code/
    ├── first_llm_call.py      # 第一次 Responses API 调用
    ├── structured_output.py   # Pydantic 结构化输出
    ├── tool_calling.py        # 完整 model → tool → model 往返
    └── requirements.txt
```

完整实现只在 `code/` 中维护；正文中的代码块只用于解释当前知识点。

➡️ [Stage 01：把 Tool Loop 变成 Agent Runtime](../01-react-runtime/README.zh-CN.md)
